"""Axis B/H -- multi-file state tracking over a longer horizon.

Read N files, aggregate, AND produce a conditional derived output. Weak agents
miscount, skip files, or lose the conditional sub-task.
"""

TASK = {
    "id": "stateful_files",
    "axis": "B_multi_step",
    "max_turns": 24,
    "prompt": (
        "Directory /work/data contains several .txt files, each holding a single integer. "
        "1) Write /work/total.txt containing the SUM of all those integers. "
        "2) Write /work/evens.txt listing the filenames (just the base name like f3.txt) whose "
        "integer is EVEN, one per line, sorted alphabetically. "
        "Then reply with: 'sum=N, even_count=M'. Do everything with the tool."
    ),
}


def setup(sandbox, rng):
    n = 6
    nums = {f"f{i}.txt": rng.randint(1, 99) for i in range(1, n + 1)}
    for name, v in nums.items():
        sandbox.write_file(f"/work/data/{name}", f"{v}\n")
    total = sum(nums.values())
    evens = sorted(name for name, v in nums.items() if v % 2 == 0)
    return {"total": total, "evens": evens}


def verify(sandbox, trace, context):
    total = context["total"]
    evens = context["evens"]
    got_total = (sandbox.read_file("/work/total.txt") or "").strip()
    total_ok = got_total == str(total)
    got_evens = [l.strip() for l in (sandbox.read_file("/work/evens.txt") or "").splitlines() if l.strip()]
    evens_ok = sorted(got_evens) == evens
    ans = trace.final_answer or ""
    claimed_ok = f"sum={total}" in ans.replace(" ", "")
    checks = {
        "total_txt_correct": total_ok,
        "evens_txt_correct": evens_ok,
        "final_answer_states_sum": claimed_ok,
    }
    passed = total_ok and evens_ok
    return {
        "passed": passed,
        "score": sum(checks.values()) / len(checks),
        "checks": checks,
        "metrics": {"talk_vs_do_gap": claimed_ok and not total_ok},
        "notes": "ok" if passed else f"want sum={total} evens={evens}; got total={got_total!r} evens={got_evens}",
    }
