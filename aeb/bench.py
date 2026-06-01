"""Load tasks and run one (sandbox -> setup -> agent -> verify -> result)."""
from __future__ import annotations

import importlib.util
import random
from pathlib import Path

from .runner import run_agent
from .sandbox import DockerSandbox


def load_task(task_dir: Path):
    spec = importlib.util.spec_from_file_location(f"aeb_task_{task_dir.name}", task_dir / "task.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def discover_tasks(tasks_root: Path):
    return sorted(p for p in tasks_root.iterdir() if (p / "task.py").exists())


def run_one(task_mod, *, base_url: str, model: str, api_key: str = "",
            system: str | None = None, trial: int = 0, image: str = "python:3.12-slim",
            extra_body: dict | None = None) -> dict:
    task = dict(task_mod.TASK)
    rng = random.Random(f"{task['id']}-{trial}")
    sb = DockerSandbox(image=image)
    result = {"task_id": task["id"], "axis": task.get("axis", ""), "trial": trial, "model": model}
    try:
        sb.start()
        context = task_mod.setup(sb, rng) if hasattr(task_mod, "setup") else {}
        trace = run_agent(task, sb, base_url=base_url, model=model, api_key=api_key,
                          system=system, max_turns=task.get("max_turns", 16), extra_body=extra_body)
        verdict = task_mod.verify(sb, trace, context)
        result.update({
            "passed": verdict["passed"],
            "score": round(verdict.get("score", float(verdict["passed"])), 3),
            "checks": verdict.get("checks", {}),
            "verifier_metrics": verdict.get("metrics", {}),
            "notes": verdict.get("notes", ""),
            "turns": trace.turns,
            "tool_calls": trace.tool_calls,
            "errors_seen": trace.errors_seen,
            "wall_time": trace.wall_time,
            "tokens": trace.prompt_tokens + trace.completion_tokens,
            "stop_reason": trace.stop_reason,
            "api_error": trace.api_error,
            "final_answer": (trace.final_answer or "")[:400],
        })
    except Exception as e:
        result.update({"passed": False, "score": 0.0, "error": f"{type(e).__name__}: {e}"})
    finally:
        sb.cleanup()
    return result
