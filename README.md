# paper-critical-reading

[简体中文说明](README.zh-CN.md)

**Understand papers through first principles and critical thinking. Ground the model's explanations in original evidence.**

AI can produce a fluent summary without explaining why a method was designed that way. It can also present a plausible inference as something the paper actually says. This repository aims to take reading further: connect the problem, design, and evidence, and make the model's claims possible to check.

It provides a paper-reading skill for Codex or Claude and accompanying local PDF tools. Reading happens primarily in chat: ask questions, explore mechanisms, and challenge conclusions. Request source locations when you want to check a claim, or a full report when you want a systematic review.

## How to understand a paper

The reading follows a chain of questions:

**Why does the problem exist → why this design → what insight led to the contribution → what do the experiments or proofs support → where are the limitations?**

- Start with the task, assumptions, and constraints to explain the mechanisms behind earlier methods' difficulties.
- Connect the problem, insight, and concrete design to explain how the method works and why it might help.
- Examine actual experimental settings, comparison conditions, ablations, or proof assumptions to assess the strength of the conclusions.
- Separate limitations acknowledged by the authors, criticism grounded in evidence, and research opportunities that still need validation.

These questions guide the reading without requiring seven sections in every answer. A focused follow-up may need only a paragraph. When reconstructing a possible path to the design, motivations not explicitly stated in the paper must be labelled as inferred.

## Citations on request. Evidence throughout.

Factual claims about a paper should rest on original content the model has actually read. The skill requires a distinction between **what the authors state, what the model infers, and what the available evidence cannot establish**. An unsuccessful search does not prove an experiment is absent; a partial read must not be presented as a complete review.

When you request a source citation, the model selects relevant original text and the runtime verifies it before generating a link. Clicking opens the saved PDF at the quoted words with line-by-line highlights so you can inspect the evidence yourself. Citations can support any claim you ask to check, not just novelty or limitations.

Text verification rejects fabricated or paraphrased quotations, but cannot automatically establish that an interpretation is correct. The surrounding context and qualifications must still support the claim. This workflow aims to constrain and expose unsupported answers; it does not guarantee that every hallucination is eliminated.

## Read through conversation

After installation, supply an accessible paper link or local PDF path and begin with a question:

> Read https://arxiv.org/abs/1706.03762v7. Explain the problem it addresses and why the method is designed this way.

Follow up on what you want to understand:

> Why might this design work? Which explanations come from the authors, and which are your inferences?

> Do the experiments actually support that conclusion? What conditions matter?

When you want to check a claim:

> Add an original-text citation for that conclusion so I can click through and verify it.

When you want a complete review:

> Generate a full critical-reading report for this paper.

| Request | Behavior |
|---|---|
| Read, explain, analyze, or answer a follow-up | Read sufficient context and answer in chat; skip the full-report and citation workflows |
| Cite a claim, locate original text, or provide a highlight link | Generate evidence links for the requested claims without generating a report |
| Generate a full report or full critical review | Load the full-review framework and respond in chat; citations are not automatic |
| Save or export a report | Create a separate file |

Reports and citations require separate explicit requests; you can request both together. Standing instructions such as “include citations in all follow-ups” remain active until changed. Follow-ups reuse the same paper and sufficient existing context, reading more as needed. This avoids unnecessary output and citation work; the amount of reading still depends on the question, with no fixed token budget.

### Full-report structure

Use this framework only when a full report is explicitly requested, adapting it to the paper type:

| Section | Question |
|---|---|
| TL;DR | What problem does the method address, and what result was observed? |
| 1. Task | What are the inputs, outputs, objectives, metrics, and assumptions? |
| 2. Challenge | Where do earlier methods struggle or face tradeoffs? |
| 3. Method | What are the information flow, training, and inference procedures? |
| 4. Insight & Novelty | What insight connects the problem to the design? What is contributed? |
| 5. Evidence & Validation | What do experiments or proofs support, and where does the evidence stop? |
| 6. Potential Flaw | What limitations do the authors acknowledge or the analysis identify? Which opportunities need further validation? |
| 7. Motivation | How could the design follow from the problem? Unstated motivations are labelled as inferred |

A full report requires coverage of the main text and relevant appendices, with any reading gaps disclosed. Theory, survey, and systems papers are assessed using their relevant forms of evidence. See the [full framework](en/references/critical-reading.md).

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

Supply an accessible paper link or an absolute PDF path on the machine running the MCP server. A chat attachment may live in a different sandbox and is not automatically a local file for the server.

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

## Language versions

| Folder | Skill name | Instructions |
|---|---|---|
| `en/` | `paper-critical-reading` | English |
| `zh/` | `paper-critical-reading-zh` | Chinese |

Both respond in the conversation's language.

## License

Repository source: Apache-2.0, see [LICENSE](LICENSE). The separately installed PyMuPDF dependency has its own [AGPL/commercial licensing](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright).
