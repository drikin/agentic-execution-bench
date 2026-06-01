"""Axis B -- multi-step planning & execution (with self cross-check).

Must write code, run it, independently cross-check the result, compare, report.
Objective ground truth: there are exactly 25 primes in [1, 100].
"""

TASK = {
    "id": "primes",
    "axis": "B_multi_step",
    "max_turns": 16,
    "prompt": (
        "In /work, write a Python file primes.py whose function returns the list of primes "
        "from 1 to 100, and which prints the COUNT of those primes when run. Run it. "
        "Then INDEPENDENTLY cross-check that count with a different one-liner (python or awk). "
        "Finally reply with exactly: 'count=N, crosscheck_match=Yes/No'. Do all of this with the tool."
    ),
}

EXPECTED = 25


def verify(sandbox, trace, context):
    ans = (trace.final_answer or "").lower()
    file_exists = sandbox.exists("/work/primes.py")
    # re-run the produced program to verify it genuinely yields 25
    produces_25 = False
    if file_exists:
        r = sandbox.run("cd /work && python3 primes.py 2>/dev/null", timeout=20)
        produces_25 = str(EXPECTED) in (r.stdout or "")
    claimed_25 = "25" in ans
    mentioned_crosscheck = "crosscheck_match" in ans or "yes" in ans
    checks = {
        "primes_py_exists": file_exists,
        "program_outputs_25": produces_25,
        "final_answer_states_25": claimed_25,
        "reported_crosscheck": mentioned_crosscheck,
    }
    passed = file_exists and produces_25 and claimed_25
    # talk-vs-do: claimed the right number but the program doesn't actually produce it
    talk_vs_do = claimed_25 and not produces_25
    return {
        "passed": passed,
        "score": sum(checks.values()) / len(checks),
        "checks": checks,
        "metrics": {"talk_vs_do_gap": talk_vs_do},
        "notes": "ok" if passed else "missing real execution or wrong count",
    }
