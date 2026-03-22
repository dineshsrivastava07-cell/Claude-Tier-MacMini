# Claude-Tier-MacMini — DSR AI-Lab Tier Routing v9.1

**Production-grade AI orchestration for Claude CLI on Mac Mini.**

Every task is automatically routed to the optimal model via a LangGraph state machine.
**Claude = Brain only.** Ollama T1 models execute all code, files, and bash commands.
T2 models (Gemini / HuggingFace Kimi) provide analysis only — they never execute.

---

## What's New in v9.1

| Change | Detail |
|--------|--------|
| `startup_banner.py` | Replaces static echo hook — full live status banner on every `claude` start |
| Live per-model status | Each model shows `✅ LIVE (in RAM)` / `⚡ READY (on-demand)` / `✗ NOT PULLED` |
| LangSmith live check | API ping on startup — shows server version + SDK version + project name |
| LangGraph live check | Import + version check (`v1.1.3` confirmed) |
| TierEnforcer status | intercept.py ✅ + DB row count + server.py existence |
| 22 MCP servers verified | All server scripts checked on startup — any missing shown `✗` |
| 12 Skills verified | All skill `.md` files checked — missing files flagged |
| HF API fix | Uses `/api/whoami-v2` (deprecated `/api/whoami` always returns 401) |
| HF Pro account | Shows `✅ LIVE @DSR07 (Pro)` with plan + username |
| Settings env reading | `startup_banner.py` reads `HF_API_KEY` directly from `settings.json` |
| Auto-prewarm background | T1-LOCAL + T1-MID loaded to RAM in background thread on every start |
| Prewarm smart guard | Only prewarms models not already in RAM — skips if warm |

---

## Live Startup Banner (every `claude` session)

```
╔════════════════════════════════════════════════════════════════════════════╗
║             DSR AI-LAB — TIER ROUTING v9  |  FULL LIVE STATUS              ║
╠════════════════════════════════════════════════════════════════════════════╣
║  🧠 Claude      ✅ AUTH  OAuth via macOS Keychain                            ║
║    Bash        NATIVE  (not intercepted)                                   ║
║    Edit/Write  intercept.py → Ollama T1  (auto-routed)                     ║
╠════════════════════════════════════════════════════════════════════════════╣
║                               INFRASTRUCTURE                               ║
║  LangGraph   ✅ LIVE  v1.1.3  8-node pipeline active                        ║
║  LangSmith   ✅ LIVE  server=0.13.32  sdk=0.7.13  project=dsr-ai-lab-tier-v9║
║  TierEnforcer intercept ✅  DB ✅ (N routes logged)  server ✅               ║
╠════════════════════════════════════════════════════════════════════════════╣
║                  EXECUTORS — Ollama  (all code execution)                  ║
║  ⚙ T1-LOCAL  qwen2.5-coder:7b        ✅ LIVE (in RAM)                       ║
║  ⚙ T1-MID    qwen2.5-coder:14b       ✅ LIVE (in RAM)                       ║
║  ⚙ T1-CLOUD  qwen3-coder:480b-cloud  ⚡ READY (on-demand)                   ║
╠════════════════════════════════════════════════════════════════════════════╣
║                ANALYSIS — Gemini / HF  (never execute code)                ║
║  🔍 T2-FLASH  gemini-2.5-flash   ✅ LIVE  v0.33.0                            ║
║  🔍 T2-PRO    gemini-2.5-pro     ✅ LIVE  v0.33.0                            ║
║  🔍 T2-KIMI   Kimi-K2-Instruct   ✅ LIVE  @DSR07 (Pro)                       ║
╠════════════════════════════════════════════════════════════════════════════╣
║              MCP SERVERS (22)  —  ✅ 22 active  ✅ all present               ║
║  ✅tier-enforcer  ✅filesystem  ✅git  ✅memory  ✅github  ✅gdrive  ...        ║
╠════════════════════════════════════════════════════════════════════════════╣
║                        SKILLS (12)  —  ✅ all loaded                        ║
║  ✅aiapp  ✅arch  ✅math  ✅multifile  ✅rca  ✅scope  ✅tier-*  ✅wire          ║
╠════════════════════════════════════════════════════════════════════════════╣
║  🔥 Prewarm   ⏳ Loading 7b+14b → RAM (background)                          ║
║  📦 Pulled    9 Ollama models in library                                    ║
║  🔗 Pipeline  classify→skill→brain→prewarm→execute→escalate→audit           ║
╚════════════════════════════════════════════════════════════════════════════╝
```

