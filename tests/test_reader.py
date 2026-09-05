"""Behavioral tests for citation integrity, real PDF geometry, URLs, and HTTP routes."""

import io
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

import pymupdf

from paper_reader.core import PaperStore, canonical
from paper_reader.server import reader_server
from paper_reader.sources import PaperError, PDFLinks, fetch_pdf, normalize_source, validate_public_url


def make_pdf(path):
    with pymupdf.open() as doc:
        page = doc.new_page(width=612, height=792)
        page.insert_text((48, 50), "A small navigation study", fontsize=18)
        page.insert_text((48, 110), "We evaluate the policy on held-out scenes.\nThe model uses only RGB observations.", fontsize=11)
        page.insert_text((340, 110), "The model uses only RGB observations.\nDepth is not supplied at test time.", fontsize=11)
        page.insert_text((48, 230), "Our naviga-\ntion policy avoids unsafe actions.", fontsize=11)
        page.insert_text((48, 330), "Repeated evidence. Repeated evidence.", fontsize=11)
        second = doc.new_page(width=612, height=792)
        second.insert_text((48, 100), "Ablation results are reported in Table 2.", fontsize=12)
        doc.set_metadata({"title": "Navigation evidence fixture"})
        doc.set_toc([[1, "Method", 1], [1, "Experiments", 2]])
        doc.save(path)


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.pdf = self.path / "paper.pdf"
        make_pdf(self.pdf)
        self.store = PaperStore(self.path / "store", port=0)
        self.paper = self.store.import_paper(str(self.pdf))["paper_id"]
        self.passages = self.store.read_passages(self.paper, limit=50)["passages"]

    def tearDown(self):
        self.temp.cleanup()

    def passage(self, text):
        return next(p for p in self.passages if text in p["text"])

    def test_multiline_quote_has_separate_real_line_boxes(self):
        p = self.passage("We evaluate")
        citation = self.store.make_citation(self.paper, p["text"], [p["id"]])
        self.assertEqual(len(citation["boxes"]), 2)
        self.assertEqual(citation["pages"], [1])
        with pymupdf.open(self.pdf) as doc:
            expected = doc[0].search_for("We evaluate the policy on held-out scenes.")[0]
        actual = citation["boxes"][0]["rect"]
        self.assertAlmostEqual(actual[0] * 612, expected.x0, places=3)
        self.assertAlmostEqual(actual[2] * 612, expected.x1, places=3)
        self.assertLess(actual[2], .5)

    def test_short_quote_does_not_highlight_the_whole_paragraph(self):
        p = self.passage("We evaluate")
        citation = self.store.make_citation(self.paper, "only RGB", [p["id"]])
        self.assertEqual(len(citation["boxes"]), 1)
        with pymupdf.open(self.pdf) as doc:
            expected = doc[0].search_for("only RGB")[0]
        actual = citation["boxes"][0]["rect"]
        self.assertAlmostEqual(actual[0] * 612, expected.x0, places=3)
        self.assertAlmostEqual(actual[2] * 612, expected.x1, places=3)

    def test_repeated_sentence_uses_selected_column(self):
        p = self.passage("Depth is not")
        citation = self.store.make_citation(self.paper, "The model uses only RGB observations.", [p["id"]])
        self.assertGreater(citation["boxes"][0]["rect"][0], .5)

    def test_ambiguous_quote_requires_occurrence(self):
        p = self.passage("Repeated evidence")
        with self.assertRaisesRegex(PaperError, "occurs 2 times"):
            self.store.make_citation(self.paper, "Repeated evidence.", [p["id"]])
        first = self.store.make_citation(self.paper, "Repeated evidence.", [p["id"]], 1)
        second = self.store.make_citation(self.paper, "Repeated evidence.", [p["id"]], 2)
        self.assertNotEqual(first["citation_id"], second["citation_id"])
        self.assertLess(first["boxes"][0]["rect"][0], second["boxes"][0]["rect"][0])
        with self.assertRaisesRegex(PaperError, "does not exist"):
            self.store.make_citation(self.paper, "Repeated evidence.", [p["id"]], 0)

    def test_paraphrase_and_noncontiguous_quote_rejected(self):
        p = self.passage("We evaluate")
        with self.assertRaisesRegex(PaperError, "exactly match"):
            self.store.make_citation(self.paper, "The policy uses RGB and depth.", [p["id"]])
        with self.assertRaisesRegex(PaperError, "adjacent"):
            self.store.make_citation(self.paper, "anything", [self.passages[0]["id"], self.passages[-1]["id"]])

    def test_line_break_hyphenation_search_and_quote(self):
        results = self.store.search(self.paper, "navigation policy")["results"]
        p = next(p for p in results if "Our navigation" in p["text"])
        citation = self.store.make_citation(self.paper, "navigation policy", [p["id"]])
        self.assertEqual(len(citation["boxes"]), 2)

    def test_snapshots_and_citations_survive_restart(self):
        p = self.passage("Ablation results")
        a = self.store.make_citation(self.paper, p["text"], [p["id"]])
        again = PaperStore(self.path / "store", port=0)
        self.assertEqual(again.citation(self.paper, a["citation_id"])["url"], a["url"])
        self.assertTrue(again.import_paper(str(self.pdf))["cached"])
        with pymupdf.open(self.pdf) as doc:
            doc[0].insert_text((48, 400), "A new revision.")
            doc.save(self.path / "revision.pdf")
        b = again.import_paper(str(self.path / "revision.pdf"))
        self.assertNotEqual(self.paper, b["paper_id"])
        self.assertEqual(again.citation(self.paper, a["citation_id"])["quote"], a["quote"])

    def test_rotated_page_coordinates_match_rendered_page(self):
        with pymupdf.open(self.pdf) as doc:
            doc[0].set_rotation(90)
            doc.save(self.path / "rotated.pdf")
        paper_id = self.store.import_paper(str(self.path / "rotated.pdf"))["paper_id"]
        p = next(p for p in self.store.read_passages(paper_id, limit=50)["passages"] if "We evaluate" in p["text"])
        citation = self.store.make_citation(paper_id, "We evaluate", [p["id"]])
        with pymupdf.open(self.path / "rotated.pdf") as doc:
            page = doc[0]
            rect = page.search_for("We evaluate")[0] * page.rotation_matrix
            actual = citation["boxes"][0]["rect"]
            self.assertAlmostEqual(actual[0] * page.rect.width, rect.x0, places=3)
            self.assertAlmostEqual(actual[1] * page.rect.height, rect.y0, places=3)

    def test_cropped_page_coordinates_match_visible_page(self):
        with pymupdf.open(self.pdf) as doc:
            doc[0].set_cropbox(pymupdf.Rect(25, 25, 590, 770))
            doc[0].set_rotation(270)
            doc.save(self.path / "cropped.pdf")
        paper_id = self.store.import_paper(str(self.path / "cropped.pdf"))["paper_id"]
        p = self.store.search(paper_id, "We evaluate")["results"][0]
        citation = self.store.make_citation(paper_id, "We evaluate", [p["id"]])
        with pymupdf.open(self.path / "cropped.pdf") as doc:
            page = doc[0]
            expected = page.search_for("We evaluate")[0] * page.rotation_matrix
            actual = citation["boxes"][0]["rect"]
            dimensions = [page.rect.width, page.rect.height] * 2
            for got, dimension, want in zip(actual, dimensions, expected):
                self.assertAlmostEqual(got * dimension, want, places=3)

    def test_url_cache_and_refresh_keep_old_citations(self):
        source = "https://arxiv.org/abs/1706.03762v7"
        with pymupdf.open(self.pdf) as doc:
            doc[0].insert_text((48, 400), "A changed online revision.")
            revision = doc.tobytes()
        with patch("paper_reader.core.load_pdf", side_effect=[
            (self.pdf.read_bytes(), "https://arxiv.org/pdf/1706.03762v7"),
            (revision, "https://arxiv.org/pdf/1706.03762v7"),
        ]) as download:
            first = self.store.import_paper(source)
            p = self.passage("We evaluate")
            citation = self.store.make_citation(first["paper_id"], "We evaluate", [p["id"]])
            self.assertTrue(self.store.import_paper(source)["cached"])
            self.assertEqual(download.call_count, 1)
            refreshed = self.store.import_paper(source, refresh=True)
            self.assertEqual(download.call_count, 2)
            self.assertNotEqual(first["paper_id"], refreshed["paper_id"])
            self.assertEqual(self.store.citation(first["paper_id"], citation["citation_id"])["quote"], "We evaluate")

    def test_scanned_page_is_reported_not_silently_read(self):
        with pymupdf.open() as doc:
            doc.new_page()
            doc.save(self.path / "blank.pdf")
        result = self.store.import_paper(str(self.path / "blank.pdf"))
        self.assertEqual(result["low_text_pages"], [1])
        self.assertEqual(result["passage_count"], 0)

    def test_http_citation_pdf_page_and_assets(self):
        with reader_server(self.store) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                p = self.passage("Ablation results")
                citation = self.store.make_citation(self.paper, p["text"], [p["id"]])
                with urllib.request.urlopen(citation["url"]) as response:
                    self.assertIn(b"Original evidence", response.read())
                    self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
                api = f"{self.store.base_url}/api/papers/{self.paper}"
                for route, magic in [("/source.pdf", b"%PDF"), ("/pages/2.png", b"\x89PNG")]:
                    with urllib.request.urlopen(api + route) as response:
                        self.assertTrue(response.read().startswith(magic))
                with urllib.request.urlopen(api + "/citations/" + citation["citation_id"]) as response:
                    self.assertEqual(json.load(response)["quote"], p["text"])
                for asset in ("reader.js", "reader.css"):
                    with urllib.request.urlopen(self.store.base_url + "/assets/" + asset) as response:
                        self.assertGreater(len(response.read()), 500)
                with self.assertRaises(urllib.error.HTTPError):
                    urllib.request.urlopen(f"http://127.0.0.1:{self.store.port}/api/papers/{self.paper}")
                with self.assertRaises(urllib.error.HTTPError):
                    urllib.request.urlopen(api + "/pages/2.png?scale=nan")
            finally:
                server.shutdown()


