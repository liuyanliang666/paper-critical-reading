"""Exercise the actual stdio protocol and reader lifecycle, not just Python calls."""

import importlib.util
import json
import socket
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path

from tests.test_reader import make_pdf


@unittest.skipUnless(importlib.util.find_spec("mcp"), 'Install with pip install -e ".[mcp]" to test MCP')
class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_tool_round_trip(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            pdf = directory / "paper.pdf"
            make_pdf(pdf)
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            params = StdioServerParameters(command=sys.executable, args=[
                "-m", "paper_reader", "--data-dir", str(directory / "store"),
                "--port", str(port), "mcp",
            ])
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    names = {tool.name for tool in (await session.list_tools()).tools}
                    self.assertEqual(names, {"import_paper", "list_papers", "read_paper", "search_paper",
                                             "create_citation", "get_citation", "view_paper_page"})

                    async def call(name, **arguments):
                        result = await session.call_tool(name, arguments)
                        self.assertFalse(result.isError, result)
                        return json.loads(next(item.text for item in result.content if item.type == "text"))

                    imported = await call("import_paper", source=str(pdf))
                    paper = imported["paper_id"]
                    results = await call("search_paper", paper_id=paper, query="Depth supplied")
                    passage = results["results"][0]
                    context = await call("read_paper", paper_id=paper, page=passage["page"])
                    self.assertIn(passage["id"], [p["id"] for p in context["passages"]])
                    citation = await call("create_citation", paper_id=paper,
                                          quote="Depth is not supplied at test time.", passage_ids=[passage["id"]])
                    self.assertGreater(citation["boxes"][0]["rect"][0], .5)
                    with urllib.request.urlopen(citation["url"], timeout=5) as response:
                        self.assertIn(b"Original evidence", response.read())
                    restored = await call("get_citation", paper_id=paper, citation_id=citation["citation_id"])
                    self.assertEqual(restored, citation)
                    self.assertTrue((await call("import_paper", source=str(pdf)))["cached"])
                    page = await session.call_tool("view_paper_page", {"paper_id": paper, "page": 1})
                    self.assertFalse(page.isError)
                    self.assertEqual(page.content[0].type, "image")
                    self.assertEqual(page.content[0].mimeType, "image/png")
                    bad = await session.call_tool("create_citation", {
                        "paper_id": paper, "quote": "This sentence was invented.", "passage_ids": [passage["id"]],
                    })
                    self.assertTrue(bad.isError)


if __name__ == "__main__":
    unittest.main()
