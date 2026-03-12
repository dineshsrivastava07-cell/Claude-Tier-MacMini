# Architecture — Claude-Tier-MacMini 7-Tier AI Routing

**Version:** v5.1 | **Platform:** Mac Mini (Apple Silicon, macOS) | **Updated:** 2026-03-12  
**Status:** 7/7 tiers LIVE · LangGraph COMPILED · LangSmith ACTIVE

---

## Design Philosophy

> **"Always attempt the cheapest, fastest, local-first option. Escalate only on proven need."**

1. **Local-first** — Ollama (free, private, fast) is always attempted before cloud
2. **Quality-gated** — every tier output is scored (0.0–1.0); escalate only if below 0.75
3. **Hard-enforced** — LangGraph physically prevents T3 access except for EPIC tasks
4. **Honest routing** — every response header shows the actual model that produced the content
5. **Memory-aware** — short-term (in-session) and long-term (cross-session SQLite) inform routing

---

## Component Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 CLAUDE-TIER-MACMINI v5.1 — COMPONENT MAP                   │
│                                                                             │
│  ACTIVATION LAYER                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  ~/.zshrc — claude() wrapper                                        │   │
│  │  Injects ~/.claude/tier-routing.md via --append-system-prompt       │   │
│  │  Fires on every claude invocation (post OAuth auth)                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  ~/.claude/settings.local.json — SessionStart hook                  │   │
│  │  Fires pre-flight banner + Ollama/Gemini health check immediately    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ENFORCEMENT LAYER                                                          │
│  ┌───────────────────────────────────┐  ┌───────────────────────────────┐  │
│  │  tier-enforcer-mcp                │  │  tier-router-mcp              │  │
│  │  ~/tier-enforcer-mcp/server.py    │  │  ~/tier-router-mcp/dist/      │  │
│  │  Python · fastmcp 3.1.0           │  │  TypeScript · Node 20+        │  │
│  │                                   │  │                               │  │
│  │  execute_task() — MASTER ENTRY    │  │  18 tools (routing/T1/T2/T3/  │  │
│  │  run_tier_graph() — LangGraph     │  │  pipelines) · 3 resources     │  │
│  │  ROUTING_RULES (server.py)        │  │  Registered: user scope       │  │
│  │  Registered: user + desktop scope │  │                               │  │
│  └───────────────────────────────────┘  └───────────────────────────────┘  │
│                                                                             │
│  EXECUTION LAYER                                                            │
│  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ ┌───────┐  │
│  │T1-LOCAL │ │ T1-MID  │ │ T1-CLOUD │ │ T2-FLASH │ │ T2-PRO │ │T2-KIMI│  │
│  │qwen2.5  │ │qwen3-30b│ │qwen3-480b│ │gemini-   │ │gemini- │ │Kimi-  │  │
│  │coder:7b │ │         │ │-cloud    │ │2.5-flash │ │2.5-pro │ │K2     │  │
│  │local    │ │local    │ │local     │ │Google API│ │Google  │ │HF API │  │
│  │SIMPLE   │ │MOD-SMALL│ │MOD-LARGE │ │CMPLX-FAST│ │CMPLX-DP│ │CMPLX-R│  │
│  └─────────┘ └─────────┘ └──────────┘ └──────────┘ └────────┘ └───────┘  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  T3 — claude-sonnet-4-6 — EPIC ONLY                                │   │
│  │  Hard-gated: t3_gate_node blocks unless EPIC or chain exhausted     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  OBSERVABILITY LAYER                                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  LangSmith: smith.langchain.com/project/dsr-ai-lab-tier-routing     │   │
│  │  Routing Log: ~/.tier-enforcer/routing.log (JSONL, every decision)  │   │
│  │  Memory DB: ~/.tier-enforcer/memory.db (SQLite, short+long-term)    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Tier Architecture

| Tier | Model | Host | Complexity | Task Examples |
|------|-------|------|-----------|---------------|
| **T1-LOCAL** | `qwen2.5-coder:7b` | `localhost:11434` | SIMPLE | Single file edit, config, shell cmd, rename |
| **T1-MID** | `qwen3-coder:30b` | `localhost:11434` | MODERATE-SMALL | New class/function, unit test, API endpoint, CRUD |
| **T1-CLOUD** | `qwen3-coder:480b-cloud` | `localhost:11434` | MODERATE-LARGE | Feature set, pipeline, AI agent, multi-file module |
| **T2-FLASH** | `gemini-2.5-flash` | Google API | COMPLEX-FAST | Debug, refactor, multi-file, e2e wiring, iteration |
| **T2-PRO** | `gemini-2.5-pro` | Google API | COMPLEX-DEEP | Architecture, security audit, RCA, tech spec |
| **T2-KIMI** | `moonshotai/Kimi-K2-Instruct` | HuggingFace API | COMPLEX-REASON | Math, stats, algorithms, proofs, Bayesian, ML |
| **T3** | `claude-sonnet-4-6` | Anthropic | EPIC | New platform, full system from scratch, greenfield |

