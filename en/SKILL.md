---
name: paper-critical-reading
description: Do a first-principles critical reading of a computer science / machine learning paper and produce a structured analysis - formalize the problem, break down the method pipeline, separate insight from novelty (flagging anything speculative), check whether the experiments actually support the claims, layer the limitations, and reverse-engineer how the authors likely arrived at the idea. Trigger this whenever the user uploads a paper PDF, or says things like "分析/解读/精读这篇论文", "读一下这篇 paper", "analyze this paper", "critique this paper", "paper analysis" - even if they don't explicitly name this skill. Always read the full text before analyzing; never produce a generic summary based only on the abstract.
---

# Paper Critical Reading

## Core principle

Reading a paper isn't about restating "what the authors did." It's about answering three questions:

1. Under what conditions does this problem exist, and mechanically why couldn't prior methods solve it?
2. What real observation forced the authors toward their approach, and how does the specific design respond to that observation?
3. Do the paper's own experiments actually prove its core claims, and where are the weak points?

If the output just paraphrases the abstract or translates the method section, the task isn't done. Every claim in the analysis should be traceable to something specific in the paper - not generic filler like "the authors propose a novel method" or "experiments demonstrate significant improvement," which are not analysis on their own.

## Output language

Respond in the same language the user is using in the conversation, regardless of the language this skill file is written in. If the user writes in Chinese, output in Chinese; if in English, output in English; if the paper is in a third language but the conversation is in another, follow the conversation language.

## Prerequisite: read the full paper, not just the abstract

Before generating the analysis, actually extract the content of:

- The Method / Approach section's specific design
- The Experiments section's datasets, baselines, metrics, and ablations
- Limitations / Future Work (if explicitly stated in the paper)

If the source is a PDF, extract the full text first (see the pdf-reading skill for technique, if available) and confirm these sections were actually retrieved before analyzing. If the paper is too long, or is a scanned copy where text extraction fails for some sections, tell the user honestly which parts weren't readable and which parts of the analysis that weakens. Don't fabricate content for sections you couldn't read.

## Output template

ALWAYS use this exact structure (see "Adjustments for special paper types" below for exceptions):

```
## TL;DR
One sentence: what method solves what problem, with what result.

## 1. Task (formalized)
- Input space / output space
- Objective function (plain text notation, no LaTeX - e.g. "loss = sum((y_i - f(x_i))^2)")
- Evaluation metric(s)

## 2. Challenge
Where and mechanically why prior methods break down. Explain the actual mechanism, not just "prior methods perform poorly."

## 3. Method (neutral description, no evaluation yet)
What each step of the pipeline does, as a step list or pseudocode. This is the factual basis for the Insight/Novelty/Flaw sections that follow.

## 4. Insight & Novelty
For each novelty, use exactly this format:
[What problem it solves] -> [Which insight it's inspired by] -> [What was specifically designed, as concretely as possible]

Every insight must state what inspiration it came from. If the paper doesn't explicitly state the source of an inspiration, mark that line "(inferred)" - never present an AI-generated rationalization as if it were the paper's own stated motivation.

## 5. Evidence & Validation
- Do the main experiments actually support the core claims?
- Does each novelty have a dedicated ablation, or only an aggregate comparison?
- Any sign that dataset/baseline choices were selected favorably for the proposed method?

## 6. Potential Flaw
Keep these three layers separate:
- Limitations the authors themselves admit (explicitly stated in Limitations/Future Work)
- Limitations found through critical reading (not mentioned in the paper, but apparent from the method or experimental design)
- Which of these gaps is large enough to be worth a standalone paper, and why

## 7. Motivation
Reverse-engineer how the authors likely arrived at the idea, using rhetorical questions and first-principles reasoning from the nature of the problem - not "because it worked well," but something like: "the prior method fails under condition X, so what if we tried Y?"
```

## Hard constraints

- No LaTeX. All formulas in plain text notation (e.g. `sum`, `^2`, `->`).
- In Insight & Novelty: any inspiration not explicitly stated in the paper must be marked "(inferred)." Never dress up an AI-generated rationalization as the paper's own stated motivation.
- Don't reproduce large verbatim passages from the paper - even if the user uploaded it themselves. Paraphrase in your own words. If a direct quote is genuinely necessary, keep it under 15 words and use at most one quote in the entire analysis.
- Output only in the conversation - don't generate a file unless the user asks for one.
- Skip pleasantries and preambles. Go straight into the analysis - no "this paper is about..." framing before the template.

## Adjustments for special paper types

- **Theoretical / proof papers** (no experiments section): replace "Evidence & Validation" with a review of proof rigor - are the assumptions realistic, are edge cases quietly excluded?
- **Survey papers**: skip the single Task formalization; instead summarize how the survey categorizes the problem space. For Novelty, evaluate what's new about the survey's taxonomy or perspective, not a specific technical contribution.
- **Systems papers** (engineering-focused rather than algorithmic): go deeper on architecture and component interaction in the Method section. In Evidence, focus on whether performance/cost benchmarks were measured under realistic conditions rather than idealized micro-benchmarks.

## When to trigger

Use this workflow whenever any of the following holds, without waiting for the user to name this skill explicitly:

- The user uploads a paper PDF and asks for any form of explanation, analysis, summary, or close reading
- The user references "this paper," "this paper" in English, or similar, along with an attached file or link
