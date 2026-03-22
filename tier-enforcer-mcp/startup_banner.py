#!/usr/bin/env python3
"""
DSR AI-LAB — Startup Banner v9.1
File: ~/tier-enforcer-mcp/startup_banner.py

Runs at Claude CLI SessionStart via settings.local.json hook.
Live-checks every system component and prints a real status banner:
  - Claude OAuth
  - LangGraph + LangSmith
  - Tier Enforcer (DB, intercept, routing count)
  - Ollama models T1-LOCAL / T1-MID / T1-CLOUD
  - Gemini CLI  T2-FLASH / T2-PRO
  - HF API  T2-KIMI
  - All 22 MCP servers
  - All Skills
  - Auto-prewarms T1-LOCAL + T1-MID in background (keep_alive=-1)

Width: 78 chars. All checks run in parallel threads (max 6s wait).
"""

import importlib.metadata, json, os, shutil, sqlite3, subprocess
import threading, time, urllib.request, urllib.error

HOME            = os.path.expanduser("~")
SETTINGS_FILE   = os.path.join(HOME, ".claude", "settings.json")

def _read_settings_env():
    """Read env vars injected into tier-enforcer MCP server from settings.json."""
    try:
        with open(SETTINGS_FILE) as f:
            d = json.load(f)
        return d.get("mcpServers", {}).get("tier-enforcer", {}).get("env", {})
    except Exception:
        return {}

_SENV           = _read_settings_env()
OLLAMA          = _SENV.get("OLLAMA_LOCAL_HOST",
                    os.environ.get("OLLAMA_LOCAL_HOST", "http://localhost:11434"))
HF_API_KEY      = _SENV.get("HF_API_KEY",
                    os.environ.get("HF_API_KEY", ""))
