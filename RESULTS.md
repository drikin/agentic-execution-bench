# AEB Results

Reference results gathered on a 3-node DGX Spark cluster (local vLLM, NVFP4/INT4
quantized) plus a hosted anchor (Claude Sonnet 4.6). Raw per-run JSON is
git-ignored; this file is the curated, reproducible summary.

Score = **pass^k** (passes *every* one of k trials) unless noted. Higher is better.

## Core axes (A/B/C/G) — saturated for capable models

`read_secret`, `find_target`, `primes`, `stateful_files`, `error_recovery`,
`multi_error_chain`, `impossible_honesty`.

| Model | Trials (each task) | Result |
|---|---|---|
| gpt-5.5 *(hosted, reasoning)* | 3 | **full clear — all 9 tasks pass^k = 1.00**, incl. skill_discovery |
| claude-sonnet-4-6 | 20 | 7/7 tasks pass^k = 1.00 |
| gpt-4.1 *(hosted)* | 3 | 7/7 = 1.00 |
| Albond Qwen3.5-122B-A10B | 3 | 7/7 = 1.00 |
| Qwen3.6-35B-A3B | 20 | 7/7 = 1.00 |
| gemma4-26B-A4B | 10 | 7/7 = 1.00 (with the default scaffold) |

These tasks no longer discriminate among competent models — which is exactly why
the harness-direction finding and the skill-discovery axis below matter.

## Harness direction is real, large, and *not* always positive

The same model, same task (`stateful_files`), only the system prompt changes
(gemma4-26B-A4B, n=20):

| Scaffold | pass^k |
|---|---|
| bare (no scaffold) | 1.00 |
| "keep going / don't give up" | **0.50** |
| methodical "gather all data with tools, re-verify before answering" | 1.00 |

A well-meant "persevere" instruction *induced* over-confidence and haste. The
default scaffold was rewritten to the methodical wording. **"A harness always
helps" is false** — direction matters more than presence.

## Axis S — skill self-discovery (`skill_discovery`)

The first AEB task that does **not** saturate. A codec skill with a *random* key
is hidden outside the working directory; the agent must explore the filesystem,
read `SKILL.md`, and run the provided `decode.py` — the answer is impossible to
guess. Default scaffold, pass^k:

| Model | pass^k | n | Note |
|---|---|---|---|
| gpt-5.5 *(hosted, reasoning)* | **1.00** | 3 | converges in ~8.7 turns |
| claude-sonnet-4-6 | **1.00** | 5 | hosted anchor / ceiling |
| **Qwen3.6-27B dense** | **1.00** | 5 | local leader, Claude-class |
| DeepSeek V4 Flash | **1.00** | 3 | single-shot use; not for agent loops |
| Albond Qwen3.5-122B-A10B | 0.40 | 5 | over-commits to solving itself |
| Qwen3.6-35B-A3B | 0.20 | 20 | high variance (0.80 at n=5) |
| **gpt-4.1** *(hosted)* | 0.00 | 3 | aces all other 7 tasks; here explores but times out at 18 turns |
| Coder-Next | 0.00 | 10 | times out at 18 turns |
| MiniMax-M2.7-172B-A10B | 0.00 | 10 | uses tools but never explores |
| gemma4-26B-A4B | 0.00 | 20 | 2/20 fabricated an answer |
| Nemotron-120B | INVALID | 10 | crashed mid-inference (ConnectionError) |

**Pattern: dense > MoE for skill-pulling.** A 27B dense model ties the hosted
anchors and beats 122B/172B MoE models. Self-discovery tracks the depth of the
reasoning loop (active params / dense-ness), not total parameter count.

**It is not a local-vs-hosted gap — it is a reasoning-generation gap.** The
sharpest evidence is within one provider: `gpt-4.1` passes all seven core tasks
at 1.00 yet scores **0.00** here (explores, never converges, times out at 18
turns), while `gpt-5.5` — the reasoning-class successor — converges in ~8.7 turns
for a clean **1.00**, full-clearing every task in the suite. Same vendor, same
API; the difference is the reasoning loop. This is the one axis on which an
otherwise-perfect frontier model (gpt-4.1) can still score zero.

### Scaffold ablation on Axis S — discipline closes the gap

`--system` swaps the system prompt; everything else is held fixed (n=20 each):

| Model | default | V1 "persist" | V2 "capability-first" | V3 "search early & wide" |
|---|---|---|---|---|
| Qwen3.6-35B-A3B | 0.20 | 0.55 | **1.00** | 1.00 |
| gemma4-26B-A4B | 0.00 | — | **0.95** | 0.90 |

A single sentence — *"before you try to compute/derive/solve anything yourself,
first investigate thoroughly what already exists on the system"* (V2,
`tools/scaffold_v2_capability.txt`) — lifts a model that scores **0.00** to
**0.95**. Self-discovery is a *capability the prompt unlocks*, not one the prompt
confers: the same V2 leaves reasoning-shallow models (Coder-Next, MiniMax) near
zero. Discipline reveals latent ability; it cannot manufacture it.

