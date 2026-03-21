# Claude-Tier-MacMini — DSR AI-Lab Tier Routing v9

**Production-grade dual-MCP AI orchestration system for Claude CLI on Mac Mini.**

Routes every task to the optimal AI model automatically via LangGraph state machine. Claude acts as **Brain only** — Ollama T1 models execute all code, files, and bash commands.

---

## What's New in v9

| Change | Detail |
|--------|--------|
| T3-EPIC removed | Was redundant — `claude_brain` node already plans every task |
| Epic tasks | Now route directly to **T1-CLOUD** (qwen3-coder:480b-cloud) |
| LangGraph nodes | Reduced from 9 → 8 (removed `t3_plan`) |
| MODEL_T1_CLOUD | Fixed to `qwen3-coder:480b-cloud` (was `qwen3-coder:480b`) |
| keep_alive=-1 | Added to all 3 Ollama tiers — models stay in RAM |
| DB schema | `routing_log` expanded to 11 columns (`elapsed`, `skills`, `brain_used`) |
| Pydantic warning | Suppressed at startup (Python 3.14 + langchain_core shim) |
| Prewarm guard | Checks `/api/ps` before loading — prevents duplicate model processes |
| Watchdog | Single instance enforced — kills duplicates automatically |
| Auth | OAuth via macOS Keychain (sk-ant-oat01-...) — API key removed from env |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     DSR AI-Lab Mac Mini                         │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Claude CLI (Brain — Bash/Edit/Write DISABLED)           │  │
│  │                                                          │  │
│  │  tier-enforcer-mcp  ←──── PreToolUse Hook               │  │
│  │  (Python/FastMCP)         Edit/Write/MultiEdit           │  │
│  │  LangGraph 8 nodes        → intercept.py → Ollama        │  │
│  │                                                          │  │
│  │  tier-router-mcp ──────────────────────────────────────► │  │
│  │  (TypeScript/Node)   18 MCP Tools + Pipelines            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│              ┌───────────────┼───────────────┐                  │
│              ▼               ▼               ▼                  │
│     ┌──────────────┐ ┌─────────────┐ ┌──────────────┐         │
│     │   T1-LOCAL   │ │   T1-MID    │ │  T1-CLOUD    │         │
│     │qwen2.5:7b    │ │qwen2.5:14b  │ │qwen3:480b    │         │
│     │ Ollama local │ │ Ollama local│ │ Ollama cloud │         │
│     │  EXECUTES    │ │  EXECUTES   │ │  EXECUTES    │         │
│     └──────────────┘ └─────────────┘ └──────────────┘         │
│                                                                 │
│     ┌──────────────┐ ┌─────────────┐ ┌──────────────┐         │
│     │   T2-FLASH   │ │   T2-PRO    │ │   T2-KIMI    │         │
│     │gemini-2.5-   │ │gemini-2.5-  │ │Kimi-K2-      │         │
│     │flash         │ │pro          │ │Instruct      │         │
│     │ ANALYSIS     │ │ ANALYSIS    │ │ ANALYSIS     │         │
│     │ only         │ │ only        │ │ only         │         │
│     └──────────────┘ └─────────────┘ └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

**Key principle:** T2 tiers **analyze only** — their output enriches the T1 prompt. T1 always executes.

---

## Tier Reference

| Tier | Model | Role | Execution | RAM |
|------|-------|------|-----------|-----|
| T1-LOCAL | qwen2.5-coder:7b | executor | Ollama localhost:11434 | 4.7 GB |
| T1-MID | qwen2.5-coder:14b | executor | Ollama localhost:11434 | 9.0 GB |
| T1-CLOUD | qwen3-coder:480b-cloud | executor (epic) | Ollama cloud | cloud |
| T2-FLASH | gemini-2.5-flash | analysis → T1-MID | Gemini CLI | — |
| T2-PRO | gemini-2.5-pro | analysis → T1-MID | Gemini CLI | — |
| T2-KIMI | Qwen/Kimi-K2-Instruct | analysis → T1-MID | HF Inference API | — |