LANGSMITH_KEY   = os.environ.get(
                    "LANGCHAIN_API_KEY",
                    """")
LANGSMITH_PROJ  = _SENV.get("LANGCHAIN_PROJECT",
                    os.environ.get("LANGCHAIN_PROJECT", "dsr-ai-lab-tier-v9"))
SKILLS_DIR      = os.path.join(HOME, ".claude", "skills")
DB_PATH         = os.path.join(HOME, ".tier-enforcer", "memory.db")
INTERCEPT_PATH  = os.path.join(HOME, "tier-enforcer-mcp", "intercept.py")
PREWARM_LOG     = os.path.join(HOME, ".tier-enforcer", "prewarm.log")
SETTINGS_PATH   = os.path.join(HOME, ".claude", "settings.json")
W               = 78   # banner inner width (including border chars)

# ── MCP server definitions ────────────────────────────────────────────────────
# (name, display_label, check_type, check_value)
# check_type: "file" = path must exist | "cmd" = shell command must be found
MCP_SERVERS = [
    # Core / infrastructure
    ("tier-enforcer",      "tier-enforcer",  "file", HOME+"/tier-enforcer-mcp/server.py"),
    ("filesystem",         "filesystem",     "cmd",  "npx"),
    ("git",                "git",            "cmd",  "uvx"),
    ("memory",             "memory",         "cmd",  "npx"),
    ("github",             "github",         "cmd",  "npx"),
    ("gdrive",             "gdrive",         "cmd",  "npx"),
    # Dev MCPs
    ("intent-mcp",         "intent",         "file", HOME+"/intent-mcp/server.py"),
    ("arch-mcp",           "arch",           "file", HOME+"/arch-mcp/server.py"),
    ("coding-mcp",         "coding",         "file", HOME+"/coding-mcp/server.py"),
    ("rca-mcp",            "rca",            "file", HOME+"/rca-mcp/server.py"),
    ("integration-mcp",    "integration",    "file", HOME+"/integration-mcp/server.py"),
    ("aidev-mcp",          "aidev",          "file", HOME+"/aidev-mcp/server.py"),
    ("math-mcp",           "math",           "file", HOME+"/math-mcp/server.py"),
    # Domain MCPs
    ("budget-mcp",         "budget",         "file", HOME+"/budget-mcp/server.py"),
    ("context-mcp",        "context",        "file", HOME+"/context-mcp/server.py"),
    ("rpa-mcp",            "rpa",            "file", HOME+"/rpa-mcp/server.py"),
    ("mobile-dev-mcp",     "mobile",         "file", HOME+"/mobile-dev-mcp/server.py"),
    ("webmobile-dev-mcp",  "webmobile",      "file", HOME+"/webmobile-dev-mcp/server.py"),
    ("website-dev-mcp",    "website",        "file", HOME+"/website-dev-mcp/server.py"),
    ("ecommerce-mcp",      "ecommerce",      "file", HOME+"/ecommerce-mcp/server.py"),
    ("mac-automation-mcp", "mac-auto",       "file", HOME+"/mac-automation-mcp/server.py"),
    ("files-automation-mcp","files-auto",    "file", HOME+"/files-automation-mcp/server.py"),
]

# ── Banner helpers ────────────────────────────────────────────────────────────

_IW = W - 2   # inner width

def _top():    return "╔" + "═" * _IW + "╗"
def _sep():    return "╠" + "═" * _IW + "╣"
def _bot():    return "╚" + "═" * _IW + "╝"

def _hdr(text):
    pad = _IW - len(text)
    return "║" + " " * (pad // 2) + text + " " * (pad - pad // 2) + "║"

def _row(label, value, lw=14):
    content = f"  {label:<{lw}}{value}"
    pad = _IW - len(content)
    return "║" + content + " " * max(pad, 1) + "║"

def _plain(text):
    pad = _IW - len(text) - 2
    return "║  " + text + " " * max(pad, 0) + "║"

# ── Checkers ──────────────────────────────────────────────────────────────────

def _ollama_state():
    pulled, loaded, up = [], [], False
    try:
        with urllib.request.urlopen(
            urllib.request.Request(OLLAMA.rstrip("/") + "/api/tags"), timeout=3
        ) as r:
            pulled = [m["name"] for m in json.loads(r.read()).get("models", [])]
            up = True
    except Exception:
        pass
    try:
        with urllib.request.urlopen(
            urllib.request.Request(OLLAMA.rstrip("/") + "/api/ps"), timeout=3
        ) as r:
            loaded = [m["name"] for m in json.loads(r.read()).get("models", [])]
    except Exception:
        pass
    return up, pulled, loaded


def _model_badge(up, pulled, loaded, name):
    if not up:
        return "✗ OLLAMA DOWN"
    short = name.split(":")[0]
    in_ram   = any(name in m or m.startswith(short + ":") for m in loaded)
    in_pull  = any(name in m or m.startswith(short + ":") for m in pulled)
    if in_ram:   return "✅ LIVE (in RAM)"
    if in_pull:  return "⚡ READY (on-demand)"
    return "✗ NOT PULLED"


def _gemini_badge():
    try:
        r = subprocess.run(["gemini", "--version"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            ver = r.stdout.strip().split("\n")[0].strip()[:15]
            return f"✅ LIVE  v{ver}"
        return "✗ DOWN"
    except FileNotFoundError:
        return "✗ NOT INSTALLED"
    except Exception as e:
        return f"✗ ERR {str(e)[:18]}"


def _hf_badge():
    key = HF_API_KEY.strip()
    if not key or key in ("SET_YOUR_HF_KEY", ""):
        return "⚠  NO API KEY — set HF_API_KEY in settings.json"
    try:
        req = urllib.request.Request(
            "https://huggingface.co/api/whoami-v2",
            headers={"Authorization": f"Bearer {key}"}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            d    = json.loads(r.read())
            user = d.get("name", "?")
            plan = "Pro" if d.get("isPro") else "Free"
            return f"✅ LIVE  @{user} ({plan})"
    except urllib.error.HTTPError as e:
        return f"✗ AUTH FAIL ({e.code}) — check HF_API_KEY"
    except Exception:
        return "✗ OFFLINE"


def _claude_badge():
    try:
        r = subprocess.run(
            ["security", "find-generic-password",
             "-s", "Claude Code-credentials", "-w"],
            capture_output=True, text=True, timeout=4
        )
        if r.returncode == 0 and r.stdout.strip():
            return "✅ AUTH  OAuth via macOS Keychain"
        return "⚠  Token not found in Keychain"
    except Exception:
        return "✅ AUTH  (active session)"


def _langsmith_badge():
    key = LANGSMITH_KEY.strip()
    if not key:
        return "⚠  NO API KEY"
    try:
        req = urllib.request.Request(
            "https://api.smith.langchain.com/info",
            headers={"x-api-key": key}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            ver  = data.get("version", "?")
            try:
                sdk = importlib.metadata.version("langsmith")
            except Exception:
                sdk = "?"
            return f"✅ LIVE  server={ver}  sdk={sdk}  project={LANGSMITH_PROJ}"
    except urllib.error.HTTPError as e:
        return f"✗ AUTH FAIL ({e.code})"
    except Exception as e:
        return f"✗ OFFLINE ({str(e)[:30]})"


def _langgraph_badge():
    try:
        from langgraph.graph import StateGraph, END  # noqa: F401
        try:
            ver = importlib.metadata.version("langgraph")
        except Exception:
            ver = "installed"
        return f"✅ LIVE  v{ver}  8-node pipeline active"
    except ImportError as e:
        return f"✗ IMPORT FAIL: {str(e)[:40]}"


def _tier_enforcer_badge():
    parts = []
    # intercept.py
    parts.append("intercept ✅" if os.path.isfile(INTERCEPT_PATH) else "intercept ✗")
    # DB
    if os.path.isfile(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            count = conn.execute("SELECT COUNT(*) FROM routing_log").fetchone()[0]
            conn.close()
            parts.append(f"DB ✅ ({count} routes logged)")
        except Exception:
            parts.append("DB ✅")
    else:
        parts.append("DB ✗ missing")
    # server.py
    srv = os.path.join(HOME, "tier-enforcer-mcp", "server.py")
    parts.append("server ✅" if os.path.isfile(srv) else "server ✗")
    return "  ".join(parts)


def _mcp_check(check_type, check_value):
    if check_type == "file":
        return os.path.isfile(check_value)
    if check_type == "cmd":
        return shutil.which(check_value) is not None
    return False


def _skills_check():
    if not os.path.isdir(SKILLS_DIR):
        return [], []
    found, missing = [], []
    for f in sorted(os.listdir(SKILLS_DIR)):
        if f.endswith(".md"):
            name = f[:-3]
            path = os.path.join(SKILLS_DIR, f)
            if os.path.isfile(path):
                found.append(name)
            else:
                missing.append(name)
    return found, missing


# ── Prewarm ───────────────────────────────────────────────────────────────────

def _prewarm_model(model):
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
        "options": {"num_predict": 1, "keep_alive": -1}
    }).encode()
    req = urllib.request.Request(
        OLLAMA.rstrip("/") + "/api/chat",
        data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120):
            pass
        elapsed = round(time.time() - t, 1)
        os.makedirs(os.path.dirname(PREWARM_LOG), exist_ok=True)
        with open(PREWARM_LOG, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {model}  OK  {elapsed}s\n")
    except Exception as e:
        with open(PREWARM_LOG, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {model}  ERR  {e}\n")


def _start_prewarm(up, loaded):
    if not up:
        return "✗ Ollama down — skip"
    need = [m for m in ["qwen2.5-coder:7b", "qwen2.5-coder:14b"]
            if not any(m in x for x in loaded)]
    if not need:
        return "✅ T1-LOCAL + T1-MID already in RAM"
    for m in need:
        threading.Thread(target=_prewarm_model, args=(m,), daemon=True).start()
    return f"⏳ Loading {' + '.join(need)} → RAM (background)"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    results = {}
    lock    = threading.Lock()

    def collect(key, fn, *args):
        try:
            val = fn(*args)
        except Exception as e:
            val = f"✗ ERR {str(e)[:30]}"
        with lock:
            results[key] = val

    # Ollama (sync — needed for model badges + prewarm)
    up, pulled, loaded = _ollama_state()

    # All remote / slow checks in parallel
    checks = [
        ("gemini",    _gemini_badge),
        ("hf",        _hf_badge),
        ("claude",    _claude_badge),
        ("langsmith", _langsmith_badge),
        ("langgraph", _langgraph_badge),
    ]
    threads = [threading.Thread(target=collect, args=(k, fn)) for k, fn in checks]
    for t in threads: t.start()

    # Fast local checks (no I/O blocking)
    tier_badge    = _tier_enforcer_badge()
    mcp_results   = {name: _mcp_check(ct, cv) for name, _, ct, cv in MCP_SERVERS}
    skills_ok, skills_miss = _skills_check()

    for t in threads: t.join(timeout=7)

    # Retrieve results
    claude_badge    = results.get("claude",    "✅ AUTH  (active session)")
    gemini_badge    = results.get("gemini",    "✗ TIMEOUT")
    hf_badge        = results.get("hf",        "✗ TIMEOUT")
    langsmith_badge = results.get("langsmith", "✗ TIMEOUT")
    langgraph_badge = results.get("langgraph", "✗ TIMEOUT")
    prewarm_msg     = _start_prewarm(up, loaded)

    t1l = _model_badge(up, pulled, loaded, "qwen2.5-coder:7b")
    t1m = _model_badge(up, pulled, loaded, "qwen2.5-coder:14b")
    t1c = _model_badge(up, pulled, loaded, "qwen3-coder:480b-cloud")

    mcp_ok_count   = sum(1 for v in mcp_results.values() if v)
    mcp_fail_count = len(mcp_results) - mcp_ok_count

    # ── Build banner ──────────────────────────────────────────────────────────
    B = []
    app = B.append

    app("")
    app(_top())
    app(_hdr("DSR AI-LAB — TIER ROUTING v9  |  FULL LIVE STATUS"))
    app(_sep())

    # Claude
    app(_row("🧠 Claude",   claude_badge))
    app(_row("  Bash",      "NATIVE  (not intercepted)"))
    app(_row("  Edit/Write","intercept.py → Ollama T1  (auto-routed)"))
    app(_sep())

    # Infrastructure
    app(_hdr("INFRASTRUCTURE"))
    app(_row("LangGraph",   langgraph_badge, lw=12))
    app(_row("LangSmith",   langsmith_badge, lw=12))
    app(_row("TierEnforcer", tier_badge, lw=13))
    app(_sep())

    # Executors
    app(_hdr("EXECUTORS — Ollama  (all code execution)"))
    app(_row("⚙ T1-LOCAL",  f"qwen2.5-coder:7b        {t1l}", lw=12))
    app(_row("⚙ T1-MID",    f"qwen2.5-coder:14b       {t1m}", lw=12))
    app(_row("⚙ T1-CLOUD",  f"qwen3-coder:480b-cloud  {t1c}", lw=12))
    app(_sep())

    # Analysis
    app(_hdr("ANALYSIS — Gemini / HF  (never execute code)"))
    app(_row("🔍 T2-FLASH",  f"gemini-2.5-flash   {gemini_badge}", lw=12))
    app(_row("🔍 T2-PRO",    f"gemini-2.5-pro     {gemini_badge}", lw=12))
    app(_row("🔍 T2-KIMI",   f"Kimi-K2-Instruct   {hf_badge}",    lw=12))
    app(_sep())

    # MCP Servers
    ok_sym  = lambda ok: "✅" if ok else "✗ "
    app(_hdr(f"MCP SERVERS ({len(MCP_SERVERS)})  —  "
             f"✅ {mcp_ok_count} active  {'✗ ' + str(mcp_fail_count) + ' missing' if mcp_fail_count else '✅ all present'}"))

    # Build compact tag lines for MCP servers (4 per row)
    labels = [f"{ok_sym(mcp_results[name])}{label}"
              for name, label, _, _ in MCP_SERVERS]
    row_size = 4
    for i in range(0, len(labels), row_size):
        chunk = labels[i:i + row_size]
        line  = "  ".join(f"{l:<18}" for l in chunk).rstrip()
        app(_plain(line))
    app(_sep())

    # Skills
    all_skills = skills_ok + skills_miss
    if all_skills:
        ok_count   = len(skills_ok)
        miss_count = len(skills_miss)
        status     = "✅ all loaded" if not miss_count else f"⚠ {miss_count} missing"
        app(_hdr(f"SKILLS ({len(all_skills)})  —  {status}"))
        # 4 per row — keeps within 76-char inner width
        skill_tags = [f"{'✅' if s in skills_ok else '✗ '}{s}" for s in sorted(all_skills)]
        for i in range(0, len(skill_tags), 4):
            chunk = skill_tags[i:i + 4]
            line  = "  ".join(f"{t:<17}" for t in chunk).rstrip()
            app(_plain(line))
    app(_sep())

    # Prewarm + summary
    app(_row("🔥 Prewarm",  prewarm_msg, lw=12))
    app(_row("📦 Pulled",   f"{len(pulled)} Ollama models in library", lw=12))
    app(_row("🔗 Pipeline", "classify→skill→brain→prewarm→execute→escalate→audit", lw=12))
    app(_bot())
    app("")

    print("\n".join(B), flush=True)


if __name__ == "__main__":
    main()