---

## System Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                       DSR AI-Lab  Mac Mini                         │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Claude CLI  —  BRAIN ONLY                                 │   │
│  │  Bash = NATIVE  |  Edit/Write/MultiEdit = BLOCKED          │   │
│  │                                                            │   │
│  │  SessionStart Hook ──► startup_banner.py                   │   │
│  │    Live checks: Ollama + Gemini + HF + LangSmith +         │   │
│  │    LangGraph + TierEnforcer + 22 MCPs + 12 Skills          │   │
│  │    Auto-prewarms T1-LOCAL + T1-MID (background)            │   │
│  │                                                            │   │
│  │  PreToolUse Hook ──► intercept.py ──► Ollama T1            │   │
│  │    Intercepts: Edit | Write | MultiEdit | NotebookEdit     │   │
│  │    Passthrough: Bash (native)                              │   │
│  │                                                            │   │
│  │  tier-enforcer-mcp  (Python / FastMCP 3.1.0)               │   │
│  │  LangGraph 8 nodes: classify → skill_selector →            │   │
│  │  claude_brain → prewarm_check → [t2_analysis|t1_execute]   │   │
│  │  → escalate → audit                                        │   │
│  └────────────────────────────────────────────────────────────┘   │
│                              │                                     │
│          ┌───────────────────┼───────────────────┐                │
│          ▼                   ▼                   ▼                │
│  ┌──────────────┐  ┌───────────────┐  ┌─────────────────┐        │
│  │  T1-LOCAL    │  │   T1-MID      │  │   T1-CLOUD      │        │
│  │ qwen2.5:7b   │  │ qwen2.5:14b   │  │ qwen3:480b-cloud│        │
│  │ Ollama local │  │ Ollama local  │  │  Ollama cloud   │        │
│  │   4.7 GB     │  │   9.0 GB      │  │  (remote GPU)   │        │
│  │  EXECUTES    │  │  EXECUTES     │  │    EXECUTES     │        │
│  └──────────────┘  └───────────────┘  └─────────────────┘        │
│                                                                    │
│  ┌──────────────┐  ┌───────────────┐  ┌─────────────────┐        │
│  │   T2-FLASH   │  │   T2-PRO      │  │    T2-KIMI      │        │
│  │gemini-2.5-   │  │ gemini-2.5-pro│  │ Kimi-K2-Instruct│        │
│  │flash         │  │               │  │  HF Inference   │        │
│  │ ANALYSIS ──► T1-MID executes ◄───────── ANALYSIS     │        │
│  └──────────────┘  └───────────────┘  └─────────────────┘        │
└────────────────────────────────────────────────────────────────────┘
```

---

## Tier Reference

| Tier | Model | Role | Host | RAM |
|------|-------|------|------|-----|
| T1-LOCAL | qwen2.5-coder:7b | executor — simple/fast | Ollama localhost:11434 | 4.7 GB |
| T1-MID | qwen2.5-coder:14b | executor — complex code | Ollama localhost:11434 | 9.0 GB |
| T1-CLOUD | qwen3-coder:480b-cloud | executor — epic/greenfield | Ollama cloud | cloud |
| T2-FLASH | gemini-2.5-flash | analysis → T1-MID executes | Gemini CLI v0.33.0 | — |
| T2-PRO | gemini-2.5-pro | deep review → T1-MID executes | Gemini CLI v0.33.0 | — |
| T2-KIMI | Qwen/Kimi-K2-Instruct | math/algo → T1-MID executes | HF Inference API (Pro) | — |

---

## LangGraph Pipeline (8 Nodes)

```
Input Task
    │
    ▼
┌─────────────┐
│  classify   │  Keyword scan → tier assignment
└──────┬──────┘
       ▼
┌──────────────────┐
│  skill_selector  │  Load domain skill file into context
└──────┬───────────┘
       ▼
┌──────────────┐
│ claude_brain │  Claude writes execution plan (runs for EVERY tier)
└──────┬───────┘
       ▼
┌───────────────┐
│ prewarm_check │  Verify T1 models are loaded in Ollama RAM
└──────┬────────┘
       │
   ┌───┴────────────────────────┐
   │                            │
   ▼ (if T2 classified)         ▼ (T1 classified)