---

## Dual MCP Components

### 1. tier-enforcer-mcp (`tier-enforcer/server.py`)
- **Framework:** FastMCP 3.1.0 (Python)
- **Scope:** Claude CLI global (`~/.claude/settings.json`)
- **Role:** LangGraph orchestrator — classify, brain, route, audit
- **Hook:** `PreToolUse → Edit|Write|MultiEdit|NotebookEdit → intercept.py → Ollama`
- **DB:** `~/.tier-enforcer/memory.db` SQLite — 11-column `routing_log`

### 2. tier-router-mcp (`src/`)
- **Framework:** TypeScript, ESM, Node 20+
- **Scope:** User-level auto-start
- **Role:** 18 MCP tools — direct T1/T2/T3 calls + pipeline chains
- **Resources:** `tier://config`, `tier://metrics`, `tier://routing-log`

---

## LangGraph Pipeline (8 Nodes)

```
classify → skill_selector → claude_brain → prewarm_check
                                                 │
                           ┌─────────────────────┤
                           ▼                     ▼
                    t2_analysis           t1_execute
                  (Gemini/Kimi)          (Ollama T1)
                           └─────────────────────┘
                                         │
                                    escalate → audit → END
```

| Node | Role |
|------|------|
| `classify` | Keyword-based tier classification |
| `skill_selector` | Loads domain skill context |
| `claude_brain` | Claude plans the execution approach — runs for EVERY tier |
| `prewarm_check` | Verifies T1 models are in Ollama RAM |
| `t2_analysis` | Gemini/Kimi analysis (enriches T1 prompt) |
| `t1_execute` | Ollama runs the task (bash/files/code) |
| `escalate` | Fallback to next tier if score below threshold |
| `audit` | Writes result to SQLite routing_log (11 cols) |

---

## Classifier Rules

| Task Signal | → Tier | Examples |
|------------|--------|---------|
| debug / error / failing / broken / traceback | T2-FLASH | "debug this error", "test failing" |
| analyze / explain / review | T2-PRO | "explain this architecture" |
| reason / complex logic | T2-KIMI | "reason through this algorithm" |
| greenfield / epic / full platform | T1-CLOUD | "build complete ecommerce platform" |
| moderate / write module | T1-MID | "write this module" |
| simple / rename / utility | T1-LOCAL | "rename this function" |

---

## Task Routing Flow

```
User sends task
       │
       ▼
[Claude Brain — classify]
       │
       ├──► T1-LOCAL  → Ollama qwen2.5-coder:7b  → executes
       ├──► T1-MID    → Ollama qwen2.5-coder:14b → executes
       ├──► T1-CLOUD  → Ollama qwen3-coder:480b-cloud → executes
       ├──► T2-FLASH  → gemini-2.5-flash analyzes → T1-MID executes
       ├──► T2-PRO    → gemini-2.5-pro analyzes   → T1-MID executes
       └──► T2-KIMI   → Kimi-K2 analyzes          → T1-MID executes
```

---

## Intercept Flow (Edit/Write Protection)

```
Claude attempts: Edit | Write | MultiEdit | NotebookEdit
                              │
                              ▼
                     intercept.py (PreToolUse hook)
                              │
                    ┌─────────┴──────────┐
                    │                    │
              Bash tool             Edit/Write/etc.
                    │                    │
              PASSTHROUGH         Route to Ollama T1
              (native exec)       → file written by model
```

Bash runs natively. File ops always go through Ollama — Claude cannot write files directly.

---

## Session Startup Sequence

```
1. Terminal opens
   → zshrc: guarded prewarm (checks /api/ps → loads 7b+14b only if cold)
   → zshrc: watchdog starts (single instance guard)

2. User types: claude
   → macOS Keychain → OAuth token (sk-ant-oat01-...) → claude.ai subscription
   → settings.json → 22 MCP servers + hooks
   → CLAUDE.md → brain protocol v8

3. Mandatory startup calls:
   → activate_tier_routing()   LangGraph 8 nodes compiled
   → tier_health_check()       all tiers verified
   → prewarm_models()          7b + 14b confirmed IN RAM

4. STARTUP BANNER shown with live model status
```

