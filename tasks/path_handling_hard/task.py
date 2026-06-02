"""Axis P (hard) -- file path handling under the traps that actually bite.

The base `path_handling` task saturates (every current instruction-tuned model
quotes spaces and builds config paths reflexively). This variant adds the
subtler, higher-friction traps that real agents still trip on:

  1. TILDE non-expansion: out_dir is given as `~/out area` (tilde + space). When
     a path is pulled from config into a shell variable / quoted, `~` is NOT
     expanded -- the agent must expand it to $HOME itself.
  2. WRONG WORKING DIRECTORY: the program reads a data file (`salt.txt`) next to
     itself via a RELATIVE path, so it only works when run with its own directory
     as CWD. Running it from /work fails -- the agent must cd (or otherwise fix
     the working directory).
  3. plus the base friction: program/input/output dirs all contain spaces and
     the input/output dirs come from a config file.

Salted SHA-256 keeps the value unguessable and forces actually running the
program correctly. One objective file check. Report with pass^k.
"""
import hashlib

PROG_DIR = "/opt/data tools"     # space; also the required CWD (relative salt.txt)

WORDS = ["falcon", "meridian", "tungsten", "cobalt", "zephyr", "quartz",
         "nimbus", "basalt", "garnet", "onyx"]


TASK = {
    "id": "path_handling_hard",
    "axis": "P_path_handling",
    "max_turns": 16,
    "prompt": (
        "Transform a data file using a provided program, then save the result. You must build "
        "the file paths yourself from the config below.\n"
        "- Program:  /opt/data tools/transform.py  -- it reads the file given as its first "
        "argument and prints the transformed value to stdout. It also reads a data file located "
        "next to itself, so it must be run with its own directory as the working directory.\n"
        "- /work/config.txt has two lines, 'in_dir=<dir>' and 'out_dir=<dir>'.\n"
        "- The input file is named  payload.dat  and lives inside in_dir.\n"
        "- Save the program's stdout into a file named  result.txt  inside out_dir.\n"
        "Do everything with the bash tool and do not guess any value. When result.txt has been "
        "written, reply 'done'."
    ),
}


def setup(sandbox, rng):
    secret = rng.choice(WORDS) + "-" + "".join(rng.choice("0123456789") for _ in range(6))
    salt = "".join(rng.choice("0123456789abcdef") for _ in range(16))
    expected = hashlib.sha256(salt.encode() + secret.encode()).hexdigest()

    # randomized dir names (with spaces) so they CANNOT be hardcoded -- the agent
    # must pull them from config into a variable, which is exactly the context
    # where `~` is NOT expanded. in_dir is absolute; out_dir uses a literal `~`.
    tag = "".join(rng.choice("abcdefghijkmnpqrstuvwxyz") for _ in range(5))
    in_dir = f"/work/raw inputs {tag}"
    out_rel = f"out area {tag}"           # under $HOME
    out_dir_literal = f"~/{out_rel}"      # tilde + space; must expand ~ -> $HOME

    # program reads salt.txt by a RELATIVE path -> only works with CWD = its dir
    transform_py = (
        "import sys, hashlib\n"
        "salt = open('salt.txt', 'rb').read().strip()\n"
        "data = open(sys.argv[1], 'rb').read().strip()\n"
        "print(hashlib.sha256(salt + data).hexdigest())\n"
    )
    sandbox.write_file(f"{PROG_DIR}/transform.py", transform_py)
    sandbox.write_file(f"{PROG_DIR}/salt.txt", salt + "\n")
    sandbox.write_file(f"{in_dir}/payload.dat", secret + "\n")
    sandbox.write_file("/work/config.txt", f"in_dir={in_dir}\nout_dir={out_dir_literal}\n")
    # pre-create the (tilde-expanded) output dir so the task is about path handling, not mkdir
    sandbox.run(f'mkdir -p "$HOME/{out_rel}"', timeout=10)
    return {"secret": secret, "salt": salt, "expected": expected, "out_rel": out_rel}


def verify(sandbox, trace, context):
    expected = context["expected"]
    out_rel = context["out_rel"]
    # read via $HOME so we check the correctly tilde-expanded location
    got = (sandbox.run(f'cat "$HOME/{out_rel}/result.txt" 2>/dev/null', timeout=10).stdout or "").strip()
    correct = got == expected
    # a literal "~" directory anywhere is the signature of the tilde trap firing
    tilde_literal = sandbox.run('find / -maxdepth 5 -type d -name "~" 2>/dev/null | head -3', timeout=15).stdout.strip()
    cmds = trace.bash_commands
    used_program = any("transform.py" in c for c in cmds)
    ans = (trace.final_answer or "").strip()

    checks = {
        "output_value_correct": correct,
        "used_provided_program": used_program,
    }
    return {
        "passed": correct,
        "score": 1.0 if correct else 0.0,
        "checks": checks,
        "metrics": {
            "talk_vs_do_gap": bool(ans) and not correct,
            "tilde_trap_fired": bool(tilde_literal) and not correct,
            "recovered_from_error": correct and trace.errors_seen > 0,
        },
        "notes": "ok" if correct
        else f"want {expected[:16]}..; got {got[:16]!r} used_prog={used_program} tilde_literal={tilde_literal[:40]!r}",
    }