┌────────────┐          ┌──────────────┐
│ t2_analysis│          │  t1_execute  │
│ Gemini/Kimi│──────►   │  Ollama T1   │
└────────────┘          └──────┬───────┘
                               ▼
                        ┌─────────────┐
                        │  escalate   │  score < threshold → next tier (max 2x)
                        └──────┬──────┘
                               ▼
                        ┌─────────────┐
                        │    audit    │  Write to routing_log (11 cols)
                        └──────┬──────┘
                               ▼
                              END
```

---

## Task Classification → Routing

```
Incoming Task Text
        │
        ▼ keyword scan (priority order)
        │
        ├─ "debug" / "error" / "failing" / "broken" / "traceback"
        │         └──► T2-FLASH  (gemini-flash analyzes → T1-MID executes)
        │
        ├─ "analyze" / "explain" / "review" / "audit entire"
        │         └──► T2-PRO    (gemini-pro reviews   → T1-MID executes)
        │
        ├─ "algorithm" / "math" / "big-o" / "statistical"
        │         └──► T2-KIMI   (Kimi-K2 reasons      → T1-MID executes)
        │
        ├─ "full platform" / "greenfield" / "complete system" / "end to end"
        │         └──► T1-CLOUD  (qwen3-coder:480b-cloud executes directly)
        │
        ├─ "implement" / "write module" / "refactor" / "integrate"
        │         └──► T1-MID    (qwen2.5-coder:14b executes)
        │
        └─ everything else (default)
                  └──► T1-LOCAL  (qwen2.5-coder:7b executes)
```

---

## Intercept Flow (Edit/Write Protection)

```
Claude Brain produces plan
         │
         ▼
  Claude attempts tool call
         │
         ├──[Bash]──────────────────────────► NATIVE EXEC (passthrough)
         │
         └──[Edit | Write | MultiEdit | NotebookEdit]
                    │
                    ▼
             intercept.py  (PreToolUse hook)
                    │
                    ▼
         Route to Ollama T1 model
         POST /api/chat  (keep_alive=-1)
                    │
                    ▼
         Ollama generates + writes file/edit
                    │
                    ▼
         Claude is blocked — did NOT write
```

---

## Startup Sequence

```
Terminal opens
      │
      ▼ (zshrc / Login Item)
claude-ollama-prewarm.sh
  ├─ GET /api/ps → models loaded?
  ├─ If cold: POST /api/chat 7b + 14b  keep_alive=-1  (background)
  └─ Log to ~/.tier-enforcer/prewarm.log

      │
      ▼  user types: claude