---

## tier-router-mcp Tools (18)

### Routing Tools
| Tool | Description |
|------|-------------|
| `tier_route_task` | Auto-route with quality-gate fallback |
| `tier_health_check` | Probe all tier availability |
| `tier_explain_decision` | Classify prompt — dry run |
| `tier_override` | Force a specific tier |

### T1 Tools (Ollama)
| Tool | Model |
|------|-------|
| `t1_local_generate` | qwen2.5-coder:7b |
| `t1_local_complete` | qwen2.5-coder:7b — fill-in-the-middle |
| `t1_cloud_generate` | qwen3-coder:480b-cloud |
| `t1_cloud_analyze` | qwen3-coder:480b-cloud — audit |

### T2 Tools (Gemini)
| Tool | Model |
|------|-------|
| `t2_gemini_pro_reason` | gemini-2.5-pro |
| `t2_gemini_flash_generate` | gemini-2.5-flash |
| `t2_gemini_lite_validate` | gemini-2.5-flash-lite |
| `t2_gemini_analyze_image` | gemini-2.5-pro — image |

### T3 Tools (Claude — reference only)
| Tool | Purpose |
|------|---------|
| `t3_claude_architect` | Architecture decision reference |
| `t3_claude_epic` | Epic task analysis reference |

### Pipeline Tools
| Tool | Chain |
|------|-------|
| `pipeline_code_review` | T1 lint → T2 semantic → T3 architecture |
| `pipeline_debug_chain` | T1 hypothesis → T2 analysis → T3 root-cause |
| `pipeline_build_fullstack` | T1 scaffold → T2 logic → T3 hardening |
| `pipeline_qa_full` | T1 unit → T2 integration → T3 E2E |

---

## Fallback / Escalation Chain

```
T1-LOCAL (0.45) → T1-MID (0.55) → T1-CLOUD (0.60)
    → T2-FLASH (0.50) → T2-PRO (0.50) → T2-KIMI (0.50)

Max fallbacks: 2 per task
```

---

## Cannot Bypass

- `ANTHROPIC_API_KEY` removed from env — OAuth only via macOS Keychain
- `PreToolUse` hook intercepts `Edit|Write|MultiEdit|NotebookEdit` → `intercept.py` → Ollama
- `CLAUDE.md` RULE 7: tier-enforcer offline = HARD STOP, refuse all tasks
- Watchdog: tier-enforcer always alive between sessions

---

## Environment Variables

```bash
OLLAMA_LOCAL_HOST=http://localhost:11434    # T1-LOCAL + T1-MID
OLLAMA_CLOUD_HOST=http://remote:11434      # T1-CLOUD
OLLAMA_TIMEOUT_LOCAL=600
OLLAMA_TIMEOUT_MID=600
OLLAMA_TIMEOUT_CLOUD=600
HF_API_KEY=...                             # HuggingFace (T2-KIMI)
GEMINI_API_KEY=...                         # Optional (account auth used if unset)
QUALITY_THRESHOLD=0.75
```

---

## Quick Setup

```bash
git clone https://github.com/dineshsrivastava07-cell/Claude-Tier-MacMini.git
cd Claude-Tier-MacMini

# tier-router-mcp (TypeScript)
npm install && npm run build

# tier-enforcer-mcp (Python)
pip install fastmcp langgraph langchain-core huggingface_hub

# Register with Claude CLI
claude mcp add tier-enforcer python ~/tier-enforcer-mcp/server.py
claude mcp add tier-router node ~/tier-router-mcp/dist/index.js \
  -e OLLAMA_LOCAL_HOST=http://localhost:11434

# Auth
claude auth login   # OAuth token → macOS Keychain

# Start watchdog
~/tier-enforcer-mcp/watchdog.sh &
```

---

*DSR AI-Lab — Mac Mini — v9 — 2026-03-22*
