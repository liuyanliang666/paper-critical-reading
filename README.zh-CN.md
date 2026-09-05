# paper-critical-reading

[English](README.md)

在 Codex 或 Claude 的聊天中阅读、追问论文。默认只在聊天窗口回答；完整报告和**可以点击定位的原文引用**分别在用户显式要求时生成。点击引用后，本地阅读器打开保存的 PDF，滚动到原句，并逐行画框、高亮。继续追问时复用同一篇论文。

原有的第一性原理批判性精读框架仍然保留：不是让模型总结论文讲了什么，而是强制做结构化拆解——把问题形式化、说明以往方法在机制上为什么会失效、创新来自什么洞察（论文未明确说明的灵感标为"推测"）、实验是否真正支持论文的结论、分三层给出局限性分析，以及用第一性原理式追问反推作者可能是如何想到这个设计的。现在可以按具体问题聚焦回答，也可以按要求输出这套完整精读，见下文"完整精读结构"。

## 需要上传 PDF 吗？

**能够获取完整 PDF 的论文链接就够了。**

| 输入 | 处理方式 |
|---|---|
| 本地 PDF 路径 | 保存文件并提取文字与坐标 |
| arXiv 摘要、PDF、HTML 链接 | 自动解析到 PDF，保留显式版本号 |
| PDF 直链 | 下载后建立索引 |
| DOI 或出版社页面 | 跟随跳转并查找 PDF 元数据/链接，需要 PDF 可访问 |

需要登录、付费或依赖特殊网页交互时，可能需要自行下载后提供 PDF。暂不支持只有 HTML 的全文和自动 OCR。

PDF 根据内容生成 `paper_id`；后续问答复用该 ID。显式刷新或导入新版本时，新文件使用新 ID，旧引用仍然指向旧文件，避免升级版本后高亮错位。

## 由哪些部分组成？

| 部分 | 作用 |
|---|---|
| `en/` 或 `zh/` 技能 | 决定怎么读、怎么解释、怎么批判，以及如何使用证据 |
| `paper_reader/` 程序 | 下载/导入、提取字形坐标、检索、核验原句、提供 MCP 和 CLI |
| 本地阅读器 | 显示原始 PDF 页面、框选高亮、翻页、缩放和下载 |
| `tests/` | 检查定位、重复句子、版本缓存及实际 MCP 调用 |

不需要额外的模型 API key、向量数据库、前端构建或网站部署；继续使用聊天客户端里的模型。这套流程也不依赖 hook。

## 安装

需要 Python 3.10 及以上。以下命令适用于 macOS/Linux；Windows 使用 `py -m venv .venv`，并将可执行文件路径换成 `.venv\Scripts\python.exe`、`.venv\Scripts\paper-reader.exe`。

```bash
git clone https://github.com/liuyanliang666/paper-critical-reading.git
cd paper-critical-reading
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[mcp]'
```

**程序和技能都要安装。** 单独复制或上传技能文件，只会得到阅读指令，不会自动安装阅读器。MCP 使用官方 Python SDK 的 v1 接口并限制版本小于 v2。配置引用虚拟环境中 Python 的绝对路径，安装后请保留仓库和该环境。

### Claude Desktop

```bash
.venv/bin/paper-reader config --client claude-desktop
```

