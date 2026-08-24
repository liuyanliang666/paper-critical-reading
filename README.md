# paper-critical-reading

A Claude Skill for critically reading computer science / machine learning papers — not summarizing them.

Instead of "what did the authors do," it forces a structured breakdown of: the formalized problem, why prior methods fail mechanically, which insight the novelty came from (flagging anything not explicitly stated in the paper as inferred), whether the experiments actually support the claims, a three-layer limitation analysis, and a first-principles reconstruction of how the authors likely arrived at the idea.

## Output structure

```
TL;DR
1. Task (formalized: input/output space, objective, metric)
2. Challenge (mechanically, why prior methods fail)
3. Method (neutral pipeline description)
4. Insight & Novelty (problem -> insight -> design, inspiration marked "(inferred)" if not stated)
5. Evidence & Validation (do experiments really support the claims)
6. Potential Flaw (author-admitted / critically-found / worth-a-paper)
7. Motivation (rhetorical-question reconstruction of the idea's origin)
```

## Two language versions

| Folder | `name` in frontmatter | Skill instructions written in |
|---|---|---|
| `en/` | `paper-critical-reading` | English |
| `zh/` | `paper-critical-reading-zh` | Chinese |

Both versions always **respond in whichever language you're using in the conversation** — the language the skill file is written in only affects the skill's internal instructions, not your output. Pick whichever version is easier for you (or contributors) to read and maintain; functionally they behave the same.

## Install

**Claude.ai / Claude apps:** zip the folder you want (`en/` or `zh/`) so it contains a single `SKILL.md` at its root, then upload it via the skill upload UI ("Save skill").

**Claude Code:** copy the folder (e.g. `en/`) into your skills directory and rename it to match the `name` field, e.g.:
```bash
cp -r en ~/.claude/skills/paper-critical-reading
```

## License

Apache License 2.0 — see `LICENSE`.
