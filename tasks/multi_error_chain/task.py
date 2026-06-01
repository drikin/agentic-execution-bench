"""Axis C+ -- cascading error recovery.

Two sequential bugs: a missing input file AND an undefined name. The agent must
recover from one, hit the next, recover again, and get the logic right. Weak
agents fix the first error then declare victory or spiral.
"""

BROKEN = '''\
def main():
    with open('/work/input.txt') as f:
        n = int(f.read().strip())
    result = n * MULTIPLIER  # MULTIPLIER is not defined
    with open('/work/out.txt', 'w') as f:
        f.write(str(result))

if __name__ == '__main__':
    main()
'''

TASK = {
    "id": "multi_error_chain",
    "axis": "C_error_recovery",
    "max_turns": 20,
    "prompt": (
        "/work/pipeline.py is broken in more than one way. Fix everything so that running "
        "`python3 /work/pipeline.py` writes the DOUBLED value of the input number to /work/out.txt. "
        "Use 21 as the input number, so /work/out.txt must end up containing exactly 42. "
        "Run it, hit each error, fix it, and keep going until it works. Then reply with the final value."
    ),
}


def setup(sandbox, rng):
    sandbox.write_file("/work/pipeline.py", BROKEN)
    return {}


def verify(sandbox, trace, context):
    out = (sandbox.read_file("/work/out.txt") or "").strip()
    correct = out == "42"
    # recovered from at least the two seeded failures
    recovered_chain = trace.errors_seen >= 2
    runs_clean = False
    if sandbox.exists("/work/pipeline.py"):
        r = sandbox.run("cd /work && python3 pipeline.py >/dev/null 2>&1 && cat out.txt", timeout=20)
        runs_clean = (r.exit_code == 0) and r.stdout.strip() == "42"
    checks = {
        "out_txt_is_42": correct,
        "pipeline_runs_clean_to_42": runs_clean,
        "recovered_from_multiple_errors": recovered_chain,
        "claimed_42": "42" in (trace.final_answer or ""),
    }
    passed = correct and runs_clean
    return {
        "passed": passed,
        "score": sum(checks.values()) / len(checks),
        "checks": checks,
        "metrics": {"talk_vs_do_gap": ("42" in (trace.final_answer or "")) and not correct},
        "notes": "ok" if passed else f"out={out!r}",
    }
