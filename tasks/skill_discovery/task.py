"""Axis S -- skill self-discovery / self-orchestration ("skill-pulling").

A capability (a "codec" skill: instructions + a random key + a decode script) is
planted on the system, away from /work. The task is ONLY solvable by
DISCOVERING it (exploring the filesystem), READING its instructions, and RUNNING
it -- the model is never told it exists or where. The decode key is random, so
the value cannot be guessed or reverse-engineered from memory: the agent must
actually find and use the skill.

This measures whether an agent proactively finds and uses available capabilities
(the skill-pulling ability) versus giving up, asking for setup, or fabricating.
It is the agentic skill that tends to degrade first under aggressive
quantization even when basic tool-calling still works, and it is stochastic near
a model's capability margin -- so report it with pass^k, not a single trial.
"""
import base64

WORDS = ["falcon", "meridian", "tungsten", "cobalt", "zephyr", "quartz",
         "nimbus", "basalt", "garnet", "onyx"]

SKILL_DIR = "/opt/toolkit/codec"


TASK = {
    "id": "skill_discovery",
    "axis": "S_skill_discovery",
    "max_turns": 18,
    "prompt": (
        "The file /work/encoded.txt holds a single value that has been obfuscated and is NOT "
        "human-readable. Report the ORIGINAL decoded value. You have a fresh Linux sandbox, and "
        "some useful tools may already be installed somewhere on this system -- look around, and "
        "if you find something that helps, use it. Do not guess: only state the value once you "
        "have actually decoded it."
    ),
}


def setup(sandbox, rng):
    secret = rng.choice(WORDS) + "-" + "".join(rng.choice("0123456789") for _ in range(4))
    key = bytes(rng.randint(1, 255) for _ in range(8))
    enc = bytes(b ^ key[i % len(key)] for i, b in enumerate(secret.encode()))

    # Plant the codec skill: random key + decode script + instructions.
    sandbox.write_file(f"{SKILL_DIR}/key.b64", base64.b64encode(key).decode() + "\n")
    decode_py = (
        "import base64, sys\n"
        f"key = base64.b64decode(open('{SKILL_DIR}/key.b64').read().strip())\n"
        "data = base64.b64decode(open(sys.argv[1]).read().strip())\n"
        "out = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))\n"
        "print(out.decode())\n"
    )
    sandbox.write_file(f"{SKILL_DIR}/decode.py", decode_py)
    skill_md = (
        "# codec toolkit\n\n"
        "Decodes values obfuscated with this toolkit (base64 of an XOR against the toolkit key).\n\n"
        "## Usage\n\n"
        f"    python {SKILL_DIR}/decode.py <path-to-encoded-file>\n\n"
        "Prints the original decoded value.\n"
    )
    sandbox.write_file(f"{SKILL_DIR}/SKILL.md", skill_md)

    sandbox.write_file("/work/encoded.txt", base64.b64encode(enc).decode() + "\n")
    return {"secret": secret}


def verify(sandbox, trace, context):
    secret = context["secret"]
    ans = (trace.final_answer or "").strip()
    correct = secret in ans
    cmds = trace.bash_commands
    explored = any(("ls " in c or "ls\n" in c or "find " in c or "grep" in c or "tree" in c) for c in cmds)
    found_skill = any(("SKILL.md" in c or "/opt/toolkit" in c or "toolkit" in c) for c in cmds)
    ran_decode = any("decode.py" in c for c in cmds)
    checks = {
        "reported_decoded_value": correct,
        "explored_filesystem": explored,
        "found_the_skill": found_skill,
        "used_the_skill_script": ran_decode,
    }
    return {
        "passed": correct,
        "score": 1.0 if correct else 0.0,
        "checks": checks,
        "metrics": {
            # confident answer without ever running the decoder = talk-not-do
            "talk_vs_do_gap": bool(ans) and not correct and not ran_decode,
            # answered without even finding the skill = fabrication
            "hallucinated": bool(ans) and not correct and not found_skill,
        },
        "notes": "ok" if correct
        else f"want '{secret}'; explored={explored} found={found_skill} ran={ran_decode} ans={ans[:40]!r}",
    }
