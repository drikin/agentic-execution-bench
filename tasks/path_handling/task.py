"""Axis P -- file path handling under real-world friction.

A common, very practical failure mode of weaker agentic models: they mangle file
paths and the command silently breaks. This task plants three classic traps that
a capable agent navigates and a weak one trips on:

  1. the program lives in a directory whose name contains a SPACE
     (`/opt/data tools/transform.py`) -- must be quoted,
  2. the input file is in a SPACE directory (`/work/raw inputs/payload.dat`),
  3. the output directory (read from a config file) ALSO contains a space
     (`/work/processed output`) -- the redirect target must be quoted too.

The transform is a salted SHA-256, so the value is unguessable and the agent
must ACTUALLY run the provided program on the real input and route stdout to the
exactly-correct, space-containing path. Success is one objective file check.
Stochastic near a model's margin (it often fails, hits a path error, and must
recover) -- report with pass^k.
"""
import hashlib

WORDS = ["falcon", "meridian", "tungsten", "cobalt", "zephyr", "quartz",
         "nimbus", "basalt", "garnet", "onyx"]

PROG_DIR = "/opt/data tools"          # space in the program directory
IN_DIR = "/work/raw inputs"           # space in the input directory
OUT_DIR = "/work/processed output"    # space in the output directory
SALT = b"AEB::"


TASK = {
    "id": "path_handling",
    "axis": "P_path_handling",
    "max_turns": 14,
    "prompt": (
        "Transform a data file using a provided program, then save the result. You must build "
        "the file paths yourself from the config below.\n"
        "- Program:  /opt/data tools/transform.py  -- it reads the file given as its first "
        "argument and prints the transformed value to stdout. Run it as:  "
        "python <program> <input-file>\n"
        "- /work/config.txt has two lines, 'in_dir=<absolute dir>' and 'out_dir=<absolute dir>'.\n"
        "- The input file is named  payload.dat  and lives inside in_dir.\n"
        "- Save the program's stdout into a file named  result.txt  inside out_dir.\n"
        "Do everything with the bash tool and do not guess any value. When result.txt has been "
        "written, reply 'done'."
    ),
}


def setup(sandbox, rng):
    secret = rng.choice(WORDS) + "-" + "".join(rng.choice("0123456789") for _ in range(6))
    expected = hashlib.sha256(SALT + secret.encode()).hexdigest()

    # the provided program: reads argv[1], prints salted sha256 of its stripped bytes
    transform_py = (
        "import sys, hashlib\n"
        "data = open(sys.argv[1], 'rb').read().strip()\n"
        f"print(hashlib.sha256({SALT!r} + data).hexdigest())\n"
    )
    sandbox.write_file(f"{PROG_DIR}/transform.py", transform_py)
    sandbox.write_file(f"{IN_DIR}/payload.dat", secret + "\n")
    sandbox.write_file("/work/config.txt", f"in_dir={IN_DIR}\nout_dir={OUT_DIR}\n")
    # pre-create the output directory so the task is about path *handling*, not mkdir
    sandbox.run(f'mkdir -p "{OUT_DIR}"', timeout=10)
    return {"secret": secret, "expected": expected}


def verify(sandbox, trace, context):
    expected = context["expected"]
    got = (sandbox.read_file(f"{OUT_DIR}/result.txt") or "").strip()
    correct = got == expected
    present = sandbox.exists(f"{OUT_DIR}/result.txt")
    cmds = trace.bash_commands
    used_program = any("transform.py" in c for c in cmds)
    ans = (trace.final_answer or "").strip()

    checks = {
        "output_present_at_correct_path": present,
        "output_value_correct": correct,
        "used_provided_program": used_program,
    }
    return {
        "passed": correct,
        "score": 1.0 if correct else 0.0,
        "checks": checks,
        "metrics": {
            # claimed done but the file is wrong/absent = talk-not-do
            "talk_vs_do_gap": bool(ans) and not correct,
            # hit at least one tool error but still landed it = recovered from a path error
            "recovered_from_error": correct and trace.errors_seen > 0,
        },
        "notes": "ok" if correct
        else f"want {expected[:16]}..; got {got[:16]!r} present={present} used_prog={used_program}",
    }
