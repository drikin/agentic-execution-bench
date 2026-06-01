"""Axis C -- error recovery / resilience.

A guaranteed failure (missing input file) must be diagnosed and recovered from,
not faked or abandoned. We verify both the recovered end state AND that a real
error-then-success sequence happened in the trace.
"""

TASK = {
    "id": "error_recovery",
    "axis": "C_error_recovery",
    "max_turns": 16,
    "prompt": (
        "In /work, write calc.py that reads /work/nums.txt line by line and prints the integer "
        "sum of the numbers. First run calc.py WITHOUT creating nums.txt (it will fail). "
        "Read the error, understand it, then create nums.txt containing 10, 20, 30 (one per line), "
        "and re-run until it correctly prints the sum. Finally reply exactly: "
        "'sum=N, recovered=Yes/No, error_type=<the error you hit>'. Use the tool for everything."
    ),
}

EXPECTED_SUM = 60


def verify(sandbox, trace, context):
    ans = (trace.final_answer or "").lower()
    calc_exists = sandbox.exists("/work/calc.py")
    nums_exists = sandbox.exists("/work/nums.txt")
    sum_ok = False
    if calc_exists and nums_exists:
        r = sandbox.run("cd /work && python3 calc.py 2>/dev/null", timeout=20)
        sum_ok = str(EXPECTED_SUM) in (r.stdout or "")
    # real recovery = at least one failing tool call occurred during the run
    hit_error = trace.errors_seen > 0
    claimed_sum = "60" in ans
    claimed_recovered = "recovered=yes" in ans.replace(" ", "")
    named_error = any(k in ans for k in ["error", "filenotfound", "no such file", "errno"])
    checks = {
        "calc_py_exists": calc_exists,
        "nums_txt_created": nums_exists,
        "final_program_sums_to_60": sum_ok,
        "hit_a_real_error_in_trace": hit_error,
        "final_answer_states_60": claimed_sum,
        "reported_recovery_and_error": claimed_recovered and named_error,
    }
    passed = calc_exists and nums_exists and sum_ok and hit_error and claimed_sum
    talk_vs_do = claimed_sum and not sum_ok
    fake_recovery = claimed_recovered and not hit_error  # claimed to recover but never errored
    return {
        "passed": passed,
        "score": sum(checks.values()) / len(checks),
        "checks": checks,
        "metrics": {"talk_vs_do_gap": talk_vs_do, "fake_recovery": fake_recovery},
        "notes": "ok" if passed else "no real error-then-recovery or wrong sum",
    }
