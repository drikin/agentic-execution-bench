# Roadmap

## Thesis
LLM intelligence ≠ one axis. (1) single-shot answer quality vs (2) **agentic
execution** — multi-step tool use, error recovery, persistence, no faking.
These don't correlate. AEB measures (2), objectively, for any model incl. local.

## Differentiators (the niche)
1. Local/edge-model-first (discriminate among small/quantized self-hosted models)
2. "Talk vs Do" as a first-class metric (claimed vs verified completion)
3. Harness-isolating (one thin scaffold; swap `--system` to quantify harness's ~30pt contribution)
4. pass^k reliability (passes *every* trial, not best-of)
5. Objective, randomized, hard-to-game verification (filesystem/state, not LLM judge)
6. Lightweight, self-contained Docker sandbox — runs anywhere

## Axes
A tool-discipline-vs-hallucination · B multi-step · C error-recovery ·
D persistence/completion · E honesty/self-report · F protocol stability ·
G limit-recognition/escalation · H long-horizon stability

## Phases
- [x] **P0** axes + verifier contract
- [x] **P1 (MVP)** runner + Docker sandbox + 3 objective-verified tasks (A/B/C) + first scores
- [ ] **P2** harness-isolation mode, pass^k, talk-vs-do reporting (partly in MVP)
- [ ] **P3** harder & discriminating tasks: forced multi-error chains, state-tracking,
      distractor tools, long-horizon (15-30 steps), ambiguity/escalation, anti-gaming
- [ ] **P4** GitHub public release: docs, leaderboard, contribution guide, held-out tasks (anti-contamination)
- [ ] **P5** community tasks + optional hosted leaderboard

## Open risks
benchmark crowding (lean on differentiators) · gaming (param-randomize + state checks)
· stochasticity (pass^k) · harness confound (turned into a feature) · scope creep (stay lightweight)

## Findings (first runs, gemma4 on local vLLM)
- gemma4 is a genuinely strong agentic executor (passes A/B/C incl. cascading
  recovery, distractors, limit-honesty) — small active params (4B MoE) ≠ weak agent.
- **Prompt wording dominates.** A "keep going until complete" scaffold *induced
  rushing/over-confidence*: gemma4 scored **45%** on the multi-file `stateful_files`
  task vs **100%** with a bare prompt, n=20. Rewording to "gather ALL data with
  the tool first, verify before answering" restored **100%** (and more, slower,
  methodical turns). The harness/prompt effect is real, large, and *direction-
  dependent* — more scaffolding is not automatically better. This is exactly why
  objective, statistically-powered, harness-isolating measurement is needed.
- Methodology notes: intermediate-difficulty tasks need many trials (pass^k, k≥20)
  to separate signal from variance; report per-task, not just an aggregate.
