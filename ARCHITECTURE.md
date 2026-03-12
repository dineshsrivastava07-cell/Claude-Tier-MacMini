# Architecture — Claude-Tier-MacMini 7-Tier AI Routing

**Version:** v5.1+ | **Platform:** Mac Mini (Apple Silicon, macOS) | **Updated:** 2026-03-12
**Status:** 7/7 tiers LIVE · LangGraph COMPILED · Progress & Execution Banners ACTIVE

---

## Design Philosophy

> **"Always attempt the cheapest, fastest, local-first option. Escalate only on proven need. Show every routing decision visibly."**

1. **Local-first** — Ollama (free, private) always before cloud
2. **Quality-gated** — every tier output scored 0.0–1.0; escalate only if < 0.75
3. **Hard-enforced** — LangGraph physically prevents T3 except for EPIC
4. **Visible** — Tier Task Progress Banner + Task Executed Tier Banner on every task
5. **Memory-aware** — short-term (session) and long-term (SQLite cross-session) inform routing

---

## Tier Task Progress & Execution Banners

`execute_task()` returns `progress_banner` and `execution_banner` on **every call**.
The system prompt (`tier-routing.md`) mandates they are displayed verbatim.

### Banner Flow

```
User sends task
      │
      ▼
 [DISPLAY progress_banner immediately]
 ╔══════════════════════════════════════════════════════════════════╗
 ║  ⚡ TIER ROUTING — TASK ASSIGNED                                  ║
 ╠══════════════════════════════════════════════════════════════════╣
 ║  Task         : <task description>                               ║
 ║  Complexity   : COMPLEX-FAST                                     ║
 ║  Tier         : 🔵  T2-FLASH                                      ║
 ║  Model        : gemini-2.5-flash                                 ║
 ║  API          : IN PROGRESS → Gemini CLI / Google API            ║
 ╚══════════════════════════════════════════════════════════════════╝
      │
      │  execute_task() → LangGraph runs (classify→gate→execute→quality→audit)
      │
      ▼
 [DISPLAY execution_banner after completion]
 ╔══════════════════════════════════════════════════════════════════╗
 ║  ✅  TASK EXECUTED — 🔵  T2-FLASH                                  ║
 ╠══════════════════════════════════════════════════════════════════╣
 ║  Model        : gemini-2.5-flash                                 ║
 ║  Quality      : 0.87 — PASS ✓                                    ║
 ║  Fallbacks    : 0 escalations                                    ║
 ║  Enforcement  : LANGGRAPH_HARD                                   ║
 ║  API          : YES → Gemini CLI / Google API ✓                  ║
 ╚══════════════════════════════════════════════════════════════════╝
```

### All Banner States

```
PASS (quality ≥ 0.75):
  ✅  TASK EXECUTED — 🟢  T1-LOCAL  quality: 0.91 — PASS ✓  fallbacks: 0
  ✅  TASK EXECUTED — 🟡  T1-MID    quality: 0.83 — PASS ✓  fallbacks: 0
  ✅  TASK EXECUTED — 🟠  T1-CLOUD  quality: 0.78 — PASS ✓  fallbacks: 0
  ✅  TASK EXECUTED — 🔵  T2-FLASH  quality: 0.87 — PASS ✓  fallbacks: 0
  ✅  TASK EXECUTED — 🔷  T2-PRO    quality: 0.92 — PASS ✓  fallbacks: 0
  ✅  TASK EXECUTED — 🟣  T2-KIMI   quality: 0.85 — PASS ✓  fallbacks: 0
  ✅  TASK EXECUTED — 🔴  T3        quality: 0.95 — PASS ✓  fallbacks: 0

ESCALATION (quality < 0.75):
  ✅  TASK EXECUTED — 🟡  T1-MID    quality: 0.61 — FAIL ✗  fallbacks: 1

T3 BLOCKED (non-EPIC hits T3 gate):
  🚫  T3 BLOCKED — complexity: SIMPLE
      Reason: T3 is EPIC only — T3 gate returned BLOCKED
```

### `_make_banners()` Implementation

Located in `tier-enforcer-mcp/server.py`:

