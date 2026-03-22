# DSR AI-Lab Tier Routing v9.1 — Architecture

**Version:** v9.1 | **Date:** 2026-03-22 | **Repo:** Claude-Tier-MacMini

---

## System Overview

DSR AI-Lab Tier Routing is a production AI orchestration system for Claude CLI on Mac Mini.
Claude acts as **Brain only** — classifies, plans, routes. Ollama T1 models execute all code
and file writes. T2 models (Gemini / Kimi) analyze and enrich prompts — they never execute.

Every Claude session fires `startup_banner.py` which live-checks all 6 models, LangSmith,
LangGraph, TierEnforcer DB, 22 MCP servers, and 12 Skills in parallel — auto-prewarming
T1-LOCAL and T1-MID in background.

---

## High-Level Architecture

```mermaid
graph TD
    User([User Task]) --> ClaudeBrain

    subgraph ClaudeBrain["Claude CLI — Brain Only"]
        SH[SessionStart Hook<br/>startup_banner.py<br/>Live checks + auto-prewarm]
        PH[PreToolUse Hook<br/>intercept.py<br/>Edit/Write → Ollama]
        TE[tier-enforcer-mcp<br/>FastMCP 3.1.0 · Python<br/>LangGraph 8 nodes]
        SH -.->|fires on start| TE
        PH -->|file ops| TE
    end

    TE --> T1L[T1-LOCAL<br/>qwen2.5-coder:7b<br/>4.7GB · localhost]
    TE --> T1M[T1-MID<br/>qwen2.5-coder:14b<br/>9.0GB · localhost]
    TE --> T1C[T1-CLOUD<br/>qwen3-coder:480b-cloud<br/>Ollama cloud]
    TE --> T2F[T2-FLASH<br/>gemini-2.5-flash<br/>Analysis only]
    TE --> T2P[T2-PRO<br/>gemini-2.5-pro<br/>Analysis only]
    TE --> T2K[T2-KIMI<br/>Kimi-K2-Instruct<br/>HF API · Pro]

    T2F -->|enriched prompt| T1M
    T2P -->|enriched prompt| T1M
    T2K -->|enriched prompt| T1M

    TE <-->|tracing| LS[LangSmith<br/>api.smith.langchain.com<br/>project: dsr-ai-lab-tier-v9]
    TE <-->|state machine| LG[LangGraph v1.1.3<br/>8-node pipeline]

    style ClaudeBrain fill:#1a1a2e,color:#fff
    style T1L fill:#457b9d,color:#fff
    style T1M fill:#457b9d,color:#fff
    style T1C fill:#e63946,color:#fff
    style T2F fill:#f4a261,color:#000
    style T2P fill:#f4a261,color:#000
    style T2K fill:#f4a261,color:#000
    style LS fill:#2d6a4f,color:#fff
    style LG fill:#2d6a4f,color:#fff
```

---

## Startup Banner Flow

```mermaid
sequenceDiagram
    participant SH as SessionStart Hook
    participant BP as startup_banner.py
    participant OL as Ollama /api/ps + /api/tags
    participant GE as gemini --version
    participant HF as HF /api/whoami-v2
    participant LS as LangSmith API
    participant LG as LangGraph import
    participant TE as TierEnforcer files+DB
    participant FS as Skills + MCP scripts
    participant RAM as Ollama RAM (prewarm bg)

    SH->>BP: python3 startup_banner.py
    BP->>OL: GET /api/tags + /api/ps (parallel)
    BP->>GE: subprocess gemini --version (parallel)
    BP->>HF: GET /api/whoami-v2 (parallel)
    BP->>LS: GET api.smith.langchain.com/info (parallel)
    BP->>LG: import langgraph.graph (parallel)

    OL-->>BP: pulled=[7b,14b,480b,...] loaded=[7b,14b]
    GE-->>BP: 0.33.0
    HF-->>BP: {name:DSR07, isPro:true}
    LS-->>BP: {version:0.13.32}
    LG-->>BP: v1.1.3

    BP->>TE: check intercept.py + memory.db + server.py
    BP->>FS: check 22 MCP scripts + 12 skill .md files
    TE-->>BP: intercept✅ DB✅(10 rows) server✅
    FS-->>BP: 22/22 MCPs present · 12/12 skills present

    BP->>RAM: Thread: prewarm 7b+14b if not in RAM (background)

    BP->>SH: Print FULL LIVE BANNER (all statuses real data)
```

