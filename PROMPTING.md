# Prompting recipes — make your agent actually execute

AEB doesn't just *score* agents; it tells you **what to write in your agent's
system prompt / persona file** (e.g. a `SOUL.md`) to raise its execution
ability. Everything below is backed by `--system` ablation runs — see
[`RESULTS.md`](RESULTS.md) for the numbers.

The headline finding: **the single highest-leverage line you can add is a
"capability-first" instruction** — *look for an existing tool/skill/script before
you try to solve it yourself*. On our local models, one sentence took
`skill_discovery` from **0.00 → 0.95** (gemma4-26B) and **0.20 → 1.00**
(Qwen3.6-35B), with **no regression** on the already-saturated tasks.

---

## 1. The capability-first line (highest leverage)

This is the winner. Drop it near the top of your agent's behavioral rules.

**English (verbatim from `tools/scaffold_v2_capability.txt`):**

> Before you try to compute, derive, or solve anything yourself, FIRST
> investigate thoroughly what already exists on the system that could do it for
> you — search the whole filesystem (not just the obvious working directory) for
> relevant tools, scripts, data, or instructions, and read any instructions you
> find and follow them. Only fall back to solving it manually after you have
> genuinely confirmed nothing useful exists.

**Japanese (the line we actually shipped into a live Hermes agent's `SOUL.md`):**

> まず道具を探してから自力に頼る。自分で計算・推論・解決しようとする前に、それを
> やってくれる道具・スキル・スクリプトが既に無いか、作業場所だけでなく広く探す。
> 見つけたら手順に従い、本当に何も無いと確認できて初めて自力でやる。一度で
> 見つからなくても諦めず、効かない手は早めに見切って別の場所・別の方法に手を
> 変えて掘り続ける。

Why it works: the dominant failure mode of mid-size local models on agentic
tasks is **over-committing to solving the problem from their own knowledge** and
never discovering the tool/skill that trivializes it. This line redirects the
very first move from "answer" to "investigate."

## 2. The default execution discipline (gather-then-verify)

Use this as your baseline agent scaffold for multi-step work. It keeps a model
from declaring victory early.

> Actually DO the work — never say you will do something without doing it in the
> same turn, and never give a final answer you have not verified by running the
> tool. Gather all the data you need with tools first; re-check it before you
> answer.

In our runs this lifted gemma4-26B's `stateful_files` from **0.50 back to 1.00**
(see the anti-pattern below for how it got to 0.50 in the first place).

## 3. Anti-pattern: don't just say "keep going / never give up"

This is the counter-intuitive result. A naive perseverance prompt can **hurt**:

| gemma4-26B, `stateful_files` (n=20) | pass^k |
|---|---|
| bare / no scaffold | 1.00 |
| **"be relentless, don't give up, keep going"** | **0.50** |
| methodical gather-then-verify | 1.00 |

A pure "push harder" instruction induced **over-confidence and haste** — the
model rushed and stopped tracking state correctly. "Persevere" is only safe when
it's paired with *direction* (where to look, when to switch approaches), which is
why the capability-first and broad-search framings work where bare "keep going"
backfires. The full persistence/broad variants we tested are in
`tools/persistence_scaffold.txt` and `tools/scaffold_v3_broad.txt`.

## 4. Discipline unlocks ability — it can't manufacture it

The same capability-first line that takes gemma4 to 0.95 leaves
reasoning-shallow models (a coder-tuned model, a thin-active-param MoE) near
**0.00**. The prompt reveals latent ability in a model that has it; it does not
add ability that isn't there. So:

- If a good prompt suddenly "wakes up" a model → it had the capability; keep the line.
- If it doesn't move the needle → that model is the wrong delegate for agentic work; pick a different one rather than prompt-engineering harder.

## How to verify on *your* model

Don't trust these numbers on a model you haven't tested — measure it:

```bash
# baseline
python -m aeb run --base-url http://localhost:8000/v1 --model your-model \
  --trials 20 --tasks skill_discovery

# with the capability-first line
python -m aeb run --base-url http://localhost:8000/v1 --model your-model \
  --trials 20 --tasks skill_discovery \
  --system "$(cat tools/scaffold_v2_capability.txt)"
```

If `--system` moves the score, that delta is exactly what adding the line to your
agent's `SOUL.md` will buy you.
