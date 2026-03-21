# DSR AI-Lab Tier Routing v9 — Architecture

**Version:** v9 | **Date:** 2026-03-22 | **Repo:** Claude-Tier-MacMini

---

## System Overview

DSR AI-Lab Tier Routing is a dual-MCP AI orchestration system. Claude acts as **Brain only** — it classifies, plans, and routes. Ollama T1 models execute all code, file writes, and bash commands. T2 models (Gemini/Kimi) provide analysis that enriches T1 prompts — they never execute directly.

---

## High-Level Architecture

```mermaid
graph TD
    User([User Task]) --> ClaudeBrain[Claude CLI<br/>Brain Only<br/>Bash/Edit/Write DISABLED]

    ClaudeBrain --> TierEnforcer[tier-enforcer-mcp<br/>Python / FastMCP 3.1.0<br/>LangGraph 8 Nodes]
    ClaudeBrain --> TierRouter[tier-router-mcp<br/>TypeScript / Node 20+<br/>18 MCP Tools]

    TierEnforcer --> T1L[T1-LOCAL<br/>qwen2.5-coder:7b<br/>Ollama local 4.7GB]
    TierEnforcer --> T1M[T1-MID<br/>qwen2.5-coder:14b<br/>Ollama local 9.0GB]
    TierEnforcer --> T1C[T1-CLOUD<br/>qwen3-coder:480b-cloud<br/>Ollama cloud]
    TierEnforcer --> T2F[T2-FLASH<br/>gemini-2.5-flash<br/>Analysis only]
    TierEnforcer --> T2P[T2-PRO<br/>gemini-2.5-pro<br/>Analysis only]
    TierEnforcer --> T2K[T2-KIMI<br/>Kimi-K2-Instruct<br/>Analysis only]

    T2F -->|enriched prompt| T1M
    T2P -->|enriched prompt| T1M
    T2K -->|enriched prompt| T1M

    TierRouter --> T1L
    TierRouter --> T1C
    TierRouter --> T2F
    TierRouter --> T2P

    style ClaudeBrain fill:#4a4a8a,color:#fff
    style TierEnforcer fill:#2d6a4f,color:#fff
    style TierRouter fill:#1d3557,color:#fff
    style T1L fill:#457b9d,color:#fff
    style T1M fill:#457b9d,color:#fff
    style T1C fill:#e63946,color:#fff
    style T2F fill:#f4a261,color:#000
    style T2P fill:#f4a261,color:#000
    style T2K fill:#f4a261,color:#000
```

---

## LangGraph State Machine (8 Nodes)

```mermaid
flowchart LR
    A([Task Input]) --> B[classify]
    B --> C[skill_selector]
    C --> D[claude_brain]
    D --> E[prewarm_check]

    E --> F{Route?}
    F -->|T2 path| G[t2_analysis<br/>Gemini / Kimi]
    F -->|T1 path| H[t1_execute<br/>Ollama]

    G --> H
    H --> I[escalate]
    I -->|score OK| J[audit]
    I -->|score low| H
    J --> K([END])

    style A fill:#555,color:#fff
    style K fill:#555,color:#fff
    style D fill:#4a4a8a,color:#fff
    style G fill:#f4a261,color:#000
    style H fill:#457b9d,color:#fff
    style I fill:#e63946,color:#fff
```

| Node | Responsibility |
|------|---------------|
| `classify` | Keyword scan → assign tier (T1-LOCAL / T1-MID / T1-CLOUD / T2-FLASH / T2-PRO / T2-KIMI) |
| `skill_selector` | Load domain skill file into context (e.g. retail-analytics, cybersecurity) |
| `claude_brain` | Claude writes execution plan — runs for EVERY tier |
| `prewarm_check` | Verify 7b + 14b models are loaded in Ollama RAM |
| `t2_analysis` | Gemini-flash / Gemini-pro / Kimi-K2 analyzes task, returns structured analysis |
| `t1_execute` | Ollama runs task using T1 model + claude_brain plan + optional T2 analysis |
| `escalate` | If quality score < threshold → bump to next tier (max 2 fallbacks) |
| `audit` | Write row to `routing_log` (11 cols: ts, session, task, classified_tier, executor_tier, model, score, ok, elapsed, skills, brain_used) |

---

## Task Classification Flow

```mermaid
flowchart TD
    Task([Incoming Task]) --> KW{Keyword Scan}

    KW -->|debug / error / failing / broken / traceback| TF[T2-FLASH]
    KW -->|analyze / explain / review / assess| TP[T2-PRO]
    KW -->|reason / infer / logic / deduce| TK[T2-KIMI]
    KW -->|greenfield / epic / full platform / complete system| TC[T1-CLOUD]
    KW -->|moderate / write module / implement feature| TM[T1-MID]
    KW -->|simple / rename / fix typo / utility| TL[T1-LOCAL]

    TF -->|analysis| TM2[T1-MID executes]
    TP -->|analysis| TM2
    TK -->|analysis| TM2
    TC --> OC[Ollama qwen3-coder:480b-cloud]
    TM --> OM[Ollama qwen2.5-coder:14b]
    TL --> OL[Ollama qwen2.5-coder:7b]

    style TF fill:#f4a261,color:#000
    style TP fill:#f4a261,color:#000
    style TK fill:#f4a261,color:#000
    style TC fill:#e63946,color:#fff
    style TM fill:#457b9d,color:#fff
    style TL fill:#457b9d,color:#fff
    style OC fill:#e63946,color:#fff
    style OM fill:#457b9d,color:#fff
    style OL fill:#457b9d,color:#fff
```

---

## Intercept / Hook Flow (Edit/Write Protection)