---

## LangGraph Enforcement Graph (Full Flow)

```
User Task
    │
    ▼
execute_task(task, session_id)          ← MCP tool — MANDATORY for every task
    │
    │ try: from langgraph_tier import run_tier_graph
    │      → LANGGRAPH_HARD mode
    │ except ImportError:
    │      → MCP soft chain fallback (T3 gate still fires)
    │
    ▼
run_tier_graph(task, session_id, context)
    │
    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  TierState (TypedDict)                                                   │
│  task, complexity, assigned_tier, result, quality_score,                │
│  fallback_count, chain_exhausted, t3_approved, audit_log,               │
│  session_id, short_term_memory, error                                   │
└──────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─ NODE 1: classify_node ─────────────────────────────────────────────────┐
│  HARD ENTRY GATE — physically the first node, cannot be skipped         │
│                                                                          │
│  1. Reads ROUTING_RULES from server.py (single source of truth)         │
│  2. Classifies complexity (SIMPLE/MOD-SM/MOD-LG/CMPLX-F/CMPLX-D/       │
│     CMPLX-R/EPIC)                                                        │
│  3. Loads short-term memory (last 3 tasks from this session)            │
│  4. Loads long-term memory (last 3 similar tasks from SQLite)           │
│  5. Enriches context with STM + LTM                                     │
│  6. Assigns tier → state.assigned_tier                                  │
│  7. Writes audit_log entry: node=classify, complexity, tier, layer=     │
│     LAYER_2_TASK_ROUTING                                                │
└──────────────────────────────────────────────────────────────────────────┘
    │
    │ conditional edge: _route_from_classify()
    │ maps assigned_tier → execution node or t3_gate
    ▼
┌─ NODE 2: t3_gate_node ──────────────────────────────────────────────────┐
│  HARD GATE 2 — fires for any T3-assigned task                           │
│                                                                          │
│  APPROVED if:                                                            │
│    complexity == "EPIC"         → "EPIC complexity approved"            │
│    chain_exhausted == True      → "Full chain exhausted"                │
│                                                                          │
│  BLOCKED if:                                                             │
│    anything else                → "BLOCKED — {complexity} is not EPIC. │
│                                    Use T1/T2."                          │
│                                                                          │
│  → t3_approved stored in state                                          │
│  → Routes to audit_node (Claude CLI handles actual T3 execution)        │
└──────────────────────────────────────────────────────────────────────────┘
    │ (for T1/T2 tasks — t3_gate not in path)
    ▼
┌─ NODE 3: execute_node (one of 6) ───────────────────────────────────────┐
│                                                                          │
│  t1_local_node  → ChatOllama(qwen2.5-coder:7b,  localhost:11434)       │
│  t1_mid_node    → ChatOllama(qwen3-coder:30b,    localhost:11434)       │
│  t1_cloud_node  → ChatOllama(qwen3-coder:480b-c, localhost:11434)       │
│  t2_flash_node  → subprocess gemini -m gemini-2.5-flash -p "..."       │
│  t2_pro_node    → subprocess gemini -m gemini-2.5-pro -p "..."         │
│  t2_kimi_node   → InferenceClient(Kimi-K2-Instruct, HF token)          │
│                                                                          │
│  All nodes:                                                              │
│  • Prepend STM + LTM context to prompt                                  │
│  • Set state.result = model output                                      │
│  • Set state.quality_score = _score_quality(result, task)              │
│  • Append audit_log entry                                               │
└──────────────────────────────────────────────────────────────────────────┘
    │
    │ all execution nodes → quality gate (mandatory, no bypass)
    ▼
┌─ NODE 4: quality_gate_node ─────────────────────────────────────────────┐
│  HARD GATE 3 — after every execution node                               │
│                                                                          │
│  quality_score >= 0.75  → PASS → route to audit_node                   │
│                                                                          │
│  quality_score < 0.75   → ESCALATE:                                     │
│    Find current tier index in FALLBACK_CHAIN                            │
│    Assign next tier: FALLBACK_CHAIN[idx + 1]                            │
│    If current >= T2-KIMI index → chain_exhausted = True → T3            │
│    fallback_count += 1                                                  │
│    Route back to next execution node                                    │
│                                                                          │
│  FALLBACK CHAIN: T1-LOCAL→T1-MID→T1-CLOUD→T2-FLASH→T2-PRO→T2-KIMI→T3 │
└──────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─ NODE 5: audit_node ────────────────────────────────────────────────────┐
│  ALWAYS LAST — writes every routing decision                            │
│                                                                          │
│  Writes JSONL to: ~/.tier-enforcer/routing.log                         │
│  Fields: event, session_id, task_preview, complexity, final_tier,      │
│          quality_score, fallback_count, t3_approved, chain_exhausted,  │
│          timestamp                                                       │
│                                                                          │
│  Updates short-term memory: STM[-10:] (last 10 tasks, this session)    │
│                                                                          │
│  Saves to SQLite long-term memory:                                      │
│  INSERT INTO long_term_memory (session_id, task_type, tier_used,       │
│                                quality, summary)                        │
│                                                                          │
│  LangSmith trace: audit_node tagged, spans visible at smith.langchain  │
└──────────────────────────────────────────────────────────────────────────┘
    │
    ▼
  END → execute_task() returns {
    enforcement, tier, complexity, quality_score,
    fallback_count, t3_approved, t3_block_reason,
    chain_exhausted, result, error, graph_nodes
  }
```

