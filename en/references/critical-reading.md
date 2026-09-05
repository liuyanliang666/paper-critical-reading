# Full critical-reading framework

Use this only for an explicitly requested full report or full critical review, after following SKILL.md's reading workflow. Run the citation workflow only if citations are also explicitly requested. Focused follow-ups should receive focused answers.

## Core questions

1. Under what conditions does the problem arise, and mechanically why do earlier approaches struggle?
2. What observation motivates this approach, and how does its design address it?
3. How strongly do experiments or proofs support its claims, and where does the evidence stop?

An abstract paraphrase is insufficient. Read all main-text sections and relevant appendices. If that is impossible, state actual coverage and narrow the review. Do not imply knowledge of prior literature you have not checked.

## Default structure

### TL;DR

One sentence connecting the method, problem, and observed result, with its main qualification if needed.

### 1. Task

Formalize inputs, outputs, objective, and metrics. Explain notation and the assumptions defining the task. Use formulas when they improve understanding.

### 2. Challenge

Explain where previous approaches fail or face a tradeoff, and why. Distinguish the paper's description of prior work from independently verified comparisons.

### 3. Method

Describe the pipeline neutrally as steps or pseudocode. Explain information flow, training versus inference, objectives, and relevant implementation choices before evaluating them.

### 4. Insight & Novelty

Connect **problem → insight → concrete design** for each main contribution. Identify inspiration explicitly stated by the authors; otherwise mark the proposed inspiration **inferred**. Separate a useful insight from historical novelty, which may need additional literature.

### 5. Evidence & Validation

Examine datasets, splits, baselines, metrics, uncertainty, compute budgets, and ablations where relevant. Distinguish aggregate improvement from evidence for a particular component. Base the analysis on actual setups and results, not merely the abstract's interpretation; create citations for that evidence when requested. Describe concrete comparison weaknesses without speculating about intent.

### 6. Potential Flaw

Keep three levels explicit:

- Limitations the authors state, grounded in the corresponding text; add evidence links when requested.
- Limitations you identify from specific designs, results, or assumptions, labelled as your analysis.
- Research opportunities suggested by those gaps, with what further evidence would establish their value. Do not force every limitation into a standalone-paper claim.

### 7. Motivation

Reconstruct a plausible path from the problem to the design using first-principles questions where helpful. This is a reasoning exercise, not a historical account. Mark unstated causal or motivational claims **inferred**.

## Adapt to the paper

- **Theory/proof:** Review assumptions, proof steps, edge cases, and the scope of the result instead of experimental validation.
- **Survey:** Explain taxonomy and coverage instead of forcing a single task or method. Evaluate its organizing perspective and omissions.
- **Systems:** Detail architecture and component interactions. Check realistic workloads, resource costs, failures, and deployment conditions.

Only when citations are requested, place verified source links near the claims they support. Distinguish exact sentence citations, whole-passage links, and page-level visual evidence.
