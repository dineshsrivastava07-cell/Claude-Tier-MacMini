# Claude-Tier-MacMini — 7-Tier AI Routing for Claude CLI

![Version](https://img.shields.io/badge/version-v5.1-blue)
![Platform](https://img.shields.io/badge/platform-Mac%20Mini%20Apple%20Silicon-black)
![Ollama](https://img.shields.io/badge/T1-Ollama%20Qwen-orange)
![Gemini](https://img.shields.io/badge/T2-Gemini%202.5-blue)
![Kimi](https://img.shields.io/badge/T2--KIMI-Kimi--K2-green)
![Claude](https://img.shields.io/badge/T3-Claude%20Sonnet-purple)
![LangGraph](https://img.shields.io/badge/LangGraph-Hard%20Enforced-red)
![MCP](https://img.shields.io/badge/MCP-22%20servers-green)
![Status](https://img.shields.io/badge/7%2F7%20tiers-LIVE-brightgreen)

**Strict 7-Tier AI routing enforcement for Claude CLI on Mac Mini (Apple Silicon).**
Every task is classified by complexity and routed through a LangGraph-enforced pipeline — local Qwen first, escalating through Gemini and Kimi-K2 to Claude only for EPIC tasks.

> **v5.1**: Upgraded from 4 tiers to 7. Added T1-MID (`qwen3-coder:30b`), T2-KIMI (`Kimi-K2-Instruct`). Full LangGraph hard enforcement with SQLite memory and LangSmith tracing. All 7/7 tiers verified live 2026-03-12.

---

## System Status — Live (2026-03-12)

| Tier | Model | Test Result | Latency |
|------|-------|-------------|---------|
| T1-LOCAL | qwen2.5-coder:7b | `T1-LOCAL-OK` ✓ | ~32ms |
| T1-MID | qwen3-coder:30b | `T1-MID-OK` ✓ | ~400ms |
| T1-CLOUD | qwen3-coder:480b-cloud | `T1-CLOUD-OK` ✓ | ~4ms |
| T2-FLASH | gemini-2.5-flash | `T2-FLASH-OK` ✓ | ~10s |
| T2-PRO | gemini-2.5-pro | `HEALTHY` ✓ | ~8s |
| T2-KIMI | Kimi-K2-Instruct | `T2-KIMI-OK` ✓ | HF API |
| T3 | claude-sonnet-4-6 | `LIVE` ✓ | EPIC only |

**LangGraph**: v1.1.1 installed · Graph compiled · `LANGGRAPH_HARD` enforcement active  
**LangSmith**: Tracing enabled · Project: `dsr-ai-lab-tier-routing`  
**Routing Log**: `~/.tier-enforcer/routing.log` · Memory DB: `~/.tier-enforcer/memory.db`

---

## Overview

Claude-Tier-MacMini enforces a cost-optimised, quality-gated AI routing discipline:

- **T1-LOCAL** (free, instant): `qwen2.5-coder:7b` — all SIMPLE tasks
- **T1-MID** (free, mid-range): `qwen3-coder:30b` — MODERATE-SMALL single features
- **T1-CLOUD** (free, powerful): `qwen3-coder:480b-cloud` — MODERATE-LARGE feature sets
- **T2-FLASH** (Gemini): `gemini-2.5-flash` — COMPLEX fast (debug, iterations)
- **T2-PRO** (Gemini): `gemini-2.5-pro` — COMPLEX deep (architecture, security audit)
- **T2-KIMI** (HuggingFace): `Kimi-K2-Instruct` — COMPLEX math/stats/algorithms
- **T3** (Claude): `claude-sonnet-4-6` — **EPIC ONLY** (greenfield, platform design)

The **LangGraph enforcement engine** (`langgraph_tier.py`) physically prevents T3 access except for EPIC tasks or full chain exhaustion. The **tier-enforcer-mcp** MCP server (`server.py`) exposes `execute_task()` — the single mandatory entry point for all tasks.

---

## Architecture

### LangGraph Enforcement Graph

```
                    User Task
                        │
                        ▼
              ┌─────────────────┐
              │  execute_task() │  ← MANDATORY first call for every task
              │  MCP Tool       │
              └────────┬────────┘
                        │ invokes run_tier_graph()
                        ▼
         ╔══════════════════════════════════╗
         ║   LANGGRAPH ENFORCEMENT GRAPH   ║
         ╠══════════════════════════════════╣
         ║                                  ║
         ║  ┌─────────────────────────┐     ║
         ║  │  1. classify_node       │     ║
         ║  │  HARD GATE — ALWAYS 1st │     ║
         ║  │  reads ROUTING_RULES    │     ║
         ║  │  from server.py         │     ║
         ║  └────────────┬────────────┘     ║
         ║               │ assigns tier     ║
         ║               ▼                  ║
         ║  ┌─────────────────────────┐     ║
         ║  │  2. t3_gate_node        │     ║
         ║  │  HARD BLOCK: T3 unless  │     ║
         ║  │  EPIC or chain_exhausted│     ║
         ║  └────────────┬────────────┘     ║
         ║               │                  ║
         ║     ┌─────────┴──────────┐       ║
         ║     │  3. execute_node   │       ║
         ║     │  T1-LOCAL          │       ║
         ║     │  T1-MID            │       ║
         ║     │  T1-CLOUD          │       ║
         ║     │  T2-FLASH          │       ║
         ║     │  T2-PRO            │       ║
         ║     │  T2-KIMI           │       ║
         ║     └─────────┬──────────┘       ║
         ║               │                  ║
         ║  ┌────────────▼────────────┐     ║
         ║  │  4. quality_gate_node   │     ║
         ║  │  score ≥ 0.75 → pass    │     ║
         ║  │  score < 0.75 → escalate│     ║
         ║  │  chain exhausted → T3   │     ║
         ║  └────────────┬────────────┘     ║
         ║               │                  ║
         ║  ┌────────────▼────────────┐     ║
         ║  │  5. audit_node          │     ║
         ║  │  routing.log (JSONL)    │     ║
         ║  │  memory.db (SQLite)     │     ║
         ║  │  LangSmith trace        │     ║
         ║  └─────────────────────────┘     ║
         ╚══════════════════════════════════╝
```

### Full System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CLAUDE-TIER-MACMINI v5.1 — FULL SYSTEM                  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Claude CLI Session (activated immediately after OAuth auth)        │   │
│  │                                                                     │   │
│  │  Layer 1: OAuth auth (pre-MCP, never routed)                       │   │
│  │  Layer 2: Every user task → execute_task() → LangGraph             │   │
│  │                                                                     │   │
│  │  Injection: ~/.zshrc claude() → --append-system-prompt             │   │
│  │             tier-routing.md (v5.1) loaded every session            │   │
│  │  SessionStart hook: pre-flight banner + T1/T2 health check         │   │
│  └─────────────────────────┬───────────────────────────────────────────┘   │
│                             │ execute_task()                                │
│                             ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  tier-enforcer-mcp  (Python · fastmcp 3.1.0)                        │  │
│  │  ~/tier-enforcer-mcp/server.py                                       │  │
│  │                                                                      │  │
│  │  ROUTING_RULES (single source of truth)                              │  │
│  │  execute_task() → run_tier_graph() → langgraph_tier.py              │  │
│  │  classify → t3_gate → execute → quality_gate → audit                │  │
│  └─────────┬──────────┬──────────┬──────────┬─────────┬───────────────┘  │
│             │          │          │          │         │                    │
│             ▼          ▼          ▼          ▼         ▼                    │
│  ┌────────────┐ ┌──────────┐ ┌────────┐ ┌────────┐ ┌──────┐              │
│  │ T1-LOCAL   │ │ T1-MID   │ │T1-CLOUD│ │T2-FLASH│ │T2-PRO│              │
│  │qwen2.5-    │ │qwen3-    │ │qwen3-  │ │gemini- │ │gemini│              │
│  │coder:7b    │ │coder:30b │ │coder:  │ │2.5-    │ │2.5-  │              │
│  │localhost   │ │localhost │ │480b    │ │flash   │ │pro   │              │
│  │SIMPLE      │ │MOD-SMALL │ │MOD-LRG │ │COMPLEX │ │CMPLX │              │
│  └────────────┘ └──────────┘ └────────┘ └────────┘ └──────┘              │
│                                                                             │
│  ┌───────────────────────┐    ┌─────────────────────────────────────────┐  │
│  │ T2-KIMI               │    │ T3 (Claude — EPIC only)                 │  │
│  │ Kimi-K2-Instruct      │    │ claude-sonnet-4-6                       │  │
│  │ HuggingFace API       │    │ Hard-gated: BLOCKED unless EPIC         │  │
│  │ COMPLEX-REASON        │    │ or full T1→T2 chain exhausted           │  │
│  │ (math/stats/algo)     │    │                                         │  │
│  └───────────────────────┘    └─────────────────────────────────────────┘  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  OBSERVABILITY                                                       │  │
│  │  LangSmith: smith.langchain.com · project: dsr-ai-lab-tier-routing  │  │
│  │  Routing Log: ~/.tier-enforcer/routing.log (JSONL, every decision)  │  │
│  │  Memory DB: ~/.tier-enforcer/memory.db (SQLite, short+long-term)    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Tier Definitions

| Tier | Model | Host | Complexity | Description |
|------|-------|------|-----------|-------------|
| **T1-LOCAL** | `qwen2.5-coder:7b` | `localhost:11434` | SIMPLE | Single file, config, shell, rename, <20 lines |
| **T1-MID** | `qwen3-coder:30b` | `localhost:11434` | MODERATE-SMALL | Single features, new classes, unit tests, API endpoints |
| **T1-CLOUD** | `qwen3-coder:480b-cloud` | `localhost:11434` | MODERATE-LARGE | Feature sets, pipelines, multi-file, new modules |
| **T2-FLASH** | `gemini-2.5-flash` | Google API | COMPLEX-FAST | Debug cycles, refactor, e2e wiring, iteration |
| **T2-PRO** | `gemini-2.5-pro` | Google API | COMPLEX-DEEP | Architecture, security audit, deep analysis, system design |
| **T2-KIMI** | `moonshotai/Kimi-K2-Instruct` | HuggingFace API | COMPLEX-REASON | Math, statistics, algorithms, proofs, Bayesian, ML |
| **T3** | `claude-sonnet-4-6` | Anthropic | EPIC | Greenfield systems, new platforms, build-from-scratch — **EPIC only** |

**Fallback chain:** `T1-LOCAL → T1-MID → T1-CLOUD → T2-FLASH → T2-PRO → T2-KIMI → T3`

---

## Complexity → Tier Routing

| Complexity | Keywords (examples) | Assigned Tier |
|-----------|---------------------|---------------|
| SIMPLE | single file edit, config, shell, rename | T1-LOCAL |
| MODERATE-SMALL | implement, create feature, new class, unit test, api endpoint | T1-MID |
| MODERATE-LARGE | feature set, pipeline, new module, database schema, ai agent | T1-CLOUD |
| COMPLEX-FAST | debug, fix bug, refactor, multi-file, cross-module, e2e wire | T2-FLASH |
| COMPLEX-DEEP | architecture, security audit, system design, deep analysis, rca | T2-PRO |
| COMPLEX-REASON | math, statistic, algorithm, proof, formula, bayesian, matrix | T2-KIMI |
| EPIC | greenfield, new platform, full system, build entire, from scratch | T3 |

> **Single Source of Truth:** `ROUTING_RULES` dict in `server.py` — drives both `classify_node` in LangGraph and the `tier_classify()` MCP tool.

---

## LangGraph Enforcement Engine

The `execute_task()` MCP tool triggers the full LangGraph graph — **no node can be skipped**.

### Graph Nodes (mandatory, in order)

| Node | Function | Description |
|------|----------|-------------|
| `classify_node` | HARD GATE 1 | Reads `ROUTING_RULES` from `server.py`. Assigns complexity + tier. **Cannot be skipped.** |
| `t3_gate_node` | HARD GATE 2 | Blocks T3 unless `complexity==EPIC` or `chain_exhausted==True`. |
| `execute_node` | Execution | Calls T1 (Ollama), T2 (Gemini/HF), or approves T3. |
| `quality_gate_node` | HARD GATE 3 | Scores output 0.0–1.0. ≥0.75 → proceed. <0.75 → escalate one tier. |
| `audit_node` | Audit | Writes `routing.log`. Updates SQLite. Updates LangSmith trace. |

### Fallback Flow

```
classify_node
    │
    ├── SIMPLE  → t1_local_node  → quality_gate → PASS(≥0.75) → audit
    │                                           → FAIL(<0.75) → t1_mid_node → ...
    ├── MOD-SM  → t1_mid_node   → quality_gate → PASS → audit
    │                                           → FAIL → t1_cloud_node → ...
    ├── MOD-LG  → t1_cloud_node → quality_gate → PASS → audit
    │                                           → FAIL → t2_flash_node → ...
    ├── CMPLX-F → t2_flash_node → quality_gate → PASS → audit
    │                                           → FAIL → t2_pro_node → ...
    ├── CMPLX-D → t2_pro_node  → quality_gate → PASS → audit
    │                                           → FAIL → t2_kimi_node → ...
    ├── CMPLX-R → t2_kimi_node → quality_gate → PASS → audit
    │                                           → FAIL → chain_exhausted=True → t3_gate
    └── EPIC    → t3_gate_node  (approved) → audit → T3 responds directly
```

### Memory Architecture

```
Short-term memory (in-session):
  TierState.short_term_memory[]  ← last 10 tasks, enriches each prompt

Long-term memory (cross-session SQLite):
  ~/.tier-enforcer/memory.db
  Tables: long_term_memory, project_patterns
  Queried at classify_node to inform tier selection
```

---

## Quick Start

### 1. Clone & Setup tier-enforcer-mcp

```bash
git clone https://github.com/dineshsrivastava07-cell/Claude-Tier-MacMini.git
cd Claude-Tier-MacMini

# Install Python deps (Python 3.14)
pip install fastmcp langgraph langchain-core langchain-ollama \
            langchain-google-genai langsmith huggingface_hub

# Install tier-routing prompt
cp prompts/system-prompt-v5.md ~/.claude/tier-routing.md
```

### 2. Register tier-enforcer-mcp (Claude CLI — user scope)

```bash
claude mcp add --scope user tier-enforcer python3 \
  ~/Claude-Tier-MacMini/tier-enforcer-mcp/server.py \
  -e OLLAMA_LOCAL_HOST=http://localhost:11434 \
  -e OLLAMA_CLOUD_HOST=http://localhost:11434 \
  -e QUALITY_THRESHOLD=0.75 \
  -e HF_API_KEY=<your-hf-key> \
  -e LANGCHAIN_API_KEY=<your-langsmith-key> \
  -e LANGCHAIN_PROJECT=dsr-ai-lab-tier-routing \
  -e LANGCHAIN_TRACING_V2=true \
  -e T3_MONTHLY_TOKEN_CAP=50000 \
  -e T3_DAILY_TOKEN_CAP=5000
```

### 3. Install SessionStart Hook

Add to `~/.claude/settings.local.json`:
```json
{
  "hooks": {
    "SessionStart": [{
      "hooks": [{
        "type": "command",
        "command": "<pre-flight banner command from settings.local.json>"
      }]
    }]
  }
}
```

### 4. Wrap Claude CLI in zshrc

```bash
# Add to ~/.zshrc:
export CLAUDE_TIER_PROMPT="$HOME/.claude/tier-routing.md"
claude() {
  "$HOME/.local/bin/claude" \
    --append-system-prompt "$(cat "$CLAUDE_TIER_PROMPT")" "$@"
}
alias claude-raw="$HOME/.local/bin/claude"  # bypass if needed
```

### 5. Verify All Tiers

```bash
# Health check (from Claude CLI — calls tier_health_check MCP tool)
claude> tier_health_check()

# Manual live tests
curl -s http://localhost:11434/api/chat \
  -d '{"model":"qwen2.5-coder:7b","stream":false,"messages":[{"role":"user","content":"say: T1-LOCAL-OK"}]}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['message']['content'])"

GOOGLE_GENAI_USE_GCA=true gemini --model gemini-2.5-flash "say: T2-FLASH-OK"
```

---

## MCP Servers (22 total)

### Core Tier Routing
| Server | Type | Scope | Purpose |
|--------|------|-------|---------|
| `tier-enforcer` | Python (fastmcp) | User + Desktop | Master routing gate, `execute_task()`, LangGraph |
| `tier-router` | TypeScript (18 tools) | User | Routing tools, T1/T2/T3 tools, pipelines |

### Development MCP Suite
| Server | Tools |
|--------|-------|
| `intent-mcp` | parse_intent, scope_task, clarify_ambiguity, detect_scope_creep |
| `arch-mcp` | review_architecture, generate_architecture, create_adr, detect_violations |
| `coding-mcp` | multi_file_edit, cross_module_refactor, dependency_chain, validate_code |
| `rca-mcp` | analyze_error, trace_bug, generate_fix, regression_check, post_mortem |
| `integration-mcp` | e2e_wire, wire_api, validate_contract, test_integration, generate_mock |
| `aidev-mcp` | scaffold_ai_app, generate_prompt_template, build_chain, evaluate_llm_output |
| `math-mcp` | solve_equation, run_statistics, implement_algorithm, validate_math |
| `budget-mcp` | check_budget, record_usage, get_savings_report |
| `context-mcp` | get_project_context, refresh_project_context, save_session_context |
| `rpa-mcp` | record_workflow, generate_playwright_script, validate_rpa_output |

### Speciality MCP Suite
| Server | Tools |
|--------|-------|
| `mobile-dev-mcp` | scaffold_mobile_app, generate_screen, setup_navigation, setup_state_management |
| `webmobile-dev-mcp` | scaffold_web_app, setup_pwa, generate_api_route, generate_responsive_layout |
| `website-dev-mcp` | scaffold_website, generate_landing_page_sections, generate_seo_config |
| `ecommerce-mcp` | scaffold_ecommerce_app, generate_cart_store, generate_razorpay_integration |
| `mac-automation-mcp` | run_applescript, control_app, finder_operation, screen_capture |
| `files-automation-mcp` | organize_folder, batch_rename, find_duplicates, sync_folders |

### Standard MCP Servers
`filesystem` · `git` · `memory` · `github` · `gdrive`

---

## tier-router-mcp Tools (18 total)

### Routing Tools
| Tool | Description |
|------|------------|
| `tier_route_task` | Auto-route with quality-gate fallback |
| `tier_health_check` | Probe all 7 tier endpoints + latency |
| `tier_explain_decision` | Classify without executing (dry-run) |
| `tier_override` | Force a specific tier |

### T1 Tools (Ollama)
| Tool | Model | Use |
|------|-------|-----|
| `t1_local_generate` | qwen2.5-coder:7b | Fast SIMPLE code generation |
| `t1_local_complete` | qwen2.5-coder:7b | Fill-in-the-middle |
| `t1_cloud_generate` | qwen3-coder:480b | MODERATE code generation |
| `t1_cloud_analyze` | qwen3-coder:480b | Audit, analysis |

### T2 Tools (Gemini)
| Tool | Model | Use |
|------|-------|-----|
| `t2_gemini_pro_reason` | gemini-2.5-pro | Deep reasoning, architecture |
| `t2_gemini_flash_generate` | gemini-2.5-flash | Fast COMPLEX generation |
| `t2_gemini_lite_validate` | gemini-2.5-flash-lite | Schema validation, linting |
| `t2_gemini_analyze_image` | gemini-2.5-pro | Image/diagram analysis |

### T3 Tools (Claude)
| Tool | Model | Use |
|------|-------|-----|
| `t3_claude_architect` | claude-sonnet-4-6 | Architecture decisions |
| `t3_claude_epic` | claude-sonnet-4-6 | Full EPIC feature builds |

### Pipeline Tools
| Tool | Chain |
|------|-------|
| `pipeline_code_review` | T1 lint → T2 semantic → T3 architecture |
| `pipeline_debug_chain` | T1 hypothesis → T2 analysis → T3 root-cause |
| `pipeline_build_fullstack` | T1 scaffold → T2 logic → T3 hardening |
| `pipeline_qa_full` | T1 unit → T2 integration → T3 E2E |

---

## Environment Variables

```bash
# Ollama (T1 tiers — all local)
OLLAMA_LOCAL_HOST=http://localhost:11434
OLLAMA_CLOUD_HOST=http://localhost:11434

# HuggingFace (T2-KIMI)
HF_API_KEY=<your-key>

# LangSmith (observability)
LANGCHAIN_API_KEY=<your-key>
LANGCHAIN_PROJECT=dsr-ai-lab-tier-routing
LANGCHAIN_TRACING_V2=true

# Quality gate
QUALITY_THRESHOLD=0.75

# T3 budget caps
T3_MONTHLY_TOKEN_CAP=50000
T3_DAILY_TOKEN_CAP=5000

# Routing log
TIER_LOG=~/.tier-enforcer/routing.log
```

---

## Session Start Procedure

Every Claude CLI session runs automatically:

```
1. SessionStart hook → pre-flight banner fires
2. tier_health_check()  → all 7 tiers verified live
3. check_budget()       → T3 daily/monthly cap status
4. get_project_context() → project knowledge loaded
5. Ready — execute_task() enforced for all user tasks
```

---

## Version History

| Version | Date | Key Addition |
|---------|------|-------------|
| v1.0 | 2026-02 | TypeScript MCP server (18 tools) |
| v2.0 | 2026-02 | Base routing prompt, skill layer |
| v3.0 | 2026-03-02 | SIMPLE→T1-LOCAL strict enforcement |
| v4.0 | 2026-03-04 | Native Tool Fraud patch, sub-task routing |
| v4.1 | 2026-03-04 | Header Precision Rules |
| **v5.1** | **2026-03-12** | **7 tiers, LangGraph hard enforcement, T1-MID (qwen3-coder:30b), T2-KIMI (Kimi-K2), SQLite memory, LangSmith tracing, execute_task() master entry point** |

---

*Mac Mini · Apple Silicon · macOS · Claude CLI v5.1 · 7-Tier Strict Routing · LangGraph Enforced*