---

## End-to-End Data Flow

### Session Activation (immediately after OAuth)

```
User runs: claude [args]
    │
    ▼
~/.zshrc — claude() function intercepts
    │  --append-system-prompt "$(cat ~/.claude/tier-routing.md)"
    │  tier-routing.md (v5.1) injected as system prompt
    ▼
Claude CLI process starts
    │
    ├── SessionStart hook fires → pre-flight banner
    │   └── curl localhost:11434 → T1-Ollama LIVE/DOWN
    │   └── gemini --version → T2-Gemini LIVE/DOWN
    │   └── T3-Claude AUTH (always)
    │
    ├── tier-enforcer-mcp auto-connects (user scope)
    │   └── execute_task() tool registered
    │   └── LangGraph graph compiled on import
    │
    └── tier-router-mcp auto-connects (user scope)
        └── 18 tools registered
        └── 3 resources available
```

### Task Execution Flow

```
User: "fix the null pointer in user service"
    │
    ▼
Claude CLI receives task
    │
    ▼
execute_task(
  task="fix the null pointer in user service",
  session_id="session-xyz"
)
    │
    ▼
classify_node:
  task.lower() → "fix" matches COMPLEX-FAST keywords → T2-FLASH? 
  wait — also check "fix bug" pattern
  → complexity=COMPLEX-FAST, tier=T2-FLASH
    │
    ▼
t3_gate_node:
  complexity != EPIC, chain_exhausted=False → not in T3 path
  (T3 gate bypassed for T2-FLASH tasks)
    │
    ▼
t2_flash_node:
  subprocess.run(["gemini", "-m", "gemini-2.5-flash", "-p",
                  "...context...

Task: fix the null pointer in user service"])
  result.stdout → gemini output
  quality_score = _score_quality(output, task) → 0.87
    │
    ▼
quality_gate_node:
  0.87 >= 0.75 → PASS
    │
    ▼
audit_node:
  routing.log: {"complexity":"COMPLEX-FAST","final_tier":"T2-FLASH","quality_score":0.87}
  memory.db: INSERT task_type="debugging", tier_used="T2-FLASH", quality=0.87
  LangSmith: trace recorded
    │
    ▼
execute_task() returns:
  {enforcement: "LANGGRAPH_HARD", tier: "T2-FLASH", quality_score: 0.87, ...}
    │
    ▼
Claude CLI applies output via Write/Edit tools
```

---

## Quality Scoring

```python
def _score_quality(result: str, task: str) -> float:
    # Method 1: Structured parser (uses T1-LOCAL qwen2.5-coder:7b — free)
    # Evaluates: addresses_task, is_complete, has_code, no_refusal, confidence_score
    # Returns: 0.0 – 1.0

    # Method 2: Heuristic fallback
    score = 0.5
    if len(result) > 100:  score += 0.1    # non-trivial response
    if len(result) > 500:  score += 0.1    # substantial response
    if "```" in result:    score += 0.15   # has code blocks (for code tasks)
    if no refusal phrases: score += 0.15   # not an error/refusal
    return min(score, 1.0)
```

**Gate threshold: 0.75**
- ≥ 0.75 → accept, proceed to audit
- < 0.75 → escalate one tier, retry
- Chain exhausted (all T2 tiers failed) → `chain_exhausted=True` → T3 gate

---

## Memory Architecture

### Short-Term Memory (In-Session)

```
TierState.short_term_memory[]
    │
    ├── Populated by audit_node after each task
    ├── Stores last 10 tasks: {task[:80], tier, quality, timestamp}
    └── Injected into classify_node context as:
        "Recent session context:
          [T2-FLASH] fix the null pointer in user service
          [T1-LOCAL] rename variable in config.py"