---

## LangGraph State Machine (8 Nodes)

```mermaid
flowchart TD
    IN([Task Input]) --> CL[classify<br/>keyword scan → tier]
    CL --> SK[skill_selector<br/>load domain skill]
    SK --> CB[claude_brain<br/>Claude writes execution plan<br/>runs for EVERY tier]
    CB --> PC[prewarm_check<br/>verify T1 models in Ollama RAM]

    PC --> RT{Route?}
    RT -->|T2-FLASH / T2-PRO / T2-KIMI| T2[t2_analysis<br/>Gemini-flash / Gemini-pro / Kimi-K2<br/>returns structured analysis]
    RT -->|T1-LOCAL / T1-MID / T1-CLOUD| EX

    T2 -->|enriched prompt| EX[t1_execute<br/>Ollama T1 model runs task<br/>keep_alive=-1]

    EX --> ES{escalate<br/>score ≥ threshold?}
    ES -->|Yes| AU[audit<br/>write routing_log<br/>11 cols · SQLite]
    ES -->|No - fallback| EX

    AU --> OUT([Result])

    style IN fill:#555,color:#fff
    style OUT fill:#555,color:#fff
    style CB fill:#4a4a8a,color:#fff
    style T2 fill:#f4a261,color:#000
    style EX fill:#457b9d,color:#fff
    style ES fill:#e63946,color:#fff
    style AU fill:#2d6a4f,color:#fff
```

| Node | Responsibility |
|------|---------------|
| `classify` | Keyword scan → assign tier (T1-LOCAL / T1-MID / T1-CLOUD / T2-FLASH / T2-PRO / T2-KIMI) |
| `skill_selector` | Load matching skill `.md` file into context from `~/.claude/skills/` |
| `claude_brain` | Claude writes step-by-step execution plan — runs for **every** tier |
| `prewarm_check` | Verify 7b + 14b are in Ollama RAM; load if cold |
| `t2_analysis` | Gemini-flash / Gemini-pro / Kimi-K2 analyzes task → returns structured brief |
| `t1_execute` | Ollama runs task with brain plan + optional T2 analysis (`keep_alive=-1`) |
| `escalate` | Score < threshold → bump to next tier (max 2 fallbacks) |
| `audit` | Write row to `routing_log` (11 cols: ts, session, task, classified_tier, executor_tier, model, score, ok, elapsed, skills, brain_used) |

---

## Task Classification Flow

```mermaid
flowchart TD
    Task([Incoming Task]) --> KW{Keyword Scan<br/>priority order}

    KW -->|debug · error · failing<br/>broken · traceback| TF[T2-FLASH]
    KW -->|analyze · explain<br/>review · audit entire| TP[T2-PRO]
    KW -->|algorithm · math<br/>big-o · statistical| TK[T2-KIMI]
    KW -->|full platform · greenfield<br/>complete system · end to end| TC[T1-CLOUD]
    KW -->|implement · write module<br/>refactor · integrate| TM[T1-MID]
    KW -->|everything else — default| TL[T1-LOCAL]

    TF -->|analysis brief| TM2[T1-MID executes<br/>qwen2.5-coder:14b]
    TP -->|analysis brief| TM2
    TK -->|analysis brief| TM2
    TC --> OC[qwen3-coder:480b-cloud<br/>Ollama cloud]
    TM --> OM[qwen2.5-coder:14b<br/>Ollama local]
    TL --> OL[qwen2.5-coder:7b<br/>Ollama local]

    style TF fill:#f4a261,color:#000
    style TP fill:#f4a261,color:#000
    style TK fill:#f4a261,color:#000
    style TC fill:#e63946,color:#fff
    style TM fill:#457b9d,color:#fff
    style TL fill:#457b9d,color:#fff
    style TM2 fill:#457b9d,color:#fff
    style OC fill:#e63946,color:#fff
    style OM fill:#457b9d,color:#fff
    style OL fill:#457b9d,color:#fff
```

