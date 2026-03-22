#!/usr/bin/env python3
"""
DSR AI-LAB TOOL INTERCEPTION HOOK v9
File: ~/tier-enforcer-mcp/intercept.py

v9 PERMANENT FIX — path-based intercept logic:
  Look at WHAT FILE is being modified, not just which tool.
  ~/.claude/           = Claude CLI internal  = ALWAYS passthrough
  ~/tier-enforcer-mcp/ = MCP server files     = ALWAYS passthrough
  ~/tier-router-mcp/   = tier-router files    = ALWAYS passthrough
  ~/.tier-enforcer/    = routing DB/logs      = ALWAYS passthrough
  /tmp/, /var/, /usr/  = system paths         = ALWAYS passthrough
  Everything else      = user project         = intercept to Ollama

  No list to maintain. No regex to break. Based on file ownership.

PREVIOUS BROKEN APPROACHES (v8.x):
  v8.0: Bash|Edit|Write in matcher     → stopped ALL Bash
  v8.1: Passthrough list               → list always incomplete
  v8.2: Default passthrough            → still blocked some Bash
  v8.3: Bash excluded from matcher     → Edit on ~/.claude/ still blocked

FLOW:
  Edit/Write/MultiEdit on user project → route to Ollama T1 tier
  Edit/Write/MultiEdit on internal paths → continue=True passthrough
  Bash + everything else               → continue=True passthrough
"""

import sys
import json
import os
import time
import urllib.request
import logging

HOME   = os.path.expanduser("~")
DB_DIR = os.path.join(HOME, ".tier-enforcer")
LOG    = os.path.join(DB_DIR, "intercept.log")
os.makedirs(DB_DIR, exist_ok=True)

logging.basicConfig(
    filename=LOG,
    level=logging.INFO,
    format="%(asctime)s %(message)s"
)
log = logging.getLogger("intercept-v9")

OLLAMA_LOCAL = os.environ.get("OLLAMA_LOCAL_HOST", "http://localhost:11434")
OLLAMA_CLOUD = os.environ.get("OLLAMA_CLOUD_HOST", "http://localhost:11434")

MODELS = {
    "T1-LOCAL": {
        "model":   "qwen2.5-coder:7b",
        "base":    OLLAMA_LOCAL,
        "timeout": 300,
    },
    "T1-MID": {
        "model":   "qwen2.5-coder:14b",
        "base":    OLLAMA_LOCAL,
        "timeout": 600,
    },
    "T1-CLOUD": {
        "model":   "qwen3-coder:480b",
        "base":    OLLAMA_CLOUD,
        "timeout": 600,
    },
}

# Only these tools are candidates for interception.
# Bash is NOT here — Bash always passes through natively.
OLLAMA_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

# Internal paths that must NEVER be intercepted.
# These are Claude CLI config files and MCP infrastructure.
INTERNAL_PATHS = [
    os.path.join(HOME, ".claude"),            # CLAUDE.md, settings.json, etc.
    os.path.join(HOME, "tier-enforcer-mcp"),  # MCP server files
    os.path.join(HOME, "tier-router-mcp"),    # tier-router MCP files
    os.path.join(HOME, ".tier-enforcer"),     # routing DB, logs
    "/tmp",                                    # temp files
    "/var/",                                   # system files
    "/usr/",                                   # system files
]


def is_internal_path(file_path: str) -> bool:
    """Return True if file_path is a Claude CLI / MCP internal file."""
    expanded = os.path.expanduser(file_path) if file_path else ""
    for internal in INTERNAL_PATHS:
        if expanded.startswith(internal):
            return True
    return False


def passthrough():
    """Return pass-through response to Claude CLI."""
    print(json.dumps({"continue": True}))


def intercept(result: str, tier: str, model: str, elapsed: float):
    """Return intercepted result to Claude CLI."""
    banner = (
        "\n\n--- Executed by: " + model
        + " (" + tier + ") "
        + str(elapsed) + "s ---\n"
        + "--- Ollama executed | Claude routed | NOT Claude ---"
    )
    print(json.dumps({
        "continue":   False,
        "stopReason": "intercept_routed_to_ollama",
        "output":     result + banner,
    }))


