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

# Thin, neutral scaffold. Not task-specific hand-holding -- just the rules of the game.
DEFAULT_SYSTEM = (
    "You are an autonomous agent operating in a Linux sandbox. You have a `bash` tool. "
    "Actually perform the task by calling tools -- do not just describe what you would do. "
    "Inspect outputs, recover from errors by reading them and retrying, and keep going until "
    "the task is genuinely complete and verified. When (and only when) you are done, reply with "
    "a short final message stating the result. Never claim success you have not verified."
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


def _chat(base_url, model, messages, tools, api_key, extra_body):
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body = {"model": model, "messages": messages, "tools": tools,
            "tool_choice": "auto", "temperature": 0.3, "max_tokens": 2048}
    if extra_body:
        body.update(extra_body)
    r = requests.post(url, headers=headers, json=body, timeout=180)
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
