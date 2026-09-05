"""Resolve user-selected files and public paper URLs without bypassing access controls."""

from __future__ import annotations

import ipaddress
import socket
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

MAX_DOWNLOAD = 64 * 1024 * 1024


class PaperError(ValueError):
    """An actionable error safe to return to a CLI or MCP client."""


def normalize_source(source: str) -> str:
    source = source.strip()
    if source.startswith("10.") and "/" in source:
        source = "https://doi.org/" + source
    try:
        parsed = urllib.parse.urlsplit(source)
    except ValueError as exc:
        raise PaperError("The paper URL is malformed. Supply a valid URL or local PDF path.") from exc
    if parsed.scheme in ("http", "https"):
        if parsed.hostname in ("arxiv.org", "www.arxiv.org", "export.arxiv.org"):
            parts = parsed.path.strip("/").split("/", 1)
            if len(parts) == 2 and parts[0] in ("abs", "pdf", "html"):
                identifier = parts[1].removesuffix(".pdf")
                return "https://arxiv.org/pdf/" + identifier
        return urllib.parse.urlunsplit(parsed._replace(fragment=""))
    return str(Path(source).expanduser().resolve())


def validate_public_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise PaperError("Use an HTTP(S) paper URL or a local PDF path.")
    if parsed.username or parsed.password:
        raise PaperError("URLs containing credentials are not supported. Upload the PDF instead.")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise PaperError("Only public paper URLs are fetched. Import internal PDFs as local files.")
    except (OSError, ValueError) as exc:
        if isinstance(exc, PaperError):
            raise
        raise PaperError("Could not resolve this paper host.") from exc


class PublicRedirects(urllib.request.HTTPRedirectHandler):
    max_redirections = 5

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class PDFLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.preferred: list[str] = []
        self.other: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("name", "").lower() == "citation_pdf_url":
            if attrs.get("content"):
                self.preferred.append(attrs["content"])
        if tag == "link" and attrs.get("type", "").lower() == "application/pdf":
            if attrs.get("href"):
                self.preferred.append(attrs["href"])
        if tag == "a" and urllib.parse.urlsplit(attrs.get("href", "")).path.lower().endswith(".pdf"):
            self.other.append(attrs["href"])


def fetch_pdf(url: str) -> tuple[bytes, str]:
    opener = urllib.request.build_opener(PublicRedirects())
    visited: set[str] = set()
    for _ in range(3):
        validate_public_url(url)
        if url in visited:
            break
        visited.add(url)
        request = urllib.request.Request(url, headers={
            "User-Agent": "paper-critical-reading/0.2 (local research reader)",
            "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.5",
        })
        try:
            with opener.open(request, timeout=30) as response:
                final_url = response.geturl()
                size = response.headers.get("Content-Length")
                if size and int(size) > MAX_DOWNLOAD:
                    raise PaperError("This download exceeds the 64 MiB limit.")
                data = response.read(MAX_DOWNLOAD + 1)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            if isinstance(exc, PaperError):
                raise
            raise PaperError("Could not download the paper. Use a direct PDF link or upload the PDF.") from exc
        if len(data) > MAX_DOWNLOAD:
            raise PaperError("This download exceeds the 64 MiB limit.")
        if b"%PDF-" in data[:1024]:
            return data, final_url
        links = PDFLinks()
        links.feed(data[:2 * 1024 * 1024].decode("utf-8", errors="replace"))
        candidates = links.preferred or links.other
        if not candidates:
            break
        url = urllib.parse.urljoin(final_url, candidates[0])
    raise PaperError("No accessible PDF was found. Supply a direct PDF link or a downloaded PDF; login/paywalls are not bypassed.")


def load_pdf(source: str) -> tuple[bytes, str]:
    source = normalize_source(source)
    if urllib.parse.urlsplit(source).scheme in ("http", "https"):
        return fetch_pdf(source)
    path = Path(source)
    try:
        if path.stat().st_size > MAX_DOWNLOAD:
            raise PaperError("This PDF exceeds the 64 MiB limit.")
        data = path.read_bytes()
    except OSError as exc:
        raise PaperError("The PDF file is not readable. Supply a file path accessible to this process.") from exc
    if b"%PDF-" not in data[:1024]:
        raise PaperError("This file is not a PDF.")
    return data, source
