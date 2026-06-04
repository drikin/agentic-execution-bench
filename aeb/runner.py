"""Minimal, harness-agnostic agent loop.

Talks to any OpenAI-compatible /v1/chat/completions endpoint with tool-calling,
executes tool calls in a DockerSandbox, and records the full trace. The point is
to measure the *model's* intrinsic agentic execution ability under a thin,
documented scaffold -- not a specific framework's cleverness.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import requests

from .sandbox import DockerSandbox

BASH_TOOL = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Run a bash command in the sandbox and get back stdout, stderr and exit code. Use it to inspect files, write code, run programs, and verify results.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The bash command to run."}
            },
            "required": ["command"],
        },
    },
}

# Thin, neutral scaffold -- just the rules of the game. NOTE: the exact wording matters a lot.
# An earlier "keep going until complete" phrasing measurably induced rushing/over-confidence
# (gemma4 stateful_files: 45% vs 100% here). This methodical "gather-all-then-verify" wording
# matched the bare-prompt ceiling. See PLAN.md "Findings".
DEFAULT_SYSTEM = (
    "You are an autonomous agent in a Linux sandbox with a `bash` tool. Solve the task by "
    "actually running commands; never compute answers from memory or partial data. Work "
    "methodically one step at a time: gather ALL information you need with the tool before "
    "drawing any conclusion. If a command fails, read the error and fix it. Before giving your "
    "final answer, re-run or re-read to VERIFY it is actually correct. Only then reply with a "
    "short final result."
)


@dataclass
class RunTrace:
    task_id: str
    model: str
    final_answer: str = ""
    turns: int = 0
    tool_calls: int = 0
    bash_commands: list = field(default_factory=list)
    errors_seen: int = 0          # tool calls that returned non-zero exit / timeout
    messages: list = field(default_factory=list)
    wall_time: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    stop_reason: str = ""
    api_error: str = ""


# Per-model API quirks discovered at runtime, so we adapt once and reuse.
# Keeps AEB working across "any OpenAI-compatible endpoint": local vLLM/Ollama
# take `max_tokens` + a custom temperature, while newer hosted models (gpt-5.x,
# o-series, ...) require `max_completion_tokens` and only the default temperature.
_MODEL_QUIRKS: dict[str, set[str]] = {}
_MAX_OUTPUT_TOKENS = 2048


def _build_body(model, messages, tools, quirks):
    body = {"model": model, "messages": messages, "tools": tools, "tool_choice": "auto"}
    if "use_max_completion_tokens" in quirks:
        body["max_completion_tokens"] = _MAX_OUTPUT_TOKENS
    else:
        body["max_tokens"] = _MAX_OUTPUT_TOKENS
    if "no_temperature" not in quirks:
        body["temperature"] = 0.3
    return body


def _adapt_quirks(resp_text, quirks):
    """Inspect a 400 body for unsupported-parameter errors and learn the fix.
    Returns True if a new adaptation was applied (so the caller should retry)."""
    t = (resp_text or "").lower()
    changed = False
    if ("max_completion_tokens" in t and "max_tokens" in t
            and "use_max_completion_tokens" not in quirks):
        quirks.add("use_max_completion_tokens"); changed = True
    if ("temperature" in t and "no_temperature" not in quirks
            and any(s in t for s in ("does not support", "only the default",
                                     "unsupported value", "is not supported",
                                     "only supports"))):
        quirks.add("no_temperature"); changed = True
    return changed


def _chat(base_url, model, messages, tools, api_key, extra_body):
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    quirks = _MODEL_QUIRKS.setdefault(model, set())
    r = None
    for _ in range(4):  # adapt to at most a couple of unsupported-param errors, then give up
        body = _build_body(model, messages, tools, quirks)
        if extra_body:
            body.update(extra_body)
        r = requests.post(url, headers=headers, json=body, timeout=600)
        if r.status_code == 400 and _adapt_quirks(r.text, quirks):
            continue  # learned a fix (e.g. max_tokens -> max_completion_tokens); retry
        break
    r.raise_for_status()
    return r.json()


def run_agent(task, sandbox: DockerSandbox, *, base_url: str, model: str,
              api_key: str = "", system: str | None = None, max_turns: int = 20,
              extra_body: dict | None = None) -> RunTrace:
    tr = RunTrace(task_id=task["id"], model=model)
    messages = [
        {"role": "system", "content": system or DEFAULT_SYSTEM},
        {"role": "user", "content": task["prompt"]},
    ]
    t0 = time.time()
    try:
        for _ in range(max_turns):
            tr.turns += 1
            resp = _chat(base_url, model, messages, [BASH_TOOL], api_key, extra_body)
            usage = resp.get("usage") or {}
            tr.prompt_tokens += usage.get("prompt_tokens", 0) or 0
            tr.completion_tokens += usage.get("completion_tokens", 0) or 0
            choice = resp["choices"][0]
            msg = choice["message"]
            messages.append(msg)
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                tr.final_answer = (msg.get("content") or msg.get("reasoning_content") or "").strip()
                tr.stop_reason = "final_answer"
                break
            for tc in tool_calls:
                tr.tool_calls += 1
                fn = tc.get("function", {})
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                cmd = args.get("command", "")
                tr.bash_commands.append(cmd)
                res = sandbox.run(cmd, timeout=30)
                if res.exit_code != 0:
                    tr.errors_seen += 1
                out = f"exit_code={res.exit_code}\n--- stdout ---\n{res.stdout[:4000]}\n--- stderr ---\n{res.stderr[:2000]}"
                messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
        else:
            tr.stop_reason = "max_turns"
    except Exception as e:  # network / API / malformed -- recorded as a run failure
        tr.api_error = f"{type(e).__name__}: {e}"
        tr.stop_reason = "error"
    tr.wall_time = round(time.time() - t0, 1)
    tr.messages = messages
    return tr
