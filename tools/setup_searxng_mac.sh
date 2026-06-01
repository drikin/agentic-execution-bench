#!/bin/bash
# Stand up a local SearXNG container on the Mac for Hermes web search.
# Works around the headless-ssh keychain issue by temporarily stripping
# credsStore from ~/.docker/config.json (anonymous pull of a public image),
# then restoring it.
set -u
P="$HOME/.docker/config.json"

cp "$P" "$P.hermesbak"

python3 - <<'PYEOF'
import json, os
p = os.path.expanduser("~/.docker/config.json")
d = json.load(open(p))
d.pop("credsStore", None)
d.pop("credHelpers", None)
json.dump(d, open(p, "w"))
print("after-edit credsStore present:", "credsStore" in json.load(open(p)))
PYEOF

echo "--- config after edit ---"
grep -c credsStore "$P" || true

docker rm -f searxng 2>/dev/null || true
echo "--- pull ---"
docker pull searxng/searxng:latest 2>&1 | tail -3
echo "--- run ---"
docker run -d --name searxng --restart unless-stopped \
  -p 127.0.0.1:8888:8080 \
  -v "$HOME/searxng:/etc/searxng" \
  searxng/searxng:latest 2>&1 | tail -2

# restore original docker config (with credsStore) regardless of outcome
cp "$P.hermesbak" "$P"
echo "--- restored config (credsStore back): $(grep -c credsStore "$P") ---"
echo "--- container status ---"
docker ps --filter name=searxng --format '{{.Names}} {{.Status}} {{.Ports}}'
