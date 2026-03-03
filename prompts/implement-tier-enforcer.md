I have two files downloaded on this machine that need to be installed
as a working MCP server inside Claude CLI. Read both files first,
understand them fully, then execute the installation steps below.

The two files are:
  ~/Downloads/tier-enforcer-server.py
  ~/Downloads/tier-enforcer-setup-v5.md

══════════════════════════════════════════════════════════════════════
  PHASE 1 — READ BOTH FILES FIRST
══════════════════════════════════════════════════════════════════════

Read tier-enforcer-server.py — understand the 7 MCP tools it contains.
Read tier-enforcer-setup-v5.md — this is your install instruction manual.
Extract from setup-v5.md:
  • The claude_desktop_config.json snippet
  • The System Prompt v5.0 block
  • The install commands

Report: "Files read. Server has [N] tools: [list them]"

══════════════════════════════════════════════════════════════════════
  PHASE 2 — ENVIRONMENT CHECK
══════════════════════════════════════════════════════════════════════

Run each check, show output, fix any blockers before proceeding:

  python3 --version

  python3 -c "import fastmcp; print('fastmcp OK:', fastmcp.__version__)" \
    2>/dev/null || echo "fastmcp NOT INSTALLED"

  which gemini 2>/dev/null && gemini --version 2>/dev/null \
    || echo "gemini CLI NOT FOUND"

  curl -s --max-time 3 http://localhost:11434/api/tags \
    | python3 -c "import sys,json
m=json.load(sys.stdin).get('models',[])
qwen=[x['name'] for x in m if 'qwen' in x['name']]
print('Ollama OK, qwen:', qwen or 'NONE')" 2>/dev/null || echo "Ollama OFFLINE"

  echo "OLLAMA_CLOUD_HOST=${OLLAMA_CLOUD_HOST:-NOT SET}"

  cat "$HOME/Library/Application Support/Claude/claude_desktop_config.json" \
    2>/dev/null || echo "config NOT FOUND — will create"

Fixes if needed:
  fastmcp missing  → pip install fastmcp --break-system-packages
  qwen2.5 missing  → ollama pull qwen2.5-coder:7b
  gemini missing   → tell me, I will handle separately

══════════════════════════════════════════════════════════════════════
  PHASE 3 — INSTALL THE MCP SERVER
══════════════════════════════════════════════════════════════════════

  mkdir -p ~/tier-enforcer-mcp
  cp ~/Downloads/tier-enforcer-server.py ~/tier-enforcer-mcp/server.py

  python3 -c "import ast; ast.parse(open('$HOME/tier-enforcer-mcp/server.py').read()); print('Syntax OK')"

  python3 -c "
import json, os, subprocess, time, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path
from fastmcp import FastMCP
print('All imports OK')
"

══════════════════════════════════════════════════════════════════════
  PHASE 4 — REGISTER IN claude_desktop_config.json
══════════════════════════════════════════════════════════════════════

Read the current claude_desktop_config.json.
Preserve ALL existing mcpServers entries exactly as they are.
Add the tier-enforcer entry from setup-v5.md with these adjustments:
  - Use FULL absolute path for server.py (not ~/)
  - Use real OLLAMA_CLOUD_HOST value if set, otherwise keep placeholder
  - TIER_LOG path must also be absolute

Write merged config back to:
  ~/Library/Application Support/Claude/claude_desktop_config.json

Validate:
  python3 -c "
import json
p = '$HOME/Library/Application Support/Claude/claude_desktop_config.json'
d = json.load(open(p))
servers = d.get('mcpServers', {})
print('Valid JSON. Servers:', list(servers.keys()))
assert 'tier-enforcer' in servers, 'tier-enforcer MISSING'
print('tier-enforcer config OK')
print(json.dumps(servers['tier-enforcer'], indent=2))
"

══════════════════════════════════════════════════════════════════════
  PHASE 5 — SMOKE TEST
══════════════════════════════════════════════════════════════════════

  timeout 5 python3 ~/tier-enforcer-mcp/server.py 2>&1 | head -20 \
    || echo "(timeout expected — server is a daemon)"

Fix any import errors or exceptions before continuing.

══════════════════════════════════════════════════════════════════════
  PHASE 6 — SAVE SYSTEM PROMPT
══════════════════════════════════════════════════════════════════════

Extract the System Prompt v5.0 from tier-enforcer-setup-v5.md and save
as plain text (no markdown fences, no headers) to:
  ~/tier-enforcer-mcp/SYSTEM_PROMPT_V5.txt

Print first 8 lines to confirm.

══════════════════════════════════════════════════════════════════════
  PHASE 7 — FINAL REPORT
══════════════════════════════════════════════════════════════════════

  ┌─ TIER-ENFORCER INSTALLATION ───────────────────────────────────┐
  │ server.py          : [full path] — Syntax OK / FAILED          │
  │ fastmcp import     : OK / FAILED                               │
  │ config.json        : tier-enforcer REGISTERED / FAILED         │
  │ SYSTEM_PROMPT file : [full path]                               │
  │                                                                 │
  │ T1-LOCAL qwen2.5-coder:7b  : ONLINE / OFFLINE                 │
  │ T1-CLOUD qwen3-coder:480b  : ONLINE / NOT SET / OFFLINE        │
  │ T2 gemini CLI              : ONLINE / NOT INSTALLED            │
  │ T3 Claude (self)           : ALWAYS ONLINE                     │
  │                                                                 │
  │ NEXT: Restart Claude CLI → verify tier_health_check() works    │
  └─────────────────────────────────────────────────────────────────┘

══════════════════════════════════════════════════════════════════════
  AFTER RESTART — VERIFICATION
══════════════════════════════════════════════════════════════════════

Type this in Claude CLI to confirm MCP server loaded:
  "Call tier_health_check and show me which tiers are online"

If tier-enforcer tools are NOT visible:
  1. Run: python3 ~/tier-enforcer-mcp/server.py
     Look at the error output
  2. Common fix: pip install fastmcp --break-system-packages
  3. Check: Console.app → search "Claude" → look for MCP errors
