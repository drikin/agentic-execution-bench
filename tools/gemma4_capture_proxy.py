"""Logging forward-proxy in front of spark3 vLLM (gemma4).

Captures the FULL request (system prompt, tools, messages) that Hermes sends
for each platform, forwards to the real endpoint, returns the response.
Point Hermes' gemma4 base_url at this proxy, trigger the same query from the
Web dashboard (works) and Discord (fails), then diff the two captured records.
"""
import http.server
import socketserver
import urllib.request
import json
import time

UPSTREAM = "http://100.104.183.13:8000"
LOGFILE = "/tmp/gemma4_capture.jsonl"


class H(http.server.BaseHTTPRequestHandler):
    def _forward(self, method, body=None):
        req = urllib.request.Request(UPSTREAM + self.path, data=body, method=method)
        req.add_header("Content-Type", "application/json")
        auth = self.headers.get("Authorization")
        if auth:
            req.add_header("Authorization", auth)
        resp = urllib.request.urlopen(req, timeout=300)
        data = resp.read()
        self.send_response(resp.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            d = json.loads(body)
            msgs = d.get("messages", [])
            sys_msg = next((m.get("content") for m in msgs if m.get("role") == "system"), None)
            user_msg = next((m.get("content") for m in msgs if m.get("role") == "user"), None)
            rec = {
                "t": time.strftime("%H:%M:%S"),
                "path": self.path,
                "model": d.get("model"),
                "n_messages": len(msgs),
                "roles": [m.get("role") for m in msgs],
                "n_tools": len(d.get("tools", [])),
                "tool_names": [t.get("function", {}).get("name") for t in d.get("tools", [])],
                "max_tokens": d.get("max_tokens"),
                "system_len": len(sys_msg or ""),
                "system": sys_msg,
                "first_user": user_msg,
            }
            with open(LOGFILE, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception as e:
            with open(LOGFILE, "a") as f:
                f.write(json.dumps({"err": str(e), "raw_len": len(body)}) + "\n")
        try:
            self._forward("POST", body)
        except Exception as e:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(str(e).encode())

    def do_GET(self):
        try:
            self._forward("GET")
        except Exception as e:
            self.send_response(502)
            self.end_headers()

    def log_message(self, *a):
        pass


socketserver.ThreadingTCPServer.allow_reuse_address = True
with socketserver.ThreadingTCPServer(("0.0.0.0", 8099), H) as srv:
    print("proxy on :8099 -> " + UPSTREAM)
    srv.serve_forever()
