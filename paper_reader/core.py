"""Immutable PDF snapshots, positioned text, lexical retrieval, and verified citations."""

from __future__ import annotations

import collections
import hashlib
import json
import math
import os
import re
import secrets
import tempfile
import threading
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pymupdf

from .sources import PaperError, load_pdf, normalize_source

WRITE_LOCK = threading.RLock()
PDF_LOCK = threading.RLock()
ID_PATTERN = re.compile(r"[0-9a-f]{24}\Z")


def canonical(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).replace("\u00ad", "").split())


def tokens(text: str) -> list[str]:
    result = re.findall(r"[a-z0-9]+", canonical(text).lower())
    for run in re.findall(r"[\u3400-\u9fff]+", text):
        result.extend(run[i:i + 2] for i in range(max(1, len(run) - 1)))
    return result


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(value, handle, ensure_ascii=False, separators=(",", ":"))
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def positioned_text(block: dict, page) -> tuple[str, list[dict]]:
    """Map each normalized character to its real PDF glyph rectangle and line."""
    chars: list[str] = []
    positions: list[dict] = []
    for line_number, line in enumerate(block.get("lines", [])):
        if chars:
            # Normalize a discretionary line-end hyphen while keeping the glyph mapping.
            if chars[-1] in ("-", "\u00ad") and len(chars) > 1 and chars[-2].isalpha():
                chars.pop()
                positions.pop()
            elif chars[-1] != " ":
                chars.append(" ")
                positions.append({"line": line_number, "rect": None})
        for span in line["spans"]:
            for glyph in span["chars"]:
                rect = pymupdf.Rect(glyph["bbox"]) * page.rotation_matrix
                relative = [rect.x0 / page.rect.width, rect.y0 / page.rect.height,
                            rect.x1 / page.rect.width, rect.y1 / page.rect.height]
                for char in unicodedata.normalize("NFKC", glyph["c"]):
                    if char == "\u00ad":
                        continue
                    if char.isspace():
                        char = " "
                        if not chars or chars[-1] == " ":
                            continue
                    chars.append(char)
                    positions.append({"line": line_number, "rect": relative})
    while chars and chars[-1] == " ":
        chars.pop()
        positions.pop()
    return "".join(chars), positions