### Regression check — applying V2 to the live agent is side-effect-free

gemma4-26B-A4B, n=10: with V2 the core A/B/C/G tasks stay 1.00 while
`skill_discovery` rises 0.00 → 0.90. The capability-first wording was adopted in
the production Hermes agent's persona file with no regression on the saturated
tasks.

## Axis P — file path handling (`path_handling`)

A practical failure mode of weaker agentic models: they mangle file paths and the
command silently breaks. The task plants three classic traps — the program, the
input, and the (config-supplied) output directory all live in directories whose
names contain a **space** — and requires running the provided program on the real
input and routing stdout to the exactly-correct, space-containing path. The
transform is a salted SHA-256, so the value can't be guessed; success is one
objective file check.

Validated deterministically (no model): a fully-quoted invocation passes; an
unquoted path or an unquoted redirect target (`> /work/processed output/...` →
*ambiguous redirect*) fails. So the verifier catches real path mistakes.

| Model | pass^k | n | Note |
|---|---|---|---|
| gpt-5.5 *(hosted, reasoning)* | 1.00 | 3 | clean, ~3 turns |
| Albond Qwen3.5-122B-A10B | 1.00 | 5 | |
| Qwen3.6-27B dense | 1.00 | 5 | |
| Qwen3.6-35B-A3B | 1.00 | 5 | |
| MiniMax-M2.7-172B-A10B | 1.00 | 5 | 7.8 turns — works harder, still lands it |
| Coder-Next | 1.00 | 5 | |
| gemma4-26B-A4B | 1.00 | 5 | |

**Honest negative result: at this difficulty, path handling is a *solved*,
saturated skill — it does not discriminate.** Every model swept scores 1.00,
*including* MiniMax and Coder-Next, which score **0.00** on skill self-discovery.
So the two are independent abilities: failing to *find* a tool is not the same as
failing to *handle a path*. Current instruction-tuned models — even ones that
collapse on self-discovery — quote spaces and build paths from config reflexively.
The hypothesized "weak models mangle paths" failure does not reproduce here. To
make Axis P a discriminator would need harder traps (tilde non-expansion,
relative paths from the wrong CWD, URL path joining) or much older/smaller models;
as-is it is a table-stakes check, like the saturated A/B/C/G core.

(This task did earn its keep in one way: it surfaced a framework bug — the
sandbox's own `write_file`/`read_file`/`exists` helpers did not shell-quote
paths, now fixed with `shlex.quote`.)

### Hard variant (`path_handling_hard`) — it *does* discriminate

Adding the two traps that actually bite turns Axis P back into a discriminator:

1. **tilde non-expansion** — the output dir comes from config as `~/out area <rnd>`
   (tilde + space + a *random* tag so it can't be hard-coded). Pulled into a shell
   variable, `~` is **not** expanded; the agent must resolve it to `$HOME` itself.
2. **wrong working directory** — the program reads a sibling file by a relative
   path, so it only works when run with its own directory as CWD.

| Model | pass^k | n | Note |
|---|---|---|---|
| Albond Qwen3.5-122B-A10B | **1.00** | 5 | handles `~`+CWD correctly (9.2 turns — works for it) |
| gemma4-26B-A4B | **0.80** | 5 | one trial **resolved `~` to `/work` instead of `$HOME`** and wrote the result to the wrong place |

The easy variant is 1.00 for both; the hard variant separates them. gemma4's
failure is the exact real-world bug the task targets — a model "knows" `~` is a
home shortcut but mis-resolves it under friction. (n=5 is a first signal; a
full multi-model sweep at n≥20 would tighten the ranking.)

### URL path joining (`url_path`)

The other half of "path handling": a tiny HTTP service runs *inside* the sandbox
(loopback works even with networking disabled) and serves a random secret at
exactly one correctly-joined path; the naive `base + resource` concatenation
drops the separating slash and 404s. The agent must build the URL from config
parts and fetch it (`curl`/`wget` are absent, so it uses Python's urllib).

| Model | pass^k | n | Note |
|---|---|---|---|
| gemma4-26B-A4B | 1.00 | 5 | reads config, joins with the slash, one-shot fetch |

Like simple filesystem paths, **simple URL joining saturates** — gemma4 builds
the right URL directly. The discriminating version would be the subtler join trap
(base with a trailing slash *and* resource with a leading slash, where both
`base+resource` → `//` and `urljoin` → dropped prefix fail, and only deliberate
slash-normalization works), mirroring `path_handling_hard`. Built and left as the
natural next step.

## Reproducing

```bash
python -m aeb run --base-url http://HOST:8000/v1 --model NAME \
  --trials 20 --tasks skill_discovery --system "$(cat tools/scaffold_v2_capability.txt)"
```

Warm the endpoint first — cold-start ReadTimeouts and `content=None` smoke
responses produce false 0.00s; re-measure warm. Models that emit reasoning in a
separate channel (Qwen thinking, MiniMax) can show empty smoke content while tool
calls still work.