```

### Long-Term Memory (Cross-Session SQLite)

```
~/.tier-enforcer/memory.db
    │
    ├── Table: long_term_memory
    │     session_id, task_type, tier_used, quality, summary, timestamp
    │     Queried at classify_node: last 3 similar task_type records
    │
    └── Table: project_patterns
          project, tech_stack, patterns, preferred_tier, last_updated
```

```
_classify_task_type(task):
  "math/statistic/algorithm" → "mathematical"
  "debug/fix/bug/error"      → "debugging"
  "refactor/clean/improve"   → "refactoring"
  "implement/create/build"   → "implementation"
  "design/architect/plan"    → "architecture"
  "test/spec/coverage"       → "testing"
  default                    → "general"
```

---

## Routing Rules — Single Source of Truth

**All routing logic lives in `server.py → ROUTING_RULES` dict.**  
`langgraph_tier.py` imports `_classify_task()` and `ROUTING_RULES` from `server.py`.  
No duplicate keyword lists anywhere.

```
ROUTING_RULES = {
  "EPIC":           tier=T3,        gate=t3_epic_gate (BLOCKED unless EPIC)
  "COMPLEX-REASON": tier=T2-KIMI,   keywords=[math, statistic, algorithm, ...]
  "COMPLEX-DEEP":   tier=T2-PRO,    keywords=[architecture, security audit, ...]
  "COMPLEX-FAST":   tier=T2-FLASH,  keywords=[debug, fix bug, refactor, ...]
  "MODERATE-LARGE": tier=T1-CLOUD,  keywords=[feature set, pipeline, ai agent, ...]
  "MODERATE-SMALL": tier=T1-MID,    keywords=[implement, create feature, new class, ...]
  "SIMPLE":         tier=T1-LOCAL,  keywords=[] (default fallback — everything else)
}
```

**Complexity check runs FIRST, before task type.** SIMPLE always → T1-LOCAL, regardless of task type.

---

## Full Routing Matrix

| Task Type | SIMPLE | MOD-SMALL | MOD-LARGE | CMPLX-FAST | CMPLX-DEEP | CMPLX-REASON | EPIC |
|-----------|--------|-----------|-----------|-----------|-----------|-------------|------|
| CODE_GEN | T1-LOCAL | T1-MID | T1-CLOUD | T2-FLASH | T2-PRO | T2-KIMI | T3 |
| CODE_FIX | T1-LOCAL | T1-MID | T1-CLOUD | T2-FLASH | T2-PRO | T2-KIMI | T3 |
| REFACTOR | T1-LOCAL | T1-MID | T1-CLOUD | T2-FLASH | T2-PRO | T2-KIMI | T3 |
| DEBUG | T1-LOCAL | T1-MID | T1-CLOUD | T2-FLASH | T2-PRO | T2-KIMI | T3 |
| MATH/ALGO | T1-LOCAL | T1-MID | T1-CLOUD | T2-FLASH | T2-PRO | T2-KIMI | T3 |
| QA | T1-LOCAL | T1-MID | T1-CLOUD | T2-FLASH | T2-PRO | T2-KIMI | T3 |
| ARCHITECTURE | T1-LOCAL | T1-MID | T1-CLOUD | T2-FLASH | T2-PRO | T2-KIMI | T3 |
| **Catch-all** | T1-LOCAL | T1-MID | T1-CLOUD | T2-FLASH | T2-PRO | T2-KIMI | T3 |

---

## Fallback Chain Diagram

```
T1-LOCAL
  quality ≥ 0.75 → ✅ DONE
  quality < 0.75 → escalate
        │
        ▼
     T1-MID
       quality ≥ 0.75 → ✅ DONE
       quality < 0.75 → escalate
             │
             ▼
          T1-CLOUD
            quality ≥ 0.75 → ✅ DONE
            quality < 0.75 → escalate
                  │
                  ▼
               T2-FLASH
                 quality ≥ 0.75 → ✅ DONE
                 quality < 0.75 → escalate
                       │
                       ▼
                    T2-PRO
                      quality ≥ 0.75 → ✅ DONE
                      quality < 0.75 → escalate
                            │
                            ▼
                         T2-KIMI
                           quality ≥ 0.75 → ✅ DONE
                           quality < 0.75 → chain_exhausted=True
                                 │
                                 ▼
                              T3 GATE
                              t3_approved=True (chain exhausted)
                                 │
                                 ▼
                          T3 — Claude answers directly ✅