class PaperStore:
    def __init__(self, data_dir: str | Path | None = None, port: int = 8765):
        default = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "paper-critical-reading"
        self.root = Path(data_dir or os.environ.get("PAPER_READER_DATA_DIR", default)).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.port = port
        token_path = self.root / "reader-token"
        with WRITE_LOCK:
            try:
                descriptor = os.open(token_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(descriptor, "w") as handle:
                    handle.write(secrets.token_urlsafe(24))
            except FileExistsError:
                pass
            self.token = token_path.read_text().strip()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/r/{self.token}"

    def paper_dir(self, paper_id: str) -> Path:
        if not ID_PATTERN.fullmatch(paper_id):
            raise PaperError("Invalid paper ID. Use the ID returned by import_paper or list_papers.")
        return self.root / "papers" / paper_id

    def index(self, paper_id: str) -> dict:
        try:
            return json.loads((self.paper_dir(paper_id) / "index.json").read_text())
        except FileNotFoundError as exc:
            raise PaperError("Paper not found. Import the PDF first.") from exc

    def metadata(self, paper_id: str) -> dict:
        data = self.index(paper_id)
        reader_url = f"{self.base_url}/paper/{paper_id}"
        pages = [page | {"page_url": f"{reader_url}?page={page['number']}"} for page in data["pages"]]
        return {**data["metadata"], "pages": pages, "outline": data["outline"],
                "passage_count": len(data["passages"]), "reader_url": reader_url}

    def list_papers(self) -> list[dict]:
        return [self.metadata(path.parent.name) for path in sorted((self.root / "papers").glob("*/index.json"))]

    def import_paper(self, source: str, title: str | None = None, refresh: bool = False) -> dict:
        normalized = normalize_source(source)
        catalog_path = self.root / "sources.json"
        catalog = json.loads(catalog_path.read_text()) if catalog_path.exists() else {}
        # A local file may have changed in place; always hash it. URLs are explicitly refreshed.
        if normalized.startswith(("https://", "http://")) and not refresh and normalized in catalog:
            return {**self.metadata(catalog[normalized]), "cached": True}
        raw, resolved_source = load_pdf(normalized)
        digest = hashlib.sha256(raw).hexdigest()
        paper_id = digest[:24]
        destination = self.paper_dir(paper_id)
        if (destination / "index.json").exists():
            result = {**self.metadata(paper_id), "cached": True}
        else:
            try:
                with PDF_LOCK:
                    doc = pymupdf.open(stream=raw, filetype="pdf")
            except Exception as exc:
                raise PaperError("The downloaded file could not be opened as a PDF.") from exc
            with PDF_LOCK, doc:
                if doc.needs_pass:
                    raise PaperError("This PDF is password protected. Import an unlocked copy.")
                if not 0 < len(doc) <= 1000:
                    raise PaperError("Supported PDFs contain between 1 and 1,000 pages.")
                outline = [{"level": item[0], "title": item[1], "page": item[2]} for item in doc.get_toc() if item[2] > 0]
                passages, pages, unreadable = [], [], []
                for page_number, page in enumerate(doc, 1):
                    pages.append({"number": page_number, "width": page.rect.width, "height": page.rect.height})
                    page_count = 0
                    section = next((item["title"] for item in reversed(outline) if item["page"] <= page_number), None)
                    # Keep PDF block boundaries: a quote must not silently jump between columns.
                    for block in page.get_text("rawdict", sort=False)["blocks"]:
                        if block["type"] != 0:
                            continue
                        text, positions = positioned_text(block, page)
                        if not text:
                            continue
                        page_count += len(text)
                        passages.append({"id": f"p{page_number}-b{len(passages) + 1}", "page": page_number,
                                         "section": section, "text": text, "positions": positions})
                    if page_count < 40:
                        unreadable.append(page_number)
                metadata = {"paper_id": paper_id, "sha256": digest,
                            "title": title or doc.metadata.get("title") or Path(normalized).stem or paper_id,
                            "source": normalized, "resolved_source": resolved_source,
                            "imported_at": datetime.now(timezone.utc).isoformat(), "page_count": len(doc),
                            "low_text_pages": unreadable,
                            "warnings": (["Some pages have little extractable text. Inspect their page images; scanned text requires OCR before it can be quoted."] if unreadable else [])}
            with WRITE_LOCK:
                destination.mkdir(parents=True, exist_ok=True)
                (destination / "source.pdf").write_bytes(raw)
                atomic_json(destination / "index.json", {"schema_version": 1, "metadata": metadata,
                            "pages": pages, "outline": outline, "passages": passages})
            result = {**self.metadata(paper_id), "cached": False}
        with WRITE_LOCK:
            catalog = json.loads(catalog_path.read_text()) if catalog_path.exists() else {}
            catalog[normalized] = paper_id
            atomic_json(catalog_path, catalog)
        return result

    def read_passages(self, paper_id: str, page: int | None = None, start: int = 0, limit: int = 12) -> dict:
        passages = self.index(paper_id)["passages"]
        if page is not None:
            if not 1 <= page <= self.metadata(paper_id)["page_count"]:
                raise PaperError("Page number is outside this PDF.")
            passages = [p for p in passages if p["page"] == page]
        if start < 0 or not 1 <= limit <= 50:
            raise PaperError("Use start >= 0 and a limit between 1 and 50.")
        return {"paper_id": paper_id, "total": len(passages),
                "page_url": f"{self.base_url}/paper/{paper_id}?page={page}" if page is not None else None,
                "next_start": start + limit if start + limit < len(passages) else None,
                "passages": [self.public_passage(paper_id, p) for p in passages[start:start + limit]]}

    def public_passage(self, paper_id: str, passage: dict) -> dict:
        return {k: passage[k] for k in ("id", "page", "section", "text")} | {
            "passage_url": f"{self.base_url}/paper/{paper_id}?passage={passage['id']}"}

    def search(self, paper_id: str, query: str, limit: int = 5) -> dict:
        if not query.strip() or not 1 <= limit <= 20:
            raise PaperError("Supply a nonempty query and a limit between 1 and 20.")
        passages = self.index(paper_id)["passages"]
        terms = set(tokens(query))
        documents = [collections.Counter(tokens(p["text"])) for p in passages]
        average = sum(sum(d.values()) for d in documents) / max(len(documents), 1)
        frequency = {t: sum(t in d for d in documents) for t in terms}
        ranked = []
        for passage, counts in zip(passages, documents):
            score = 0.0
            for term in terms:
                tf = counts[term]
                if tf:
                    idf = math.log(1 + (len(documents) - frequency[term] + .5) / (frequency[term] + .5))
                    score += idf * tf * 2.2 / (tf + 1.2 * (.25 + .75 * sum(counts.values()) / max(average, 1)))
            if canonical(query).lower() in passage["text"].lower():
                score += 3
            if score:
                ranked.append((score, passage))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return {"paper_id": paper_id, "query": query, "retrieval": "lexical",
                "results": [self.public_passage(paper_id, p) for _, p in ranked[:limit]],
                "hint": "Use the paper's language for search terms. Read the surrounding passages before quoting."}

    def make_citation(self, paper_id: str, quote: str, passage_ids: list[str], occurrence: int | None = None) -> dict:
        quote = canonical(quote)
        if not quote or not passage_ids or len(passage_ids) > 8 or len(set(passage_ids)) != len(passage_ids):
            raise PaperError("Supply an exact quote and 1-8 distinct passage IDs in reading order.")
        index = self.index(paper_id)
        lookup = {p["id"]: p for p in index["passages"]}
        if any(identifier not in lookup for identifier in passage_ids):
            raise PaperError("Unknown passage ID. Use read_paper or search_paper results.")
        selected = [lookup[identifier] for identifier in passage_ids]
        order = {p["id"]: i for i, p in enumerate(index["passages"])}
        if any(order[b] != order[a] + 1 for a, b in zip(passage_ids, passage_ids[1:])):
            raise PaperError("A single quote must use adjacent passages in PDF extraction order. Create separate citations for separate evidence.")
        text, mapping = "", []
        for passage in selected:
            if text:
                text += " "
                mapping.append(None)
            text += passage["text"]
            mapping.extend((passage, position) for position in passage["positions"])
        matches = [match.start() for match in re.finditer(re.escape(quote), text)]
        if not matches:
            raise PaperError("The quote does not exactly match these passages. Copy the returned text; paraphrases and ellipses cannot create a citation.")
        if len(matches) > 1 and occurrence is None:
            raise PaperError(f"This quote occurs {len(matches)} times. Narrow the passage IDs or provide a 1-based occurrence.")
        occurrence = 1 if occurrence is None else occurrence
        if not 1 <= occurrence <= len(matches):
            raise PaperError("The requested quote occurrence does not exist.")
        offset = matches[occurrence - 1]
        groups = {}
        used_ids = []
        for item in mapping[offset:offset + len(quote)]:
            if item is None:
                continue
            passage, position = item
            if passage["id"] not in used_ids:
                used_ids.append(passage["id"])
            if position["rect"] is None:
                continue
            key = (passage["page"], passage["id"], position["line"])
            rect = position["rect"]
            previous = groups.get(key, rect)
            groups[key] = [min(previous[0], rect[0]), min(previous[1], rect[1]),
                           max(previous[2], rect[2]), max(previous[3], rect[3])]
        if not groups:
            raise PaperError("No reliable text coordinates are available for this quote.")
        boxes = [{"page": key[0], "rect": [round(max(0., min(1., v)), 7) for v in rect]}
                 for key, rect in groups.items()]
        payload = {"paper_id": paper_id, "quote": quote, "passage_ids": used_ids, "boxes": boxes}
        citation_id = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24]
        payload.update({"citation_id": citation_id, "pages": list(dict.fromkeys(b["page"] for b in boxes)),
                        "title": index["metadata"]["title"], "match": "exact-normalized"})
        with WRITE_LOCK:
            atomic_json(self.paper_dir(paper_id) / "citations" / f"{citation_id}.json", payload)
        return self.citation(paper_id, citation_id)

    def citation(self, paper_id: str, citation_id: str) -> dict:
        if not ID_PATTERN.fullmatch(citation_id):
            raise PaperError("Invalid citation ID.")
        try:
            data = json.loads((self.paper_dir(paper_id) / "citations" / f"{citation_id}.json").read_text())
        except FileNotFoundError as exc:
            raise PaperError("Citation not found. Create it from the exact original text first.") from exc
        url = f"{self.base_url}/paper/{paper_id}?cite={citation_id}"
        pages = ", ".join(str(p) for p in data["pages"])
        return {**data, "url": url, "markdown": f"[Original · PDF p. {pages}]({url})"}

    def passage_target(self, paper_id: str, passage_id: str) -> dict:
        passage = next((p for p in self.index(paper_id)["passages"] if p["id"] == passage_id), None)
        if passage is None:
            raise PaperError("Passage not found.")
        return self.make_citation(paper_id, passage["text"], [passage_id], occurrence=1) | {"match": "whole-passage"}

    def page_png(self, paper_id: str, page_number: int, scale: float = 1.5) -> bytes:
        if not math.isfinite(scale) or not 0.5 <= scale <= 3:
            raise PaperError("Page scale must be between 0.5 and 3.")
        with PDF_LOCK, pymupdf.open(self.paper_dir(paper_id) / "source.pdf") as doc:
            if not 1 <= page_number <= len(doc):
                raise PaperError("Page number is outside this PDF.")
            page = doc[page_number - 1]
            if page.rect.width * page.rect.height * scale * scale > 20_000_000:
                raise PaperError("This page is too large to render at the requested scale.")
            return page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes("png")
