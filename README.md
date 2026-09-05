# paper-critical-reading

[简体中文说明](README.zh-CN.md)

Critical paper reading and follow-up Q&A in your existing Codex or Claude chat. By default, the assistant reads and answers in chat. Full reports and **clickable original-text evidence** are generated independently, only when explicitly requested. Each citation link opens the saved PDF at the quoted words with line-by-line boxes and highlights.

The original first-principles critical-reading framework remains available: instead of summarizing what the paper says, it forces a structured breakdown — the formalized problem, why prior methods fail mechanically, which insight the novelty came from (any inspiration not explicitly stated by the paper is flagged as inferred), whether the experiments actually support the claims, a three-layer limitation analysis, and a first-principles reconstruction of how the authors likely arrived at the idea. Focused questions now get focused answers instead of a full report every time; ask for the full review described under "Full-review structure" below when you want it.

## What is included

| Component | Responsibility |
|---|---|
| `en/` or `zh/` skill | Reading workflow, interpretation, criticism, and citation discipline |
| `paper_reader/` Python package | PDF/link import, positioned text, search, verified citations, CLI and MCP tools |
| Local web reader | Actual PDF page images, precise overlays, page navigation, zoom, and PDF download |
| `tests/` | Citation integrity, geometry, import behavior, HTTP routes, and an actual MCP stdio round trip |

No separate model API key, vector database, frontend build, or hosted service is required. The chat host supplies the model. Scripts handle deterministic source retrieval and positioning; no hooks are needed for this workflow.

## Input: a PDF or a paper link

| Input | Behavior |
|---|---|
| Local PDF path | Copy the PDF into the local cache and extract positioned text |
| arXiv abstract, PDF, or HTML URL | Resolve to the PDF, preserving an explicit version such as `v7` |
| Direct PDF URL | Download and index the PDF |
| DOI or publisher page | Follow redirects and look for PDF metadata/links; succeeds only if the PDF is accessible |

A link is enough **when its full PDF can be fetched**. Login/paywall pages, unsupported JavaScript-only download flows, or blocked hosts require a downloaded PDF or another accessible direct link. HTML-only papers and automatic OCR are not implemented.

Each distinct PDF gets a content-derived `paper_id`. Follow-up questions reuse that snapshot. URL imports are cached until `--refresh` / `refresh=true`; importing a changed local PDF produces a new ID. Old citations stay attached to the old bytes.

## Install the runtime

Requires Python 3.10+. Commands below use macOS/Linux shell syntax. On Windows, create the environment with `py -m venv .venv` and use `.venv\Scripts\python.exe` / `.venv\Scripts\paper-reader.exe`.

```bash
git clone https://github.com/liuyanliang666/paper-critical-reading.git
cd paper-critical-reading
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[mcp]'
```

The MCP extra uses the official Python SDK's v1 API and pins it below v2. Keep this checkout and its virtual environment in place: the generated client configuration uses that interpreter's absolute path. CLI-only use can install with `pip install -e .` instead.

## Connect a chat client

Install the runtime **and** one skill. Copying/uploading just `SKILL.md` provides reading instructions, not executable PDF tools.

### Claude Desktop

Print a configuration fragment:

```bash
.venv/bin/paper-reader config --client claude-desktop
```

Open Claude Desktop's Developer settings and edit its MCP configuration. Merge the printed `paper-reader` entry into the existing `mcpServers` object; preserve other servers. Restart the app and check that the paper tools are available. The command prints configuration and does not edit your settings. See the [official local MCP setup guide](https://modelcontextprotocol.io/docs/develop/connect-local-servers).