---

## Intercept / Hook Flow

```mermaid
sequenceDiagram
    participant U as User
    participant C as Claude Brain
    participant H as PreToolUse Hook
    participant I as intercept.py
    participant O as Ollama T1
    participant FS as File System

    U->>C: task request
    C->>C: classify + claude_brain plan
    C->>H: attempt tool call

    alt Bash tool
        H-->>C: continue=true  (passthrough — native exec)
    else Edit / Write / MultiEdit / NotebookEdit
        H->>I: intercept triggered
        I->>I: Is path ~/.claude/ or ~/tier-enforcer-mcp/?
        alt Internal path (passthrough)
            I-->>H: continue=true
        else User project file
            I->>O: POST /api/chat (task desc, keep_alive=-1)
            O->>I: generated content
            I->>FS: write file
            I-->>H: continue=false  (Claude blocked)
        end
    end
```

**Bash is always native.** Internal paths (`~/.claude/`, `~/tier-enforcer-mcp/`) passthrough.
All user project file writes go through Ollama — Claude physically cannot write them.

---

## Fallback / Escalation Chain

```mermaid
flowchart LR
    TL["T1-LOCAL<br/>qwen2.5-coder:7b<br/>threshold 0.45"]
    TM["T1-MID<br/>qwen2.5-coder:14b<br/>threshold 0.55"]
    TC["T1-CLOUD<br/>qwen3-coder:480b-cloud<br/>threshold 0.60"]
    TF["T2-FLASH<br/>gemini-2.5-flash<br/>threshold 0.50"]
    TP["T2-PRO<br/>gemini-2.5-pro<br/>threshold 0.50"]
    TK["T2-KIMI<br/>Kimi-K2-Instruct<br/>threshold 0.50"]
    END([best result])

    TL -->|score low| TM
    TM -->|score low| TC
    TC -->|score low| TF
    TF -->|score low| TP
    TP -->|score low| TK
    TK -->|max 2 fallbacks| END

    style TL fill:#457b9d,color:#fff
    style TM fill:#457b9d,color:#fff
    style TC fill:#e63946,color:#fff
    style TF fill:#f4a261,color:#000
    style TP fill:#f4a261,color:#000
    style TK fill:#f4a261,color:#000
```

---

## Full Session Startup Sequence

```mermaid
sequenceDiagram
    participant Z as zshrc / Login Item
    participant OL as Ollama
    participant C as Claude CLI
    participant K as macOS Keychain
    participant S as settings.json
    participant BP as startup_banner.py
    participant MCP as tier-enforcer-mcp
    participant LS as LangSmith

    Z->>OL: GET /api/ps — models loaded?
    alt Cold
        Z->>OL: POST /api/chat 7b keep_alive=-1 (bg)
        Z->>OL: POST /api/chat 14b keep_alive=-1 (bg)
    end

    Z->>C: user runs: claude

    C->>K: find "Claude Code-credentials"
    K-->>C: OAuth sk-ant-oat01-... (claude.ai subscription)

    C->>S: load settings.json
    S-->>C: 22 MCP servers + hooks + env vars

    C->>MCP: spawn server.py (stdio)
    MCP-->>C: FastMCP ready

    C->>BP: SessionStart hook fires
    BP->>BP: parallel checks (6s max)
    BP-->>C: FULL LIVE BANNER printed

    C->>MCP: activate_tier_routing(session_id)
    MCP->>MCP: compile LangGraph 8 nodes
    MCP-->>C: LANGGRAPH_HARD mode active

    C->>MCP: tier_health_check(tier=ALL)
    MCP-->>C: all tiers ONLINE

    C->>MCP: prewarm_models()
    MCP->>OL: verify 7b + 14b in RAM
    MCP-->>C: models confirmed warm

    C->>LS: trace session start
    LS-->>C: tracing active (project: dsr-ai-lab-tier-v9)

    C-->>Z: READY — execute_task() available
```

---

## Database Schema (`~/.tier-enforcer/memory.db`)