```python
_TIER_META = {
    "T1-LOCAL": {"model": "qwen2.5-coder:7b",        "api": "localhost:11434/api/chat", "icon": "🟢"},
    "T1-MID":   {"model": "qwen3-coder:30b",          "api": "localhost:11434/api/chat", "icon": "🟡"},
    "T1-CLOUD": {"model": "qwen3-coder:480b-cloud",   "api": "localhost:11434/api/chat", "icon": "🟠"},
    "T2-FLASH": {"model": "gemini-2.5-flash",         "api": "Gemini CLI / Google API",  "icon": "🔵"},
    "T2-PRO":   {"model": "gemini-2.5-pro",           "api": "Gemini CLI / Google API",  "icon": "🔷"},
    "T2-KIMI":  {"model": "Kimi-K2-Instruct",         "api": "HuggingFace API",          "icon": "🟣"},
    "T3":       {"model": "claude-sonnet-4-6",        "api": "Anthropic (Claude direct)","icon": "🔴"},
}

def _make_banners(task, tier, complexity, quality, fallback_count,
                  enforcement, t3_blocked=False, t3_reason="") -> dict:
    # Returns: {"progress_banner": str, "execution_banner": str}
    # progress_banner  → shown BEFORE execute_task fires
    # execution_banner → shown AFTER execute_task returns
```

**`execute_task()` return payload includes:**
```python
{
    "enforcement":      "LANGGRAPH_HARD",
    "tier":             "T2-FLASH",
    "complexity":       "COMPLEX-FAST",
    "quality_score":    0.87,
    "fallback_count":   0,
    "t3_approved":      False,
    "chain_exhausted":  False,
    "result":           "<model output>",
    "graph_nodes":      ["classify", "t2_flash", "quality", "audit"],
    "progress_banner":  "╔══...⚡ TIER ROUTING — TASK ASSIGNED...╝",
    "execution_banner": "╔══...✅ TASK EXECUTED — 🔵 T2-FLASH...╝",
}
```

---

## Component Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 CLAUDE-TIER-MACMINI v5.1+ — COMPONENT MAP                  │
│                                                                             │
│  ACTIVATION LAYER                                                           │
│  ~/.zshrc → claude() → --append-system-prompt tier-routing.md (v5.1)       │
│  SessionStart hook → pre-flight banner → Ollama/Gemini health check        │
│                                                                             │
│  ENFORCEMENT LAYER                                                          │
│  ┌───────────────────────────────────┐  ┌───────────────────────────────┐  │
│  │  tier-enforcer-mcp (Python)       │  │  tier-router-mcp (TypeScript) │  │
│  │  execute_task() → LangGraph       │  │  18 tools · 3 resources       │  │
│  │  _make_banners() → banners        │  │  routing/T1/T2/T3/pipelines   │  │
│  └───────────────────────────────────┘  └───────────────────────────────┘  │
│                                                                             │
│  EXECUTION LAYER                                                            │
│  🟢 T1-LOCAL  qwen2.5-coder:7b      localhost:11434  SIMPLE                │
│  🟡 T1-MID    qwen3-coder:30b       localhost:11434  MODERATE-SMALL        │
│  🟠 T1-CLOUD  qwen3-coder:480b-clou localhost:11434  MODERATE-LARGE        │
│  🔵 T2-FLASH  gemini-2.5-flash      Google API       COMPLEX-FAST          │
│  🔷 T2-PRO    gemini-2.5-pro        Google API       COMPLEX-DEEP          │
│  🟣 T2-KIMI   Kimi-K2-Instruct      HuggingFace API  COMPLEX-REASON        │
│  🔴 T3        claude-sonnet-4-6     Anthropic        EPIC ONLY (gated)     │
│                                                                             │
│  OBSERVABILITY LAYER                                                        │
│  LangSmith → smith.langchain.com/project/dsr-ai-lab-tier-routing           │
│  Routing Log → ~/.tier-enforcer/routing.log (JSONL)                        │
│  Memory DB  → ~/.tier-enforcer/memory.db (SQLite, STM + LTM)               │
│  Banners    → progress_banner + execution_banner in every execute_task()   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## LangGraph Enforcement Graph (Full Flow with Banners)