For the reading instructions, upload a ZIP containing your chosen skill folder (`en/` or `zh/`, including `references/`) using Claude's custom skill upload, then enable it. See [Claude's skill instructions](https://support.claude.com/en/articles/12512180-use-skills-in-claude). Skill availability depends on the client/account. MCP tools remain usable with explicit reading instructions if custom skills are unavailable.

### Local Codex clients

```bash
.venv/bin/paper-reader config --client codex
```

Run the printed `codex mcp add paper-reader -- ...` command, then check `codex mcp list`. See [Codex MCP configuration](https://developers.openai.com/codex/mcp).

Install one language version, including its references. For example, for English:

```bash
mkdir -p ~/.agents/skills/paper-critical-reading
cp -R en/. ~/.agents/skills/paper-critical-reading/
```

For Chinese, use `zh/.` and destination `~/.agents/skills/paper-critical-reading-zh/`. Choose one to avoid duplicate routing. See [Codex skill locations](https://developers.openai.com/codex/skills).

### Claude Code

Copy one skill into `~/.claude/skills/`, keeping the folder name equal to its frontmatter name, and register the same stdio MCP command with Claude Code's MCP settings. For example:

```bash
mkdir -p ~/.claude/skills/paper-critical-reading
cp -R en/. ~/.claude/skills/paper-critical-reading/
```

### Start asking questions

Supply an accessible paper link or an absolute PDF path on the machine running the MCP server. A chat attachment may live in a different sandbox and is not automatically a local file for the server.

For example: “Read https://arxiv.org/abs/1706.03762v7. Why does this model need positional information? Explain in Chinese and attach short original-text citations I can click.”

Follow-ups reuse `paper_id` and answer in chat without automatically creating citations or a full report; explicit standing requests such as “include citations in all follow-ups” remain active. Ask separately to “add an original-text citation for this claim” or “generate a full report.” These workflows trigger independently. Reports also appear in chat unless saving or exporting a file is requested.

## Use without MCP

Keep the reader running in one terminal:

```bash
.venv/bin/paper-reader serve
```

In another terminal:

```bash
.venv/bin/paper-reader import /absolute/path/to/paper.pdf
.venv/bin/paper-reader search --paper PAPER_ID --query 'technical keywords'
.venv/bin/paper-reader read --paper PAPER_ID --page 3
.venv/bin/paper-reader cite --paper PAPER_ID --passage PASSAGE_ID --quote 'exact text from the read result'
```

`PAPER_ID`, `PASSAGE_ID`, the page, and the quote are placeholders: use actual import/read results. Open the returned `url` to see the highlighted source. Follow `read --start N` using the returned `next_start` when more text remains. `--passage` can be repeated for adjacent blocks; duplicate text may require `--occurrence 2` after checking context.

Global options precede the subcommand, e.g. `paper-reader --data-dir /path/to/cache --port 8766 serve`. Use the **same directory and port** for the reader, CLI, and MCP configuration. Reconfigure the client after moving the environment or changing these values.

## Evidence contract

The model selects original text; code verifies it and records its location. Each citation stores the PDF identity, exact normalized quote, source block IDs, PDF page numbers, and normalized glyph rectangles. Line breaks, ligatures, and discretionary line-end hyphens are normalized. Different lines receive separate boxes, which scale with the page.

Invented or paraphrased quotes are rejected. Repeated text must be disambiguated, and nonadjacent passages cannot be silently joined into one citation. Matching verifies **where the text occurs**, not whether the assistant's interpretation is correct.

| Returned link | Meaning |
|---|---|
| Citation `url` | Verified quote with exact line boxes |
| `passage_url` | Whole text block, not an exact sentence |
| `page_url` | Page navigation for figures or other visual evidence; no sentence boxes |

Page numbers are 1-based positions in the PDF, which may differ from printed page labels. Chapter navigation uses existing PDF bookmarks; section detection is not inferred for unbookmarked PDFs.

## Reading environment and limits

- This version opens an ordinary link to a **local custom reader**, normally in the browser. Native Codex/Claude right-sidebar embedding and native citation-click interception are not implemented. The reader currently disallows iframe embedding.
- Run the service on the same machine where you click the links. A remote/cloud sandbox's `127.0.0.1` is not your laptop. Cloud-client integration would need a separately designed reachable service and authentication.
- The reader must remain running. The MCP process starts it automatically; CLI-only use needs `serve`. Restarting with the same cache and port restores old links. If two clients share one running reader, stopping its owning process stops that reader; restart one client or keep a standalone `serve` process running for shared use.
- The reader renders the actual PDF as page images with overlays. Its PDF image text is not selectable; the quote panel is selectable, and the original PDF can be downloaded. Scanned text needs an OCR workflow before verified text citations can be made.
- Text-block order and extraction quality depend on the PDF. Unusual layouts, formulas, and damaged text layers require visual inspection. Search is lexical, not multilingual semantic retrieval.
- Current import limits are 64 MiB and 1,000 pages. Password-protected PDFs must be unlocked before import.

PDFs and citations are saved locally under `~/.local/share/paper-critical-reading` by default (`XDG_DATA_HOME`, `PAPER_READER_DATA_DIR`, or `--data-dir` can override it). The reader binds only to loopback and uses an unguessable local URL token. There is no automatic upload to a separate paper service, but **text and page images returned through MCP are shared with your chat host**. Removing cached snapshots breaks their citations; no cache is committed to this repository.

## Development and verification

```bash
.venv/bin/python -m unittest discover -v
node --check paper_reader/web/reader.js
```

Tests generate temporary PDFs with independent source geometry, including two columns, repeated text, line wrapping, hyphenation, and rotation. They verify exact boxes, snapshot persistence, protected reader routes, and real MCP discovery/calls/image output. The MCP test is skipped without the optional SDK. Node is only needed for the optional JavaScript syntax check, not to run the reader.

These tests do not certify a specific desktop application's UI behavior or every publisher's download flow.

## Language versions and full review

| Folder | Skill name | Instructions |
|---|---|---|
| `en/` | `paper-critical-reading` | English |
| `zh/` | `paper-critical-reading-zh` | Chinese |

Both respond in the conversation's language.

### Full-review structure

| Section | What it answers |
|---|---|
| TL;DR | One sentence connecting the method, problem, and result |
| 1. Task | Formalized input/output space, objective, and metrics |
| 2. Challenge | Why prior methods fail mechanically, or what tradeoff they face |
| 3. Method | Neutral pipeline description, no evaluation yet |
| 4. Insight & Novelty | Problem → insight → concrete design for each main contribution; inspiration not explicitly stated by the authors is marked **inferred** |
| 5. Evidence & Validation | Whether experiments/proofs actually support the claims, and where the evidence stops |
| 6. Potential Flaw | Three layers: author-admitted limitations, critically-found limitations, and worth-a-paper research opportunities |
| 7. Motivation | A first-principles, rhetorical-question reconstruction of how the authors likely arrived at the idea |

Unstated inspirations remain labelled as inferred. Quotes can now support multiple claims, within the host's applicable quotation limits.

## License

Repository source: Apache-2.0, see [LICENSE](LICENSE). The separately installed PyMuPDF dependency has its own [AGPL/commercial licensing](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright).