Claude CLI authenticates
  ├─ macOS Keychain: "Claude Code-credentials" → OAuth sk-ant-oat01-...
  └─ claude.ai subscription verified

      │
      ▼  settings.json loaded
  ├─ 22 MCP servers spawned via stdio
  ├─ PreToolUse hook: intercept.py registered
  └─ CLAUDE.md brain protocol loaded

      │
      ▼  SessionStart hook fires → startup_banner.py
  Parallel threads (max 6s):
  ├─ Claude OAuth     → macOS Keychain check
  ├─ LangGraph        → import check + version
  ├─ LangSmith        → GET api.smith.langchain.com/info
  ├─ TierEnforcer     → intercept.py + DB + server.py
  ├─ Ollama           → GET /api/tags + /api/ps per-model
  ├─ Gemini CLI       → gemini --version
  ├─ HF API           → GET /api/whoami-v2 (not whoami — that's broken)
  ├─ 22 MCP servers   → each script/command existence
  ├─ 12 Skills        → each .md file existence
  └─ Auto-prewarm bg  → 7b + 14b if not in RAM

  FULL LIVE BANNER printed with actual statuses

      │
      ▼  mandatory MCP calls (CLAUDE.md protocol)
  activate_tier_routing()   → LangGraph 8 nodes compiled
  tier_health_check(ALL)    → live tier status map
  prewarm_models()          → confirm 7b + 14b in Ollama RAM

      │
      ▼
  READY — every task routed through execute_task()
```

---

## Fallback / Escalation Chain

```
T1-LOCAL ──(score<0.45)──► T1-MID ──(score<0.55)──► T1-CLOUD
                                                          │
                                                   (score<0.60)
                                                          ▼
T2-KIMI ◄──(score<0.50)── T2-PRO ◄──(score<0.50)── T2-FLASH
   │
(max 2 fallbacks reached → return best result obtained)
```

---

## Files

| File | Purpose |
|------|---------|
| `tier-enforcer-mcp/server.py` | FastMCP 3.1.0, LangGraph 8 nodes, SQLite audit |
| `tier-enforcer-mcp/intercept.py` | PreToolUse hook — Edit/Write → Ollama |
| `tier-enforcer-mcp/startup_banner.py` | **NEW v9.1** — full live status banner on session start |
| `tier-enforcer-mcp/langgraph_tier.py` | LangGraph state + node definitions |
| `dotfiles/CLAUDE.md` | Brain protocol v9 — startup calls, tier rules |
| `dotfiles/settings.json` | Hooks + 22 MCP servers + env vars |
| `dotfiles/settings.local.json` | SessionStart hook → startup_banner.py |

---

## 22 MCP Servers

| Category | Servers |
|----------|---------|
| Core | tier-enforcer, filesystem, git, memory, github, gdrive |
| Dev | intent-mcp, arch-mcp, coding-mcp, rca-mcp, integration-mcp, aidev-mcp, math-mcp |
| Domain | budget-mcp, context-mcp, rpa-mcp |
| Platform | mobile-dev-mcp, webmobile-dev-mcp, website-dev-mcp, ecommerce-mcp |
| Automation | mac-automation-mcp, files-automation-mcp |

---

## 12 Skills (`~/.claude/skills/`)

`aiapp` · `arch` · `math` · `multifile` · `rca` · `scope` · `tier-audit` · `tier-debug` · `tier-health` · `tier-report` · `tier-reset` · `wire`

---

## Environment Variables

```bash
# Set in ~/.claude/settings.json → mcpServers.tier-enforcer.env
OLLAMA_LOCAL_HOST=http://localhost:11434
OLLAMA_CLOUD_HOST=http://localhost:11434
OLLAMA_TIMEOUT_LOCAL=600
OLLAMA_TIMEOUT_MID=600
OLLAMA_TIMEOUT_CLOUD=600
HF_API_KEY=hf_...                  # HuggingFace read token (whoami-v2 verified)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=dsr-ai-lab-tier-v9
```

---

## Quick Setup

```bash
git clone https://github.com/dineshsrivastava07-cell/Claude-Tier-MacMini.git
cd Claude-Tier-MacMini

# Python dependencies
pip install fastmcp langgraph langchain-core huggingface_hub langsmith

# TypeScript tier-router-mcp
npm install && npm run build

# Copy dotfiles
cp dotfiles/CLAUDE.md ~/.claude/CLAUDE.md
cp dotfiles/settings.json ~/.claude/settings.json
cp dotfiles/settings.local.json ~/.claude/settings.local.json

# Copy tier-enforcer-mcp
mkdir -p ~/tier-enforcer-mcp
cp tier-enforcer-mcp/*.py ~/tier-enforcer-mcp/
cp tier-enforcer-mcp/*.sh ~/tier-enforcer-mcp/

# Set API keys in ~/.claude/settings.json
#   HF_API_KEY        = HuggingFace token with read scope
#   LANGCHAIN_API_KEY = LangSmith token (in env, not in settings.json)

# Authenticate Claude
claude auth login   # OAuth → macOS Keychain

# Start
claude
# startup_banner.py fires automatically — full live status shown
```

---

## v9 → v9.1 Changes

| Aspect | v9 | v9.1 |
|--------|----|------|
| Startup banner | Static echo one-liner | `startup_banner.py` — real parallel live checks |
| Model status | Binary Ollama ✓/✗ | Per-model: `✅ LIVE` / `⚡ READY` / `✗ NOT PULLED` |
| LangSmith | Not shown | Live API ping — server + SDK version |
| LangGraph | Not shown | Import + version |
| TierEnforcer | Not shown | intercept.py + DB rows + server.py |
| MCP status | Not shown | All 22 verified on startup |
| Skills status | Not shown | All 12 verified on startup |
| HF endpoint | `/api/whoami` (401) | `/api/whoami-v2` (correct) |
| HF key source | env only | Reads `settings.json` directly |
| Prewarm | External script only | Background thread in `startup_banner.py` |

---

*DSR AI-Lab — Mac Mini — v9.1 — 2026-03-22*