```
User Task
    │
    ▼
execute_task(task, session_id)
    │
    │ [progress_banner generated from classify result — displayed before execution]
    │
    ▼
run_tier_graph()
    │
    ▼
┌─ classify_node ──────────────────────────────────────────────────────────┐
│  HARD GATE 1 — always first, cannot be skipped                          │
│  Reads ROUTING_RULES from server.py (single source of truth)            │
│  Assigns: complexity + tier                                             │
│  Enriches: context with STM (last 3 session tasks) + LTM (SQLite)      │
│  Logs: audit_log entry {node: classify, complexity, tier, layer: L2}   │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   │ conditional edge → execution node or t3_gate
    ┌──────────────────────────────▼──────────────────────────────────────┐
    │  EPIC? → t3_gate_node                                               │
    │           APPROVED (EPIC or chain exhausted) → audit               │
    │           BLOCKED (not EPIC) → 🚫 T3 BLOCKED banner → audit        │
    └─────────────────────────────────────────────────────────────────────┘
    │
    │  T1/T2 tasks:
    ▼
┌─ execute_node (one of 6) ─────────────────────────────────────────────────┐
│  t1_local_node  → ChatOllama(qwen2.5-coder:7b,  localhost:11434)         │
│  t1_mid_node    → ChatOllama(qwen3-coder:30b,    localhost:11434)         │
│  t1_cloud_node  → ChatOllama(qwen3-coder:480b-c, localhost:11434)         │
│  t2_flash_node  → subprocess gemini -m gemini-2.5-flash                  │
│  t2_pro_node    → subprocess gemini -m gemini-2.5-pro                    │
│  t2_kimi_node   → InferenceClient(Kimi-K2-Instruct, HF token)            │
│                                                                           │
│  All nodes: state.result = output, state.quality_score = _score_quality  │
└───────────────────────────────────────┬───────────────────────────────────┘
                                        │ → quality gate (mandatory)
    ┌───────────────────────────────────▼───────────────────────────────────┐
    │  quality_gate_node                                                    │
    │  score ≥ 0.75  → PASS → audit                                        │
    │  score < 0.75  → ESCALATE → next tier in fallback chain              │
    │  at T2-KIMI and still failing → chain_exhausted=True → T3 gate       │
    └───────────────────────────────────┬───────────────────────────────────┘
                                        │
    ┌───────────────────────────────────▼───────────────────────────────────┐
    │  audit_node                                                           │
    │  → routing.log (JSONL): tier, quality, fallback_count, timestamp     │
    │  → memory.db (SQLite): long_term_memory INSERT                       │
    │  → STM update: short_term_memory[-10:]                               │
    │  → LangSmith: trace recorded                                         │
    └───────────────────────────────────┬───────────────────────────────────┘
                                        │
                                        ▼
                                       END
    │
    ▼
_make_banners(tier, complexity, quality, fallback_count, enforcement)
    │
    ├── progress_banner  (tier assignment — IN PROGRESS)
    └── execution_banner (result — PASS ✓ / FAIL ✗ / 🚫 BLOCKED)

execute_task() returns full payload including both banners
```

---

## Fallback Chain with Banner States

```
T1-LOCAL  → quality ≥ 0.75 → ✅ TASK EXECUTED — 🟢 T1-LOCAL  PASS ✓
              quality < 0.75 → ✅ TASK EXECUTED — 🟢 T1-LOCAL  FAIL ✗  escalating...
                  │
                  ▼
            T1-MID  → quality ≥ 0.75 → ✅ TASK EXECUTED — 🟡 T1-MID  PASS ✓
              quality < 0.75 → escalate...
                  │
                  ▼
            T1-CLOUD → quality ≥ 0.75 → ✅ TASK EXECUTED — 🟠 T1-CLOUD  PASS ✓
              quality < 0.75 → escalate...
                  │
                  ▼
            T2-FLASH → quality ≥ 0.75 → ✅ TASK EXECUTED — 🔵 T2-FLASH  PASS ✓
              quality < 0.75 → escalate...
                  │
                  ▼
            T2-PRO  → quality ≥ 0.75 → ✅ TASK EXECUTED — 🔷 T2-PRO  PASS ✓
              quality < 0.75 → escalate...
                  │
                  ▼
            T2-KIMI → quality ≥ 0.75 → ✅ TASK EXECUTED — 🟣 T2-KIMI  PASS ✓
              quality < 0.75 → chain_exhausted=True
                  │
                  ▼
            T3 GATE → approved (chain exhausted)
                  │
                  ▼
            ✅ TASK EXECUTED — 🔴 T3  PASS ✓
```

---

## Two-Layer Activation Model

```
LAYER 1: OAuth (pre-MCP — banners NOT applicable)
  ┌──────────────────────────────────────────────────────────────────┐
  │ Process-level auth before Claude CLI shell opens                │
  │ MCP tools / tier-routing.md / banners do NOT exist yet          │
  │ LAYER_1_AUTH_BYPASS = True (hardcoded in server.py)             │
  └──────────────────────────────────────────────────────────────────┘
                  │ auth completes
                  ▼
LAYER 2: Task routing — banners ACTIVE on every task
  ┌──────────────────────────────────────────────────────────────────┐
  │ Claude CLI shell opens                                          │
  │ tier-routing.md injected → BANNER DISPLAY RULES loaded         │
  │ SessionStart hook fires → pre-flight banner                    │
  │ tier-enforcer-mcp auto-connects → execute_task() registered    │
  │                                                                 │
  │ Every user task:                                                │
  │   1. Show progress_banner (tier assigned, IN PROGRESS)         │
  │   2. execute_task() → LangGraph runs                           │
  │   3. Show execution_banner (PASS ✓ / FAIL ✗ / 🚫 BLOCKED)     │
  └──────────────────────────────────────────────────────────────────┘
```

