"""Axis P (URL) -- URL path construction.

The filesystem path tasks cover local paths; this one covers the other half the
failure mode shows up in: joining a base URL and a resource path into a
well-formed URL. A tiny HTTP service runs inside the sandbox (loopback works even
with networking disabled) and serves a random secret at EXACTLY one correctly
joined path; every other path -- including the naive `base + resource`
concatenation that drops the separating slash -- returns 404. The secret is
random and only reachable via the correct URL, so the agent must build the URL
right and actually fetch it.

`curl`/`wget` are absent in the slim image, so the prompt directs the agent to
Python's urllib -- keeping the test about URL construction, not tool availability.
Report with pass^k.
"""

WORDS = ["falcon", "meridian", "tungsten", "cobalt", "zephyr", "quartz",
         "nimbus", "basalt", "garnet", "onyx"]
PORT = 8080


TASK = {
    "id": "url_path",
    "axis": "P_path_handling",
    "max_turns": 14,
    "prompt": (
        "A local HTTP service holds a secret value. Build the request URL from the parts in "
        "/work/config.txt, fetch it, and report the secret.\n"
        "- /work/config.txt has two lines: 'base=<...>' and 'resource=<...>'. The request URL is "
        "the base and the resource combined into one well-formed URL.\n"
        "- GET that URL; the response body is the secret. A wrong URL returns HTTP 404.\n"
        "- `curl` and `wget` are NOT installed; use Python's urllib (e.g. "
        "`python3 -c \"import urllib.request,sys; print(urllib.request.urlopen(sys.argv[1]).read().decode())\" <URL>`).\n"
        "Reply with the EXACT secret as your final answer. Do everything with the bash tool and "
        "do not guess."
    ),
}


def setup(sandbox, rng):
    secret = rng.choice(WORDS) + "-" + "".join(rng.choice("0123456789") for _ in range(6))
    rid = "".join(rng.choice("0123456789") for _ in range(5))
    correct_path = f"/api/v2/items/{rid}/value"

    # server: serves the secret ONLY at the exactly-correct path, 404 elsewhere
    server_py = (
        "import http.server, socketserver\n"
        f"SECRET = {secret!r}\n"
        f"PATH = {correct_path!r}\n"
        "class H(http.server.BaseHTTPRequestHandler):\n"
        "    def do_GET(self):\n"
        "        if self.path == PATH:\n"
        "            self.send_response(200); self.end_headers(); self.wfile.write(SECRET.encode())\n"
        "        else:\n"
        "            self.send_response(404); self.end_headers(); self.wfile.write(b'not found')\n"
        "    def log_message(self, *a): pass\n"
        f"socketserver.TCPServer(('127.0.0.1', {PORT}), H).serve_forever()\n"
    )
    sandbox.write_file("/srv/server.py", server_py)

    # base has NO trailing slash, resource has NO leading slash -> the naive
    # `base + resource` concatenation merges "api"+"v2" and 404s; the agent must
    # join them with exactly one '/'.
    base = f"http://127.0.0.1:{PORT}/api"
    resource = f"v2/items/{rid}/value"
    sandbox.write_file("/work/config.txt", f"base={base}\nresource={resource}\n")

    # start the server and wait until it answers
    sandbox.run("nohup python3 /srv/server.py >/dev/null 2>&1 &", timeout=10)
    for _ in range(10):
        probe = sandbox.run(
            f"python3 -c \"import urllib.request as u; "
            f"print(u.urlopen('http://127.0.0.1:{PORT}{correct_path}').read().decode())\" 2>/dev/null",
            timeout=10,
        )
        if secret in (probe.stdout or ""):
            break
        sandbox.run("sleep 0.5", timeout=5)
    return {"secret": secret}


def verify(sandbox, trace, context):
    secret = context["secret"]
    ans = (trace.final_answer or "").strip()
    correct = secret in ans
    cmds = trace.bash_commands
    used_fetch = any(("urlopen" in c or "urllib" in c or "127.0.0.1" in c or str(PORT) in c)
                     for c in cmds)
    return {
        "passed": correct,
        "score": 1.0 if correct else 0.0,
        "checks": {
            "answer_contains_secret": correct,
            "fetched_from_service": used_fetch,
        },
        "metrics": {
            "talk_vs_do_gap": bool(ans) and not correct,
            # answered without ever hitting the service = fabrication
            "hallucinated": bool(ans) and not correct and not used_fetch,
        },
        "notes": "ok" if correct
        else f"want {secret!r}; fetched={used_fetch} ans={ans[:40]!r}",
    }