class SourceTests(unittest.TestCase):
    def test_arxiv_versions_and_doi(self):
        self.assertEqual(normalize_source("https://arxiv.org/abs/1706.03762v7"), "https://arxiv.org/pdf/1706.03762v7")
        self.assertEqual(normalize_source("https://arxiv.org/pdf/cs/9901001.pdf"), "https://arxiv.org/pdf/cs/9901001")
        self.assertEqual(normalize_source("10.1000/example"), "https://doi.org/10.1000/example")

    def test_publisher_metadata_prioritized(self):
        links = PDFLinks()
        links.feed('<a href="supplement.pdf">Supplement</a><meta content="paper.pdf" name="citation_pdf_url">')
        self.assertEqual(links.preferred, ["paper.pdf"])

    def test_internal_addresses_and_credentials_rejected(self):
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]):
            with self.assertRaisesRegex(PaperError, "public"):
                validate_public_url("https://example.com/paper.pdf")
        with self.assertRaisesRegex(PaperError, "credentials"):
            validate_public_url("https://user:password@example.com/paper.pdf")

    def test_quote_normalization(self):
        self.assertEqual(canonical("  A  ﬁnal\nresult  "), "A final result")

    def test_publisher_pdf_resolution_uses_final_page_url(self):
        class Response(io.BytesIO):
            headers = {}

            def __init__(self, data, url):
                super().__init__(data)
                self.url = url

            def geturl(self):
                return self.url

        landing = Response(b'<meta name="citation_pdf_url" content="../files/paper.pdf">',
                           "https://publisher.example/articles/123")
        pdf = Response(b"%PDF-1.7\nfixture", "https://publisher.example/files/paper.pdf")
        with patch("paper_reader.sources.validate_public_url") as validate, \
                patch("paper_reader.sources.urllib.request.build_opener") as build:
            build.return_value.open.side_effect = [landing, pdf]
            content, url = fetch_pdf("https://doi.org/10.1000/example")
            self.assertTrue(content.startswith(b"%PDF"))
            self.assertEqual(url, "https://publisher.example/files/paper.pdf")
            self.assertEqual(validate.call_args_list[-1].args[0], url)
            request = build.return_value.open.call_args_list[-1].args[0]
            self.assertEqual(request.full_url, url)


if __name__ == "__main__":
    unittest.main()
