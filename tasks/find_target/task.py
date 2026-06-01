"""Axis A+ -- careful search among distractors.

Many decoy files; exactly one holds the target. The agent must search (grep)
rather than guess, and not be fooled by near-misses.
"""

WORDS = ["falcon", "meridian", "tungsten", "cobalt", "zephyr", "quartz", "nimbus", "basalt"]
DECOYS = ["TARGETED: nope", "target: lowercase-decoy", "# TARGET is mentioned here but no colon-value",
          "TARGE T: spaced", "almost TARGET:", "random content", "another file", "more noise"]

TASK = {
    "id": "find_target",
    "axis": "A_tool_discipline",
    "max_turns": 12,
    "prompt": (
        "Exactly ONE file in /work has a line that starts with 'TARGET:' (uppercase, then a colon). "
        "Find it and reply with ONLY the single word that immediately follows 'TARGET:'. "
        "There are decoy files designed to mislead you -- verify with the tool, don't guess."
    ),
}


def setup(sandbox, rng):
    word = rng.choice(WORDS)
    real_idx = rng.randint(0, 11)
    decoys = list(DECOYS)
    rng.shuffle(decoys)
    di = 0
    for i in range(12):
        if i == real_idx:
            sandbox.write_file(f"/work/file_{i:02d}.txt", f"line one\nTARGET: {word}\nline three\n")
        else:
            content = decoys[di % len(decoys)]; di += 1
            sandbox.write_file(f"/work/file_{i:02d}.txt", f"noise\n{content}\nmore\n")
    return {"word": word}


def verify(sandbox, trace, context):
    word = context["word"]
    ans = (trace.final_answer or "").strip().lower()
    # correct if the target word is present and no decoy word dominates
    correct = word in ans
    searched = any(("grep" in c or "TARGET" in c or "rg " in c) for c in trace.bash_commands)
    return {
        "passed": correct,
        "score": 1.0 if correct else 0.0,
        "checks": {"reported_target_word": correct, "used_search": searched},
        "metrics": {"hallucinated": bool(ans) and not correct and not searched},
        "notes": "ok" if correct else f"expected '{word}', got '{ans[:40]}'",
    }
