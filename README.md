# Agentic Execution Bench (AEB)

*[日本語版 README は `README.ja.md`](README.ja.md)*

**LLM intelligence is not one number.** A model can be brilliant at single-shot
answers yet fall apart the moment it has to *act* — call a tool, read the result,
recover from an error, and see a multi-step task through to the end. AEB measures
that second kind of intelligence: **agentic execution — the ability to grind a
task to completion without faking it.**

It is deliberately **lightweight, self-contained, and harness-agnostic**: every
task runs in a throwaway, network-isolated Docker sandbox, success is checked by
**objective machine verification of the final state** (not an LLM judge), and it
runs against **any OpenAI-compatible endpoint** — local vLLM/Ollama or a hosted
API. You can benchmark the small/quantized models you actually self-host on a
laptop.

## Why another benchmark?

The "agentic execution matters" thesis is well established (Terminal-Bench,
τ-bench, GAIA all show frontier models cratering when moving from one-shot to
multi-step). AEB's niche is the under-served angle:

- **Local/edge-model-first** — discriminate among the small, quantized, self-hosted models, where the gap is widest and most practical.
- **"Talk vs Do" is a first-class metric** — we separately track *claimed* success from *verified* success, catching the "I did it!" hallucination (口だけ) that wrecks real agents.
- **Harness-isolating** — the harness is known to add ~30 points (bigger than most model-generation gaps). AEB uses one thin, documented scaffold so you measure the *model*, and can swap the system prompt (`--system`) to quantify harness contribution.
- **pass^k reliability** — repeat each task; report whether it passes *every* time, not best-of.
- **Objective scoring** — randomized, unguessable ground truth + filesystem/output verification. Hard to game, easy to reproduce.

## What it measures (axes)

| Axis | Question | Tasks |
|---|---|---|
| A. Tool discipline vs hallucination | Does it use a tool for data it can't know, or fabricate? | `read_secret`, `find_target` |
| B. Multi-step planning & execution | Chain tool calls, use outputs, track state, self cross-check | `primes`, `stateful_files` |
| C. Error recovery / resilience | Diagnose a failure, fix it, retry — not spiral or fake | `error_recovery`, `multi_error_chain` |
| G. Limit-recognition / honesty | Admit an impossible task instead of faking a result | `impossible_honesty` |
| S. Skill self-discovery | Find and use a hidden skill instead of solving by hand | `skill_discovery` |

Axis S is the first task that does **not** saturate among competent models: a
codec skill with a *random* key is hidden outside the working directory, so the
answer is impossible to guess and the model must explore, read the skill doc, and
run it. See [`RESULTS.md`](RESULTS.md) for the leaderboard and the
scaffold-ablation study (a single capability-first sentence lifts a 0.00 model to
0.95).

Planned: protocol stability, escalation, long-horizon (15–30 step) stability.

## Sample results (our local run)

From a 3-node DGX Spark cluster (local vLLM, NVFP4/INT4-quantized) plus a hosted
anchor. Score = **pass^k** (passes *every* one of k trials). Full tables and
methodology in [`RESULTS.md`](RESULTS.md).

**Axis S — skill self-discovery (default scaffold):**

| Model | pass^k | n |
|---|---|---|
| claude-sonnet-4-6 *(hosted anchor)* | **1.00** | 5 |
| **Qwen3.6-27B dense** *(local leader)* | **1.00** | 5 |
| Albond Qwen3.5-122B-A10B | 0.40 | 5 |
| Qwen3.6-35B-A3B | 0.20 | 20 |
| MiniMax-M2.7-172B-A10B | 0.00 | 10 |
| gemma4-26B-A4B | 0.00 | 20 |

Skill-pulling tracks the **depth of the reasoning loop (dense-ness / active
params), not total size** — a 27B dense model ties the anchor and beats 122B/172B
MoE. Core axes A/B/C/G are already saturated (≈1.00) for all of these.

**Harness direction is real and not always positive** — same model, same task,
only the system prompt changes:

| | gemma4 `stateful_files` (n=20) | gemma4 `skill_discovery` (n=20) |
|---|---|---|
| bare / default | 1.00 | 0.00 |
| "keep going, don't give up" | **0.50** | — |
| capability-first ("search for an existing tool before solving") | 1.00 | **0.95** |

A single capability-first sentence lifts a 0.00 model to 0.95; the same sentence
*hurts* nothing and a naive "persevere" prompt *induces* over-confidence. This is
why AEB isolates the harness with `--system`.

➡️ **Want to apply this to your own agent?** [`PROMPTING.md`](PROMPTING.md) has
the exact lines (EN + JA) to drop into a `SOUL.md`/system prompt to raise
execution ability — including the one we shipped into a live agent — plus the
anti-pattern to avoid.

## Quick start

```bash
pip install -r requirements.txt   # just `requests`; Docker must be installed
python -m aeb run \
  --base-url http://localhost:8000/v1 \
  --model your-model \
  --trials 3
```

Output: a per-task PASS/FAIL table, a composite **Agentic Execution Score**,
pass^k, talk-vs-do counts, and a results JSON under `results/`.

## How it works

```
[runner: thin agent loop, OpenAI tool-calling]  <->  [your model endpoint]
        | bash tool calls
[Docker sandbox: isolated, no network]
        | after the run
[verifier: objective check of final state]  ->  score + metrics
```

Each task lives in `tasks/<id>/task.py` as a `TASK` dict plus optional `setup()`
(seeds randomized ground truth) and `verify()` (inspects the sandbox's final
state and the run trace). Adding a task = adding one file.

## Status

8 tasks across 5 axes (A/B/C/G/S), thin runner, network-isolated Docker sandbox,
objective verifiers, `--system` harness ablation, and a reference leaderboard in
[`RESULTS.md`](RESULTS.md). Roadmap in [`PLAN.md`](PLAN.md). Contributions of
tasks and model results welcome.

## License

MIT.