def pick_tier(tool_name: str, tool_input: dict) -> str:
    """Select Ollama tier based on file modification size."""
    if tool_name == "Write":
        content = str(tool_input.get("content", ""))
        return "T1-MID" if len(content) > 500 else "T1-LOCAL"

    if tool_name == "Edit":
        old = str(tool_input.get("old_string", ""))
        new = str(tool_input.get("new_string", ""))
        return "T1-MID" if len(old + new) > 500 else "T1-LOCAL"

    if tool_name in ("MultiEdit", "NotebookEdit"):
        edits = tool_input.get("edits", [])
        if len(edits) > 3 or len(str(edits)) > 3000:
            return "T1-CLOUD"
        return "T1-MID"

    return "T1-LOCAL"


def make_prompt(tool_name: str, tool_input: dict) -> str:
    """Build execution prompt for Ollama."""
    if tool_name == "Write":
        path    = tool_input.get("path", "unknown")
        content = tool_input.get("content", "")
        return (
            "Write exactly this content to file: " + path + "\n"
            "Return ONLY the line: File written: " + path + "\n\n"
            + content
        )

    if tool_name == "Edit":
        path = tool_input.get("path", "unknown")
        old  = tool_input.get("old_string", "")
        new  = tool_input.get("new_string", "")
        return (
            "Edit file: " + path + "\n"
            "FIND:\n" + old + "\n"
            "REPLACE WITH:\n" + new + "\n"
            "Return ONLY: Edit applied: " + path
        )

    if tool_name == "MultiEdit":
        path  = tool_input.get("path", "unknown")
        edits = tool_input.get("edits", [])
        parts = ["MultiEdit: " + path]
        for i, e in enumerate(edits, 1):
            parts.append(
                str(i) + ". Replace: "
                + str(e.get("old_string", ""))[:80]
                + " -> "
                + str(e.get("new_string", ""))[:80]
            )
        parts.append("Return ONLY: MultiEdit applied: " + path)
        return "\n".join(parts)

    return "Execute: " + json.dumps(tool_input)[:400]


def call_ollama(model: str, base: str, prompt: str, timeout: int) -> str:
    """Call Ollama via streaming HTTP. stdlib only."""
    payload = json.dumps({
        "model":    model,
        "messages": [{"role": "user", "content": prompt}],
        "stream":   True,
        "options":  {
            "num_ctx":     4096,
            "num_predict": 2048,
            "temperature": 0.05,
            "keep_alive":  -1,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        base.rstrip("/") + "/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    chunks = []
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    c = obj.get("message", {}).get("content", "")
                    if c:
                        chunks.append(c)
                    if obj.get("done", False):
                        break
                except json.JSONDecodeError:
                    pass
        return "".join(chunks).strip()
    except Exception as e:
        log.error("OLLAMA_ERR model=%s err=%s", model, str(e)[:120])
        return "Ollama error: " + str(e)[:200]


def main():
    t_start = time.time()

    # Read from Claude CLI
    try:
        raw  = sys.stdin.read()
        data = json.loads(raw)
    except Exception as e:
        log.warning("PARSE_FAIL %s — passthrough", str(e)[:60])
        passthrough()
        return

    tool_name  = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    # Bash always passes through — no interception ever
    if tool_name == "Bash":
        passthrough()
        return

    # Not in our intercept list — pass through
    if tool_name not in OLLAMA_TOOLS:
        passthrough()
        return

    # v9 PATH-BASED FILTER: Never intercept Claude CLI / MCP internal files
    file_path = (
        tool_input.get("path", "")
        or tool_input.get("file_path", "")
        or ""
    )
    if is_internal_path(file_path):
        log.info("PASSTHROUGH internal=%s tool=%s", file_path[:80], tool_name)
        passthrough()
        return

    # No file path at all — pass through (safety)
    if not file_path:
        log.info("PASSTHROUGH no-path tool=%s", tool_name)
        passthrough()
        return

    # Route user project file modification to Ollama
    tier    = pick_tier(tool_name, tool_input)
    cfg     = MODELS[tier]
    model   = cfg["model"]
    base    = cfg["base"]
    timeout = cfg["timeout"]
    prompt  = make_prompt(tool_name, tool_input)

    log.info("INTERCEPT tool=%s file=%s tier=%s model=%s", tool_name, file_path[:60], tier, model)

    result  = call_ollama(model, base, prompt, timeout)
    elapsed = round(time.time() - t_start, 1)

    log.info("DONE tier=%s model=%s elapsed=%ss", tier, model, elapsed)

    intercept(result, tier, model, elapsed)


if __name__ == "__main__":
    main()