```sql
CREATE TABLE routing_log (
    ts              REAL,   -- Unix timestamp
    session         TEXT,   -- session UUID
    task            TEXT,   -- task text (first 120 chars)
    classified_tier TEXT,   -- tier classifier assigned (e.g. T2-FLASH)
    executor_tier   TEXT,   -- tier that actually executed (e.g. T1-MID)
    model           TEXT,   -- model name used
    score           REAL,   -- quality score 0.0–1.0
    ok              INTEGER,-- 1=success 0=failure
    elapsed         REAL,   -- total seconds
    skills          TEXT,   -- JSON array of matched skills
    brain_used      INTEGER -- 1=claude_brain ran
);
```

---

## MCP Servers (22 total)

```mermaid
graph LR
    subgraph Core
        TE[tier-enforcer]
        FS[filesystem]
        GIT[git]
        MEM[memory]
        GH[github]
        GD[gdrive]
    end

    subgraph Dev
        IN[intent-mcp]
        AR[arch-mcp]
        CO[coding-mcp]
        RC[rca-mcp]
        IT[integration-mcp]
        AI[aidev-mcp]
        MT[math-mcp]
    end

    subgraph Domain
        BU[budget-mcp]
        CT[context-mcp]
        RP[rpa-mcp]
    end

    subgraph Platform
        MO[mobile-dev-mcp]
        WM[webmobile-dev-mcp]
        WS[website-dev-mcp]
        EC[ecommerce-mcp]
    end

    subgraph Automation
        MA[mac-automation-mcp]
        FA[files-automation-mcp]
    end

    Claude --> Core
    Claude --> Dev
    Claude --> Domain
    Claude --> Platform
    Claude --> Automation
```

---

## Skills (12 total, `~/.claude/skills/`)

| Skill | Domain |
|-------|--------|
| `aiapp` | AI app development |
| `arch` | Architecture / ADR |
| `math` | Mathematics / algorithms |
| `multifile` | Multi-file implementation |
| `rca` | Root cause analysis / debugging |
| `scope` | Task scoping |
| `tier-audit` | Tier routing audit |
| `tier-debug` | Tier system debugging |
| `tier-health` | Tier health checks |
| `tier-report` | Routing report generation |
| `tier-reset` | Tier state reset |
| `wire` | Wiring / integration |

---

## Component Files

| File | Type | Purpose |
|------|------|---------|
| `tier-enforcer-mcp/server.py` | Python | FastMCP 3.1.0 · LangGraph 8 nodes · SQLite audit |
| `tier-enforcer-mcp/intercept.py` | Python | PreToolUse hook — Edit/Write → Ollama |
| `tier-enforcer-mcp/startup_banner.py` | Python | **v9.1** — live status banner + auto-prewarm |
| `tier-enforcer-mcp/langgraph_tier.py` | Python | LangGraph state + node definitions |
| `dotfiles/CLAUDE.md` | Markdown | Brain protocol v9 — startup calls + tier rules |
| `dotfiles/settings.json` | JSON | Hooks + 22 MCP servers + env vars |
| `dotfiles/settings.local.json` | JSON | SessionStart hook → startup_banner.py |
| `src/core/router.ts` | TypeScript | tier-router-mcp routing engine (18 tools) |

---

## v9 → v9.1 Architecture Changes

| Aspect | v9 | v9.1 |
|--------|----|------|
| Startup check | Static echo banner (no real checks) | `startup_banner.py` — 9 parallel live checks |
| Model status granularity | Binary Ollama up/down | Per-model: LIVE / READY / NOT PULLED |
| LangSmith | Config only, not verified | Live API ping on every start |
| LangGraph | Assumed available | Import + version verified on every start |
| TierEnforcer health | Not shown at startup | intercept.py + DB row count + server.py |
| MCP server health | Not verified | All 22 script paths checked |
| Skills health | Not verified | All 12 `.md` files checked |
| HF API endpoint | `/api/whoami` (deprecated — always 401) | `/api/whoami-v2` (correct endpoint) |
| HF key loading | `os.environ` only (broken for hooks) | Reads `settings.json` mcpServers env directly |
| Prewarm trigger | Only from zshrc/Login Item | Also from `startup_banner.py` background thread |

---

*DSR AI-Lab — Mac Mini — Architecture v9.1 — 2026-03-22*
