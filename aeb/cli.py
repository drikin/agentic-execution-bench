"""CLI: run the Agentic Execution Bench against any OpenAI-compatible model.

Example:
  python -m aeb run --base-url http://localhost:8000/v1 --model your-model --trials 3
"""
from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

from .bench import discover_tasks, load_task, run_one

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser(prog="aeb", description="Agentic Execution Bench")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--base-url", required=True, help="OpenAI-compatible base url, e.g. http://host:8000/v1")
    r.add_argument("--model", required=True)
    r.add_argument("--api-key", default="")
    r.add_argument("--trials", type=int, default=1, help="repeats per task (for pass^k reliability)")
    r.add_argument("--tasks", nargs="*", default=None, help="task ids (default: all)")
    r.add_argument("--tasks-root", default=str(ROOT / "tasks"))
    r.add_argument("--image", default="python:3.12-slim")
    r.add_argument("--system", default=None, help="override the agent system prompt (profile)")
    r.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.cmd == "run":
        return cmd_run(a)


def cmd_run(a):
    dirs = discover_tasks(Path(a.tasks_root))
    mods = [load_task(d) for d in dirs]
    if a.tasks:
        mods = [m for m in mods if m.TASK["id"] in a.tasks]
    results = []
    print(f"# Agentic Execution Bench | model={a.model} | tasks={[m.TASK['id'] for m in mods]} | trials={a.trials}\n")
    for m in mods:
        for t in range(a.trials):
            res = run_one(m, base_url=a.base_url, model=a.model, api_key=a.api_key,
                          system=a.system, trial=t, image=a.image)
            results.append(res)
            mark = "PASS" if res.get("passed") else "FAIL"
            extra = res.get("api_error") or res.get("error") or res.get("notes", "")
            print(f"  [{mark}] {res['task_id']:<16} trial{t} "
                  f"score={res.get('score',0):.2f} turns={res.get('turns','?')} "
                  f"tools={res.get('tool_calls','?')} {res.get('wall_time','?')}s  {extra[:50]}")

    summary = aggregate(results)
    out = a.out or str(ROOT / "results" / f"{a.model.replace('/','_')}_{int(time.time())}.json")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps({"model": a.model, "summary": summary, "results": results},
                                    ensure_ascii=False, indent=2))
    print("\n" + render_summary(a.model, summary))
    print(f"\nsaved: {out}")
    return 0


def aggregate(results):
    by_task = defaultdict(list)
    for r in results:
        by_task[r["task_id"]].append(r)
    tasks = {}
    for tid, rs in by_task.items():
        n = len(rs)
        passes = sum(1 for r in rs if r.get("passed"))
        tasks[tid] = {
            "axis": rs[0].get("axis", ""),
            "pass_rate": round(passes / n, 3),
            "pass_at_k": passes == n,           # passed every trial (reliability)
            "passes": passes, "trials": n,
            "mean_score": round(sum(r.get("score", 0) for r in rs) / n, 3),
            "talk_vs_do": sum(1 for r in rs if r.get("verifier_metrics", {}).get("talk_vs_do_gap")),
            "hallucinated": sum(1 for r in rs if r.get("verifier_metrics", {}).get("hallucinated")),
            "avg_turns": round(sum(r.get("turns", 0) for r in rs) / n, 1),
        }
    overall_pass = sum(t["pass_rate"] for t in tasks.values()) / max(len(tasks), 1)
    return {"agentic_execution_score": round(overall_pass, 3), "tasks": tasks}


def render_summary(model, s):
    lines = [f"=== {model} | Agentic Execution Score = {s['agentic_execution_score']:.2f} ==="]
    lines.append(f"{'task':<16}{'axis':<20}{'pass_rate':>10}{'pass^k':>8}{'talk/do':>9}{'turns':>7}")
    for tid, t in s["tasks"].items():
        lines.append(f"{tid:<16}{t['axis']:<20}{t['pass_rate']:>10.2f}{('Y' if t['pass_at_k'] else 'n'):>8}"
                     f"{t['talk_vs_do']:>9}{t['avg_turns']:>7}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