命令打印 MCP 配置片段。在 Claude Desktop 的 Developer 设置中编辑配置，将返回的 `paper-reader` 条目合并到已有 `mcpServers` 中，保留其他服务。重启客户端，确认论文工具已出现。命令本身不会修改客户端设置。参见[官方本地 MCP 配置说明](https://modelcontextprotocol.io/docs/develop/connect-local-servers)。

将 `zh/` 技能文件夹（包含 `SKILL.md` 和 `references/`）打包成 ZIP，通过 Claude 的自定义技能入口上传并启用；也可选择 `en/`。[官方技能使用说明](https://support.claude.com/en/articles/12512180-use-skills-in-claude)中的入口和可用性取决于客户端及账号。如果暂时没有自定义技能功能，仍可在聊天中明确要求使用这些 MCP 工具进行有依据的阅读。

### 本地 Codex 客户端

```bash
.venv/bin/paper-reader config --client codex
```

执行返回的 `codex mcp add paper-reader -- ...` 命令，再用 `codex mcp list` 检查。参见[Codex MCP 配置](https://developers.openai.com/codex/mcp)。

安装中文技能：

```bash
mkdir -p ~/.agents/skills/paper-critical-reading-zh
cp -R zh/. ~/.agents/skills/paper-critical-reading-zh/
```

英文版使用 `en/.` 和 `~/.agents/skills/paper-critical-reading/`。选择一个即可，两者都会跟随对话语言回答。[Codex 技能路径说明](https://developers.openai.com/codex/skills)。

Claude Code 可将相同技能目录复制到 `~/.claude/skills/` 下，以 frontmatter 中的 `name` 命名，并在其 MCP 设置中注册相同的 stdio 启动命令。

## 聊天时怎么用？

例如：

> 读一下 <https://arxiv.org/abs/1706.03762v7>。为什么这个模型需要位置信息？用中文解释，并附上简短原文和可点击定位的引用。

工具导入一次论文，随后技能检索并阅读上下文；上例明确要求引用，因此为准确原句创建引用。普通追问复用同一 `paper_id` 并在聊天中回答，不自动创建引用或完整报告；“后续都附引用”等明确持续要求仍有效。需要时可单独要求“给这个结论补上原文引用”，或“对这篇论文生成完整报告”。两种流程独立触发，报告默认也在聊天中输出，仅要求保存或导出时生成文件。

本地 PDF 需提供 MCP 服务进程可以访问的路径。聊天附件可能位于另一台机器或沙箱，不能自动当成本机文件使用。

## 不使用 MCP 也能运行

一个终端保持阅读器运行：

```bash
.venv/bin/paper-reader serve
```

另一个终端执行：

```bash
.venv/bin/paper-reader import /absolute/path/to/paper.pdf
.venv/bin/paper-reader search --paper PAPER_ID --query 'technical keywords'
.venv/bin/paper-reader read --paper PAPER_ID --page 3
.venv/bin/paper-reader cite --paper PAPER_ID --passage PASSAGE_ID --quote 'exact text from the read result'
```

将 ID、页码及原文替换为实际返回结果；打开引用结果里的 `url` 即可定位。分页读取时，用返回的 `next_start` 继续 `read --start N`。

`--data-dir` 和 `--port` 放在子命令前，例如 `paper-reader --port 8766 serve`。MCP、CLI 和阅读器必须使用相同数据目录与端口。修改后需要重新生成客户端配置。

## 定位的含义与边界

模型选择原文，程序核验文字并保存 PDF 身份、文本块 ID、页码及真实字形矩形。跨行句子按行分别画框；空白、连字和行末断词会规范化。编造或改写的文字会被拒绝，重复句子需要明确选择位置，不相邻的证据不能拼成一个引用。准确匹配只能证明文字位于哪里，不能代替对解释是否成立的判断。

| 链接 | 含义 |
|---|---|
| 引用 `url` | 精确原文片段及逐行框选 |
| `passage_url` | 整个文本块高亮 |
| `page_url` | 跳到指定页，适合图表等视觉依据，不承诺句子框选 |

页码按 PDF 内部从 1 开始计数，可能与印刷页码不同。章节导航使用 PDF 自带书签，无书签时不猜章节。

- 当前通过普通链接打开本地专用阅读器，通常由浏览器打开。**尚未实现 Codex/Claude 原生右栏嵌入或原生引用点击拦截**，阅读器也暂不允许 iframe 嵌入。
- 服务和点击链接的用户需在同一台机器。远端/云端沙箱的 `127.0.0.1` 不是你的电脑；云端接入需要另行设计可访问的服务和认证。
- MCP 进程自动启动阅读器；只用 CLI 则需保持 `serve` 运行。相同缓存和端口重启后，旧链接可继续使用。多个客户端共享阅读器时，关闭实际承载它的进程会停止服务；可重启客户端，或用独立的 `serve` 常驻。
- 页面以原始 PDF 渲染图显示，图中文字不可选择；引用栏中的文字可以复制，也可下载 PDF。扫描文字需要 OCR 后才能建立经过核验的文字引用，当前未集成 OCR。
- 特殊排版、公式、损坏文字层需要查看页面核查；检索是词汇匹配，不是跨语言语义搜索。
- 当前限制为 64 MiB、1,000 页。加密文件需先解锁。

PDF 和引用默认保存在 `~/.local/share/paper-critical-reading`，可通过 `XDG_DATA_HOME`、`PAPER_READER_DATA_DIR` 或 `--data-dir` 修改。阅读器只监听本机回环地址，链接含随机令牌。不会自动上传到另一个论文服务，但 **MCP 返回的文字和页面图像会交给当前聊天服务**。删除缓存会使相应引用失效；论文及缓存不会提交到仓库。

## 验证与维护

```bash
.venv/bin/python -m unittest discover -v
node --check paper_reader/web/reader.js
```

测试临时生成双栏、跨行、重复句子、断词和旋转页面，检查真实坐标、持久化、阅读器接口，以及实际 MCP 工具调用和图像输出。没有安装 MCP 依赖时，对应测试会跳过。Node 仅用于可选语法检查，运行阅读器不需要 Node。

这些测试不等于已验证每个桌面客户端的界面行为，也不能覆盖所有出版社的下载流程。

### 完整精读结构

完整精读仍包含以下部分：

| 部分 | 回答的问题 |
|---|---|
| TL;DR | 一句话概括方法、问题与结果 |
| 1. Task | 形式化输入输出空间、目标与评价指标 |
| 2. Challenge | 以往方法在机制上为什么会失效或有什么权衡 |
| 3. Method | 中性描述整个流程（不做评价） |
| 4. Insight & Novelty | 每个主要贡献的"问题→洞察→具体设计"对应关系；论文未明确说明的灵感标为**推测** |
| 5. Evidence & Validation | 实验/证明是否真正支持论文的结论，证据止步于何处 |
| 6. Potential Flaw | 三层局限：作者自陈的、批判性发现的、值得单独成文的研究机会 |
| 7. Motivation | 用第一性原理式的追问，重构作者可能是如何从问题走到这个设计的 |

未明确陈述的灵感和动机继续标为推测。多条重要判断现在可以分别附上原文证据，并遵守宿主的适用引用限制。

仓库源代码使用 [Apache-2.0](LICENSE)；单独安装的 PyMuPDF 依赖有自己的 [AGPL/商业许可](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright)。
