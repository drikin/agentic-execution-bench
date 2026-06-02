"""Reproducible, network-isolated Docker sandbox for agentic task execution.

The sandbox is the ground-truth environment: the agent acts on it through the
`bash` tool, and verifiers inspect its final state. Network is disabled by
default so tasks are fully self-contained and reproducible anywhere.
"""
from __future__ import annotations

import shlex
import subprocess
import uuid
from dataclasses import dataclass


@dataclass
class CmdResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool


class DockerSandbox:
    def __init__(self, image: str = "python:3.12-slim", workdir: str = "/work",
                 network: bool = False, mem: str = "1g", cpus: str = "2"):
        self.image = image
        self.workdir = workdir
        self.network = network
        self.mem = mem
        self.cpus = cpus
        self.name = f"aeb-{uuid.uuid4().hex[:10]}"
        self._started = False

    def start(self) -> None:
        args = [
            "docker", "run", "-d", "--name", self.name,
            "-w", self.workdir,
            "--memory", self.mem, "--cpus", self.cpus,
            "--pids-limit", "256",
        ]
        if not self.network:
            args += ["--network", "none"]
        args += [self.image, "sleep", "infinity"]
        subprocess.run(args, check=True, capture_output=True, text=True)
        self.run(f"mkdir -p {self.workdir}", timeout=10)
        self._started = True

    def run(self, command: str, timeout: int = 30) -> CmdResult:
        """Run a bash command inside the sandbox. Always returns a result."""
        try:
            p = subprocess.run(
                ["docker", "exec", self.name, "bash", "-lc", command],
                capture_output=True, text=True, errors="replace", timeout=timeout,
            )
            return CmdResult(p.stdout, p.stderr, p.returncode, False)
        except subprocess.TimeoutExpired as e:
            out = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            err = (e.stderr or b"").decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
            return CmdResult(out, err + f"\n[command timed out after {timeout}s]", 124, True)

    def write_file(self, path: str, content: str) -> None:
        """Seed a file into the sandbox (used by task setup, not the agent).

        The path is shell-quoted, so paths containing spaces or other shell
        metacharacters are handled correctly.
        """
        import base64
        b64 = base64.b64encode(content.encode()).decode()
        q = shlex.quote(path)
        self.run(f'mkdir -p "$(dirname {q})"; echo {b64} | base64 -d > {q}', timeout=15)

    def read_file(self, path: str) -> str | None:
        r = self.run(f"cat {shlex.quote(path)} 2>/dev/null", timeout=15)
        return r.stdout if r.exit_code == 0 else None

    def exists(self, path: str) -> bool:
        return self.run(f"test -e {shlex.quote(path)}", timeout=10).exit_code == 0

    def cleanup(self) -> None:
        if self._started:
            subprocess.run(["docker", "rm", "-f", self.name], capture_output=True, text=True)
            self._started = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.cleanup()
