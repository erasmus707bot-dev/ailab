#!/usr/bin/env bash
# Install the srt sandbox, run the Hermes MCP server as a user service (survives reboots), switch the AI Lab to
# connected mode, then restart it.
# Safe to re-run: every step skips itself if already done. Run in a terminal on gandalf:
#   bash ~/ailab/tools/ailab-connect.sh
set -u
say() { printf '\n== %s\n' "$*"; }
LABCFG="$HOME/.config/ailab/config.json"
TOKEN="$HOME/hermes-forge/mcp/tokens/ailab.token"

say "1/5 srt sandbox"
if command -v srt >/dev/null; then echo "srt already installed: $(command -v srt)"
else
  miss=""; for p in bwrap socat rg; do command -v $p >/dev/null || miss="$miss $p"; done
  if [ -n "$miss" ]; then
    echo "srt needs:$miss  →  installing (sudo password asked once)"
    sudo apt-get install -y bubblewrap socat ripgrep || { echo "✗ apt failed — stop"; exit 1; }
  fi
  npm install -g @anthropic-ai/sandbox-runtime || { echo "✗ npm install failed — stop"; exit 1; }
  command -v srt >/dev/null || { echo "✗ srt installed but not on PATH (check ~/.npm-global/bin) — stop"; exit 1; }
fi

say "2/5 Lab token for the Hermes MCP server"
if [ -s "$TOKEN" ]; then echo "token already exists"
else (cd "$HOME/hermes" && python3 -m forge.projects.mcp_server token add ailab) || { echo "✗ token add failed — stop"; exit 1; }
fi

say "3/5 Hermes MCP server (user service, 127.0.0.1:8851)"
PORT=8851
is_mcp() { curl -s -m 2 -X POST -H 'Content-Type: application/json' -d '{}' "http://127.0.0.1:$1/mcp" 2>/dev/null | grep -q 'missing or unknown token'; }
if [ -x "$HOME/hermes/ops/mcp/install.sh" ] && command -v systemctl >/dev/null; then
  pkill -u "$(id -u)" -f "forge.projects.mcp_server http --port 8851" 2>/dev/null   # a one-off copy from the old script would block the port
  bash "$HOME/hermes/ops/mcp/install.sh" || exit 1
else
  echo "no ops/mcp/install.sh or no systemd — starting a one-off copy (will not survive a reboot)"
  is_mcp $PORT || (cd "$HOME/hermes" && setsid nohup python3 -m forge.projects.mcp_server http --port "$PORT" >>"$HOME/.config/ailab/mcp.log" 2>&1 </dev/null &)
fi
for _ in $(seq 1 15); do is_mcp $PORT && break; sleep 0.3; done
is_mcp $PORT || { echo "✗ MCP server not answering on $PORT — journalctl --user -u hermes-mcp -n 30"; exit 1; }

say "4/5 Lab config → connected"
mkdir -p "$(dirname "$LABCFG")"
[ -f "$LABCFG" ] && cp -p "$LABCFG" "$LABCFG.bak-$(date +%Y%m%d-%H%M%S)" && echo "backup saved next to it"
python3 - "$LABCFG" "$PORT" "$TOKEN" <<'EOF'
import json, sys, pathlib
p, port, tok = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
c = json.loads(p.read_text() or "{}") if p.exists() else {}
c.update(mode="connected", hermes_mcp_url=f"http://127.0.0.1:{port}/mcp", hermes_token_file=tok)
p.write_text(json.dumps(c, indent=1) + "\n")
print("mode=connected, hermes_mcp_url=" + c["hermes_mcp_url"])
EOF

say "5/5 restart the Lab"
"$HOME/ailab/tools/ailab-open.sh" && echo "✓ done — the Lab's top bar should say 🔗 Connected and the red sandbox line should be gone"