```

---

## Two-Layer Activation Model

```
LAYER 1: OAuth Authentication
  ┌─────────────────────────────────────────────────────────────────┐
  │ Runs at process level before Claude CLI shell opens             │
  │ MCP tools do NOT exist yet                                      │
  │ tier-routing.md has NOT loaded yet                              │
  │ T3 gate CANNOT fire — it is infrastructure, not a task         │
  │ LAYER_1_AUTH_BYPASS = True (hardcoded in server.py)            │
  └─────────────────────────────────────────────────────────────────┘
                  │
                  │ auth completes
                  ▼
LAYER 2: Task Routing (all user tasks)
  ┌─────────────────────────────────────────────────────────────────┐
  │ Claude CLI shell opens                                          │
  │ tier-routing.md injected (--append-system-prompt)              │
  │ SessionStart hook fires                                         │
  │ MCP servers auto-connect                                        │
  │ LangGraph graph compiled on tier-enforcer-mcp import           │
  │                                                                 │
  │ EVERY user task → execute_task() → LangGraph graph             │
  │ NO exceptions. T3 gate always in path.                         │
  └─────────────────────────────────────────────────────────────────┘
```

---

## Native Tool Permission Map

| Tool | Permitted? | Rule |
|------|-----------|------|
| `Read` file | ✅ Always | Build context for T1/T2 prompt — never substitutes T1 work |
| `Bash` (ls, cat, git, grep) | ✅ Always | Gather context — read-only |
| `Write` / `Edit` file | ⚠️ Apply only | ONLY to apply T1/T2/T3 output — never self-generate |
| `Bash` (write/exec) | ⚠️ Apply only | Apply T1/T2 output or EPIC tasks |
| Generate content (SIMPLE) | ❌ Banned | Must call T1-LOCAL Ollama API |
| Generate content (MODERATE) | ❌ Banned | Must call T1-CLOUD Ollama API |
| Generate content (COMPLEX) | ❌ Banned | Must call Gemini or Kimi API |
| Generate content (EPIC) | ✅ T3 only | Claude generates directly — only legitimate T3 case |

---

## Security Model

| Layer | Mechanism | What it enforces |
|-------|-----------|-----------------|
| **System Prompt** | `~/.claude/tier-routing.md` via `--append-system-prompt` | Routing rules as context |
| **SessionStart Hook** | `settings.local.json` | Pre-flight banner, health check on every session |
| **LangGraph Hard Graph** | `langgraph_tier.py` — compiled DAG | T3 physically unreachable except EPIC/exhausted |
| **MCP Tool Gate** | `t3_gate_node` in graph | Returns BLOCKED with reason for non-EPIC |
| **MCP Fallback Gate** | `t3_epic_gate()` in server.py | Still fires if LangGraph unavailable |
| **Quality Gate** | threshold 0.75 | Prevents low-quality output propagating |
| **Audit Log** | `~/.tier-enforcer/routing.log` | Every decision logged: tier, quality, timestamp |
| **SQLite Memory** | `~/.tier-enforcer/memory.db` | Cross-session memory informs routing |
| **LangSmith** | All executions traced | Full observability — smith.langchain.com |
| **T3 Budget Caps** | `T3_MONTHLY_TOKEN_CAP=50000` | Hard spending limit on T3 (EPIC) tasks |
| **Ollama Local-only** | T1 models on localhost | No data leaves machine for T1 tasks |
| **No secrets in repo** | `.env.example` only | API keys via env vars |

---

## Version Evolution

| Version | Date | Change |
|---------|------|--------|
| v1.0 | 2026-02 | TypeScript MCP server, 4-tier concept |
| v2.0 | 2026-02 | Base routing prompt, skill layer |
| v3.0 | 2026-03-02 | Strict SIMPLE→T1-LOCAL, shell remapping, B-01/B-06 fixed |
| v4.0 | 2026-03-04 | Native Tool Fraud patch, sub-task routing, B-02/B-03/B-04 fixed |
| v4.1 | 2026-03-04 | Header Precision Rules, B-05/B-07/B-08 fixed |
| **v5.1** | **2026-03-12** | **7 tiers: +T1-MID (qwen3-coder:30b), +T2-KIMI (Kimi-K2-Instruct). LangGraph hard enforcement engine. execute_task() master entry point. SQLite short+long-term memory. LangSmith tracing. All 7/7 tiers verified LIVE.** |

---

*Architecture document for Claude-Tier-MacMini · v5.1 · Mac Mini Apple Silicon · 2026-03-12 IST*