```mermaid
sequenceDiagram
    participant U as User
    participant C as Claude Brain
    participant H as PreToolUse Hook
    participant I as intercept.py
    participant O as Ollama T1
    participant FS as File System

    U->>C: Give me a task
    C->>C: Plan with claude_brain
    C->>H: Attempt Edit/Write/MultiEdit

    H->>I: Intercept triggered
    I->>I: tool_name in OLLAMA_TOOLS?

    alt Bash command
        I-->>H: continue: true (passthrough)
        H-->>C: native execution
    else Edit / Write / MultiEdit
        I->>O: POST /api/generate (task description)
        O->>I: generated file content
        I->>FS: Write file
        I-->>H: continue: false (blocked Claude)
    end
```

**Bash is native passthrough.** Edit/Write/MultiEdit/NotebookEdit always go through Ollama — Claude physically cannot write files directly.

---

## Fallback / Escalation Chain

```mermaid
flowchart LR
    TL[T1-LOCAL<br/>threshold 0.45] -->|score low| TM
    TM[T1-MID<br/>threshold 0.55] -->|score low| TC
    TC[T1-CLOUD<br/>threshold 0.60] -->|score low| TF
    TF[T2-FLASH<br/>threshold 0.50] -->|score low| TP
    TP[T2-PRO<br/>threshold 0.50] -->|score low| TK
    TK[T2-KIMI<br/>threshold 0.50] -->|max fallbacks| END([Stop])

    style TL fill:#457b9d,color:#fff
    style TM fill:#457b9d,color:#fff
    style TC fill:#e63946,color:#fff
    style TF fill:#f4a261,color:#000
    style TP fill:#f4a261,color:#000
    style TK fill:#f4a261,color:#000
```

Max fallbacks per task: **2**. Quality scores written to `routing_log` for every attempt.

---

## Session Startup Sequence

```mermaid
sequenceDiagram
    participant T as Terminal / zshrc
    participant O as Ollama
    participant W as Watchdog
    participant C as Claude CLI
    participant K as macOS Keychain
    participant MCP as tier-enforcer-mcp

    T->>O: GET /api/ps (are models loaded?)
    alt Models cold
        T->>O: POST /api/generate keep_alive=-1 (7b + 14b)
        O-->>T: Models in RAM
    else Models warm
        T-->>T: Skip prewarm (guard exits)
    end

    T->>W: Start watchdog (single instance guard)
    W->>MCP: Start server.py (FastMCP)

    T->>C: claude (user invokes)
    C->>K: Read "Claude Code-credentials"
    K-->>C: OAuth token sk-ant-oat01-...
    C->>C: Load settings.json (22 MCP servers + hooks)
    C->>C: Load CLAUDE.md (brain protocol v8)

    C->>MCP: activate_tier_routing(session_id)
    MCP->>MCP: Compile LangGraph 8 nodes
    MCP-->>C: OK — LangGraph ready

    C->>MCP: tier_health_check(tier=ALL)
    MCP-->>C: Tier status map

    C->>MCP: prewarm_models()
    MCP->>O: Verify 7b + 14b in RAM
    MCP-->>C: Models confirmed warm

    C->>C: Show STARTUP BANNER (live data)
```

---

## Database Schema (`routing_log`)

```sql
CREATE TABLE routing_log (
    ts              TEXT,       -- ISO timestamp
    session         TEXT,       -- session UUID
    task            TEXT,       -- task description (first 200 chars)
    classified_tier TEXT,       -- e.g. T2-FLASH
    executor_tier   TEXT,       -- actual executing tier (e.g. T1-MID)
    model           TEXT,       -- model name used
    score           REAL,       -- quality score 0.0-1.0
    ok              INTEGER,    -- 1=success, 0=failure
    elapsed         REAL,       -- seconds elapsed
    skills          TEXT,       -- JSON array of matched skills
    brain_used      INTEGER     -- 1=claude_brain ran, 0=skipped
);
```

---

## v9 vs v8 Diff

| Aspect | v8 | v9 |
|--------|----|----|
| Tiers | T1-LOCAL, T1-MID, T1-CLOUD, T2-FLASH, T2-PRO, T2-KIMI, **T3-EPIC** | T1-LOCAL, T1-MID, T1-CLOUD, T2-FLASH, T2-PRO, T2-KIMI |
| Epic routing | T3-EPIC → blueprint → T1-CLOUD | T1-CLOUD directly |
| LangGraph nodes | 9 (included t3_plan) | 8 (t3_plan removed) |
| claude_brain | Ran for every tier | Ran for every tier (same) |
| T3-EPIC rationale | "Claude writes blueprint" | Redundant — claude_brain already does this |
| MODEL_T1_CLOUD | `qwen3-coder:480b` | `qwen3-coder:480b-cloud` (fixed) |
| keep_alive | 7b + 14b only | 7b + 14b + 480b-cloud |
| DB columns | 8 | 11 (+ elapsed, skills, brain_used) |
| Auth | ANTHROPIC_API_KEY env var | OAuth macOS Keychain only |
| Prewarm | Fires every terminal open | Guarded: checks /api/ps first |

---

## Constraint Summary

| Rule | What it means |
|------|--------------|
| RULE 1 | Bash/Edit/Write/MultiEdit disabled for Claude — attempt = ignored |
| RULE 2 | Every task goes through `execute_task()` MCP tool |
| RULE 5 | Epic tasks → T1-CLOUD — T3-EPIC does not exist in v9 |
| RULE 6 | T2 = analysis only; T1 = all execution |
| RULE 7 | tier-enforcer offline → HARD STOP, Claude refuses all tasks |

---

*DSR AI-Lab — Mac Mini — Architecture v9 — 2026-03-22*