---

## Routing Rules (server.py — single source of truth)

```python
ROUTING_RULES = {
  "EPIC":           tier=T3,        keywords=[greenfield, new platform, full system...]
  "COMPLEX-REASON": tier=T2-KIMI,   keywords=[math, statistic, algorithm, bayesian...]
  "COMPLEX-DEEP":   tier=T2-PRO,    keywords=[architecture, security audit, rca...]
  "COMPLEX-FAST":   tier=T2-FLASH,  keywords=[debug, fix bug, refactor, multi-file...]
  "MODERATE-LARGE": tier=T1-CLOUD,  keywords=[feature set, pipeline, new module...]
  "MODERATE-SMALL": tier=T1-MID,    keywords=[implement, create feature, new class...]
  "SIMPLE":         tier=T1-LOCAL,  keywords=[] (default catch-all)
}
```

Imported by `langgraph_tier.py` → `classify_node`. No duplicate keyword lists anywhere.

---

## Full Routing Matrix

| Task Type | SIMPLE 🟢 | MOD-SM 🟡 | MOD-LG 🟠 | CMPLX-F 🔵 | CMPLX-D 🔷 | CMPLX-R 🟣 | EPIC 🔴 |
|-----------|-----------|-----------|-----------|-----------|-----------|-----------|---------|
| CODE_GEN | T1-LOCAL | T1-MID | T1-CLOUD | T2-FLASH | T2-PRO | T2-KIMI | T3 |
| CODE_FIX | T1-LOCAL | T1-MID | T1-CLOUD | T2-FLASH | T2-PRO | T2-KIMI | T3 |
| REFACTOR | T1-LOCAL | T1-MID | T1-CLOUD | T2-FLASH | T2-PRO | T2-KIMI | T3 |
| DEBUG | T1-LOCAL | T1-MID | T1-CLOUD | T2-FLASH | T2-PRO | T2-KIMI | T3 |
| MATH/ALGO | T1-LOCAL | T1-MID | T1-CLOUD | T2-FLASH | T2-PRO | T2-KIMI | T3 |
| ARCHITECTURE | T1-LOCAL | T1-MID | T1-CLOUD | T2-FLASH | T2-PRO | T2-KIMI | T3 |
| **Catch-all** | T1-LOCAL | T1-MID | T1-CLOUD | T2-FLASH | T2-PRO | T2-KIMI | T3 |

---

## Security Model

| Layer | Mechanism | Covers |
|-------|-----------|--------|
| System Prompt | `tier-routing.md` · BANNER DISPLAY RULES | Routing + banner enforcement |
| LangGraph | 5-node compiled graph | T3 physically unreachable unless EPIC |
| MCP Gate | `t3_gate_node` · `t3_epic_gate()` | Hard block with reason + banner |
| Quality Gate | threshold 0.75 | Low-quality escalation + banner FAIL state |
| Audit Log | `routing.log` (JSONL) | Every decision: tier, quality, timestamp |
| SQLite Memory | `memory.db` | Cross-session routing history |
| LangSmith | All traces | Full observability |
| Budget Caps | `T3_MONTHLY_TOKEN_CAP=50000` | T3 spending control |
| Ollama Local | T1 models on localhost | No data leaves machine for T1 |

---

## Version Evolution

| Version | Date | Change |
|---------|------|--------|
| v1.0 | 2026-02 | TypeScript MCP server, 4-tier concept |
| v2.0 | 2026-02 | Base routing prompt, skill layer |
| v3.0 | 2026-03-02 | SIMPLE→T1-LOCAL strict, B-01/B-06 fixed |
| v4.0 | 2026-03-04 | Native Tool Fraud patch, B-02/B-03/B-04 fixed |
| v4.1 | 2026-03-04 | Header Precision Rules, B-05/B-07 fixed |
| v5.1 | 2026-03-12 | 7 tiers, LangGraph, T1-MID, T2-KIMI, SQLite, LangSmith |
| **v5.1+** | **2026-03-12** | **`_make_banners()` · Tier Task Progress Banner · Task Executed Tier Banner · all 7 tiers with icons · wired into execute_task() · mandated by tier-routing.md** |

---

*Architecture document for Claude-Tier-MacMini · v5.1+ · Mac Mini Apple Silicon · 2026-03-12 IST*
