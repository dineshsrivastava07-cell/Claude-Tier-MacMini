# Claude-Tier-MacMini — 4-Tier AI Routing for Claude CLI

![Version](https://img.shields.io/badge/version-v4.1-blue) ![Platform](https://img.shields.io/badge/platform-Mac%20Mini%20Apple%20Silicon-black) ![Ollama](https://img.shields.io/badge/T1-Ollama%20Qwen-orange) ![Gemini](https://img.shields.io/badge/T2-Gemini%202.5-blue) ![Claude](https://img.shields.io/badge/T3-Claude%20Sonnet-purple) ![MCP](https://img.shields.io/badge/MCP-18%20tools-green)

Strict 4-Tier AI routing enforcement for Claude CLI and Claude Desktop on Mac Mini (Apple Silicon). Every task is classified by complexity and routed to the optimal model — local Qwen first, escalating through Gemini to Claude only when necessary. **v4.0 patches Native Tool Fraud. v4.1 adds Header Precision Rules.**

---

## Overview

Claude-Tier-MacMini enforces a cost-optimised, quality-gated AI routing discipline:

- **T1-LOCAL** (free, fast): `qwen2.5-coder:7b` via Ollama — handles all SIMPLE tasks
- **T1-CLOUD** (free, powerful): `qwen3-coder:480b` via Ollama — handles MODERATE multi-file work
- **T2** (Google Gemini): `gemini-2.5-pro / flash` — handles COMPLEX analytics, architecture, security
- **T3** (Claude): `claude-sonnet-4-6` — **EPIC only** (greenfield apps, platform design)

Two MCP servers enforce this: **tier-router-mcp** (TypeScript, Claude CLI soft gate) and **tier-enforcer-mcp** (Python, Claude Desktop hard gate with T3 physically blocked).

---

## Architecture

### Path A — Claude CLI (Soft Enforcement via System Prompt)

```
┌──────────────┐    ┌─────────────────────────────────────────────────────────┐
│  User types  │    │  ~/.zshrc  claude() function                            │
│  claude ...  │───▶│  claude-raw --append-system-prompt tier-routing.md "$@" │
└──────────────┘    └─────────────────────┬───────────────────────────────────┘
                                          │ tier-routing.md injected as system prompt
                                          ▼
                    ┌─────────────────────────────────────────────────────────┐
                    │  Claude CLI Session                                     │
                    │  ┌─────────────────────────────────────────────────┐   │
                    │  │  Routing Decision Engine (in system prompt)      │   │
                    │  │  1. Classify complexity (SIMPLE/MOD/COMPLEX/EPIC)│   │
                    │  │  2. Assign tier via routing matrix               │   │
                    │  │  3. Make actual API call to assigned tier        │   │
                    │  │  4. Score quality (0.0–1.0) → escalate if <0.75 │   │
                    │  └──────────────────┬──────────────────────────────┘   │
                    │                     │ MCP tools available               │
                    │                     ▼                                   │
                    │  ┌──────────────────────────────────────────────────┐  │
                    │  │  tier-router-mcp (TypeScript, 18 tools)          │  │
                    │  └──────┬───────────┬──────────────┬────────────────┘  │
                    └─────────│───────────│──────────────│────────────────────┘
                              │           │              │
                    ┌─────────▼──┐  ┌─────▼──────┐  ┌──▼─────────────────┐
                    │ T1-LOCAL   │  │ T1-CLOUD   │  │ T2-PRO / T2-FLASH  │
                    │ qwen2.5-   │  │ qwen3-     │  │ gemini-2.5-pro     │
                    │ coder:7b   │  │ coder:480b │  │ gemini-2.5-flash   │
                    │ SIMPLE     │  │ MODERATE   │  │ COMPLEX            │
                    └────────────┘  └────────────┘  └────────────────────┘
                              (T3 = Claude itself — EPIC tasks only)
```

### Path B — Claude Desktop (Hard Gate via tier-enforcer-mcp)

```
┌──────────────────┐    ┌──────────────────────────────────────────────────┐
│  Claude Desktop  │───▶│  tier-enforcer-mcp (Python, fastmcp 3.1.0)       │
│  (user prompt)   │    │  ~/tier-enforcer-mcp/server.py                   │
└──────────────────┘    │                                                  │
                        │  Step 1: tier_classify(prompt, context)          │
                        │  Step 2: Route to correct tool:                  │
                        │    SIMPLE   → t1_local_execute()                 │
                        │    MODERATE → t1_cloud_execute()                 │
                        │    COMPLEX  → t2_gemini_execute()                │
                        │    EPIC     → t3_epic_gate() ──► if APPROVED     │
                        │                                                  │
                        │  ┌──────────────────────────────────────────┐   │
                        │  │  T3 HARD GATE — t3_epic_gate()           │   │
                        │  │  Non-EPIC? → returns status=BLOCKED ❌   │   │
                        │  │  EPIC?     → returns status=APPROVED ✅  │   │
                        │  └──────────────────────────────────────────┘   │
                        │  Step 5: tier_audit_log() — always last          │
                        └──────────────────────────────────────────────────┘
```

---

## What's New

### Version Changelog

| Version | Key Change | Bug Fixed |
|---------|-----------|-----------|
| v1.0 | Initial 4-tier MCP server (TypeScript) | — |
| v2.0 | Base routing prompt added | — |
| v3.0 | SIMPLE→T1-LOCAL strict enforcement | SIMPLE tasks with unmapped type falling through to T3 |
| **v4.0** | **Native Tool Fraud patch** | Claude using Read/Edit/Write to self-generate content for SIMPLE/MODERATE tasks, bypassing tier system entirely |
| **v4.1** | **Header Precision Rules** | `API Call Made` field showing "YES" before call completed; endpoint/model mismatch in headers; Fallback Path always starting from T1-LOCAL regardless of assigned tier |

### v4.0 — The Native Tool Fraud Problem (Patched)

**The bug:** Claude CLI was using its own native tools (Read/Edit/Write) to generate content directly — bypassing the tier system entirely. The routing header claimed T1-CLOUD but T3 was silently doing all the work.

```
FRAUDULENT (before v4.0):
  Header claimed: "T1-CLOUD + T3 to apply fixes"
  Reality: T3 read file → T3 generated 4 lines → T3 wrote file
  Zero Ollama calls made. The routing header was a lie.

CORRECT (after v4.0):
  Step 1: Classify → SIMPLE (4-line config edit)
  Step 2: Read file via Bash (gathering context — allowed)
  Step 3: curl -s localhost:11434/api/chat  ← ACTUAL API CALL (required)
          model: qwen2.5-coder:7b
  Step 4: Receive qwen output
  Step 5: Score quality → apply via Write tool (applying T1 output — allowed)
  Header: "API Call Made: YES → localhost:11434 ✅"
```

### v4.1 — Header Precision Rules

| Rule | Before v4.1 | After v4.1 |
|------|------------|-----------|
| API Call Made timing | `YES` written before call completes | `IN PROGRESS` before → `YES` after |
| Endpoint-model match | `localhost:11434` + `qwen3-coder:480b` (inconsistent) | Endpoint must match model identity |
| Fallback Path | Always shows `T1-LOCAL → T1-CLOUD → T2-FLASH → T3` | Starts from **assigned** tier |

---

## Components

| | tier-router-mcp | tier-enforcer-mcp |
|---|---|---|
| **Type** | TypeScript MCP Server | Python MCP Server (fastmcp 3.1.0) |
| **Target** | Claude CLI | Claude Desktop |
| **Enforcement** | Soft (prompt-based) | Hard (MCP gate — T3 physically blocked) |
| **Tools** | 18 tools | 7 tools |
| **Resources** | 3 (config, metrics, log) | none |
| **Path** | `~/tier-router-mcp/` | `~/tier-enforcer-mcp/` |
| **Tests** | 43/43 passing | — |
| **T3 Gate** | Prompt warns against T3 | `t3_epic_gate` returns `BLOCKED` for non-EPIC |

---

## Quick Start

### tier-router-mcp (Claude CLI)

```bash
# Build
cd ~/tier-router-mcp && npm install && npm run build

# Register with Claude CLI (user scope — persists across sessions)
claude mcp add --scope user tier-router node ~/tier-router-mcp/dist/index.js \
  -e OLLAMA_LOCAL_HOST=http://localhost:11434 \
  -e QUALITY_THRESHOLD=0.75

# Verify
claude mcp list
# tier-router: ✓ Connected
```

### tier-enforcer-mcp (Claude Desktop)

```bash
# Install dependencies
cd ~/tier-enforcer-mcp && pip install fastmcp

# Register in Claude Desktop config
# Add to ~/Library/Application Support/Claude/claude_desktop_config.json:
# "tier-enforcer": {
#   "command": "python3",
#   "args": ["/Users/dsr-ai-lab/tier-enforcer-mcp/server.py"],
#   "env": {
#     "OLLAMA_LOCAL_HOST": "http://localhost:11434",
#     "OLLAMA_CLOUD_HOST": "http://localhost:11434",
#     "QUALITY_THRESHOLD": "0.75"
#   }
# }
```

### System Prompt v4.0 (Claude CLI injection)

```bash
# Install active system prompt
cp prompts/system-prompt-v4.md ~/.claude/tier-routing.md

# Ensure zshrc wraps claude binary (add if not present):
# claude() {
#   "$HOME/.local/bin/claude" \
#     --append-system-prompt "$(cat ~/.claude/tier-routing.md)" "$@"
# }
```

---

## Tier Routing Rules

### Complexity Classification

| Complexity | Task Examples | Assigned Tier |
|-----------|--------------|---------------|
| **SIMPLE** | Single file edit (<20 lines), shell commands, config changes, unit test for one function, rename/format | **T1-LOCAL** |
| **MODERATE** | 2–10 files, feature-sized work, API integration, multi-function refactor | **T1-CLOUD** |
| **COMPLEX** | Statistics/ML, security audit, long-context analysis (50+ files), algorithm design | **T2-PRO / T2-FLASH** |
| **EPIC** | Greenfield app, multi-service architecture, 10+ files from scratch, platform design | **T3** |

### Routing Matrix

| Task Type | SIMPLE | MODERATE | COMPLEX | EPIC |
|-----------|--------|----------|---------|------|
| CODE_GEN | T1-LOCAL | T1-CLOUD | T2-FLASH | T3 |
| CODE_FIX | T1-LOCAL | T1-CLOUD | T2-FLASH | T3 |
| REFACTOR | T1-LOCAL | T1-CLOUD | T2-FLASH | T3 |
| DEBUG | T1-LOCAL | T1-CLOUD | T2-FLASH | T3 |
| QA | T1-LOCAL | T1-CLOUD | T2-PRO | T3 |
| INTEGRATION | T1-LOCAL | T1-CLOUD | T2-PRO | T3 |
| ARCHITECTURE | T1-LOCAL | T2-PRO | T2-PRO | T3 |
| ANALYTICS | T1-LOCAL | T2-PRO | T2-PRO | T3 |
| FULLSTACK | T1-LOCAL | T2-PRO | T3 | T3 |

> **Key rule:** Complexity is classified **first**, before task type. SIMPLE always stops at T1-LOCAL — no exceptions, no matter the task type.

### Shell/Explore Remapping (always SIMPLE → T1-LOCAL)

| User says | Real operation | Tier |
|-----------|--------------|------|
| "connect to project" | `ls + git log` | T1-LOCAL |
| "explore directory" | `ls -la` | T1-LOCAL |
| "check git history" | `git log` | T1-LOCAL |
| "what's in this file" | `cat` | T1-LOCAL |
| "inspect project" | `ls + git status` | T1-LOCAL |

---

## System Prompt v4.0

The `prompts/system-prompt-v4.md` file is injected into every Claude CLI session via `--append-system-prompt`. It enforces the full routing discipline in-session.

**What it contains:**
- Routing Decision Engine (3 steps: classify → matrix → execute)
- Native Tool Permission Map
- Mandatory routing header format
- Fraud detection checklist
- Sub-task routing rules
- Fallback chain with quality gate

**Install:**
```bash
cp prompts/system-prompt-v4.md ~/.claude/tier-routing.md
```

**What v4.0 fixes over v3.0:**

| | v3.0 | v4.0 |
|---|---|---|
| SIMPLE + unmapped task type | → T3 ❌ | → T1-LOCAL ✅ |
| Native tool content generation | Allowed (fraud) ❌ | BANNED for SIMPLE/MODERATE ✅ |
| Read → generate → write pattern | T3 work disguised as T1 ❌ | Read OK; generate = must call Ollama ✅ |
| `API Call Made` header field | Optional ❌ | Mandatory fraud detector ✅ |
| Sub-task routing | Single tier for whole request ❌ | Each sub-task individually classified ✅ |

---

## Tier Enforcer MCP

Physical routing gate for **Claude Desktop**. Unlike the system prompt (soft enforcement), tier-enforcer-mcp physically executes Ollama and Gemini calls and hard-blocks T3 for non-EPIC tasks.

**File:** `tier-enforcer-mcp/server.py` (Python, fastmcp 3.1.0, 309 lines)
**System Prompt:** `tier-enforcer-mcp/SYSTEM_PROMPT_V5.txt`

### 7 Tools

| Tool | Purpose |
|------|---------|
| `tier_classify` | Classify prompt → complexity + next_tool recommendation |
| `t1_local_execute` | Execute via Ollama qwen2.5-coder:7b (SIMPLE tasks) |
| `t1_cloud_execute` | Execute via Ollama qwen3-coder:480b (MODERATE tasks) |
| `t2_gemini_execute` | Execute via Gemini CLI with Google auth (COMPLEX tasks) |
| `t3_epic_gate` | Gate check for T3 — returns BLOCKED for non-EPIC, APPROVED for EPIC |
| `tier_health_check` | Check Ollama and Gemini availability + latency |
| `tier_audit_log` | Log routing decision to ~/.tier-enforcer/routing.log |

### Mandatory Workflow

```
Every task — zero exceptions:
[1] tier_classify(prompt, context)     ← ALWAYS FIRST
[2] Call next_tool from classify result:
      SIMPLE   → t1_local_execute()
      MODERATE → t1_cloud_execute()
      COMPLEX  → t2_gemini_execute()
      EPIC     → t3_epic_gate() → if APPROVED, generate yourself
[3] If result.passed_gate=false → call result.escalate_to
[4] Apply output via Edit/Write/Bash (APPLY only, never GENERATE)
[5] tier_audit_log()                   ← ALWAYS LAST
```

---

## tier-router-mcp Tools (18 total)

### Routing Tools
| Tool | Description |
|------|------------|
| `tier_route_task` | Auto-route with quality-gate fallback (main entry point) |
| `tier_health_check` | Probe tier availability and latency |
| `tier_explain_decision` | Classify prompt without executing (dry-run) |
| `tier_override` | Force a specific tier |

### T1 Tools (Ollama)
| Tool | Model | Use |
|------|-------|-----|
| `t1_local_generate` | qwen2.5-coder:7b | Fast code generation |
| `t1_local_complete` | qwen2.5-coder:7b | Fill-in-the-middle completion |
| `t1_cloud_generate` | qwen3-coder:480b | High-quality generation |
| `t1_cloud_analyze` | qwen3-coder:480b | Security/performance audit |

### T2 Tools (Gemini)
| Tool | Model | Use |
|------|-------|-----|
| `t2_gemini_pro_reason` | gemini-2.5-pro | Deep reasoning, architecture |
| `t2_gemini_flash_generate` | gemini-2.5-flash | Fast generation, balanced quality |
| `t2_gemini_lite_validate` | gemini-2.5-flash-lite | Schema validation, linting |
| `t2_gemini_analyze_image` | gemini-2.5-pro | Image/diagram analysis |

### T3 Tools (Claude)
| Tool | Model | Use |
|------|-------|-----|
| `t3_claude_architect` | claude-sonnet-4-6 | Architecture decisions |
| `t3_claude_epic` | claude-sonnet-4-6 | Full feature builds (EPIC) |

### Pipeline Tools (Multi-tier)
| Tool | Tier Chain |
|------|-----------|
| `pipeline_code_review` | T1 lint → T2 semantic → T3 architecture |
| `pipeline_debug_chain` | T1 hypothesis → T2 analysis → T3 root-cause |
| `pipeline_build_fullstack` | T1 scaffold → T2 logic → T3 hardening |
| `pipeline_qa_full` | T1 unit → T2 integration → T3 E2E |

### Resources
| URI | Content |
|-----|---------|
| `tier://config` | Tier config, models, costs, fallback chains |
| `tier://metrics` | Per-tier call counts, success rates, avg quality/latency |
| `tier://routing-log` | Last 50 routing decisions |

---

## Prompt Files

| File | Version | Status | Purpose |
|------|---------|--------|---------|
| `prompts/system-prompt-v4.md` | v4.0 + v4.1 | **ACTIVE** | Install to `~/.claude/tier-routing.md` |
| `prompts/system-prompt-v3.md` | v3.0 | Legacy | Previous active prompt |
| `prompts/tier-enforcer-setup-v5.md` | v5 | Reference | tier-enforcer-mcp setup guide |
| `prompts/implement-tier-enforcer.md` | — | Reference | Implementation guide for tier-enforcer-mcp |
| `prompts/specs/strict-routing-v4-spec.md` | v4.0 | Spec | Full v4.0 specification |
| `prompts/specs/strict-routing-v4-1-patch.md` | v4.1 | Spec | Header Precision Rules patch |
| `prompts/specs/strict-routing-v4-1-patch2.md` | v4.1 | Spec | Second v4.1 precision patch |
| `prompts/specs/mcp-server-prompt.md` | — | Spec | MCP server integration prompt spec |
| `prompts/specs/strict-routing-v3-spec.md` | v3.0 | Legacy spec | v3.0 source spec |
| `prompts/specs/base-routing-prompt-v2.md` | v2.0 | Legacy spec | Base routing prompt v2.0 |

---

## Skill References

The `/tier-routing` skill (`skill/tier-routing.md`) provides the full routing identity. Detailed references in `skill/references/`:

| File | Content |
|------|---------|
| `t1-ollama.md` | Ollama client patterns, health checks, curl commands for T1-LOCAL/T1-CLOUD |
| `t2-gemini.md` | Gemini SDK + CLI patterns, model selection, auth methods |
| `t3-claude.md` | Claude SDK + CLI patterns, orchestration, system prompts |
| `routing-engine.md` | Full TypeScript source (classifier, scorer, fallback-chain, router) |
| `pipelines.md` | 5 pipeline implementations (code-review, debug, fullstack, QA, analytics) |
| `mcp-integration.md` | 18 MCP tools, 3 resources, registration commands |
| `retail-analytics.md` | ClickHouse SQL, FY date engine, RIECT KPIs, SPSF/Sell-Thru/DOI |
| `litellm-config.md` | LiteLLM proxy config, OpenAI-compatible unified endpoint |

---

## Fallback Chains

```
T1-LOCAL  → T1-CLOUD → T2-FLASH → T3
T1-CLOUD  → T2-FLASH → T3
T2-PRO    → T2-FLASH → T3
T2-FLASH  → T3
T3        → T3 (no further fallback)
```

**Quality gate:** 0.75 (default). If tier output scores below 0.75, escalate **one step** only.
**Offline fallback:** If T1-LOCAL offline → notify user → try T1-CLOUD. Never silently skip to T3.

---

## Environment Variables

```bash
# Ollama (T1)
OLLAMA_LOCAL_HOST=http://localhost:11434     # T1-LOCAL endpoint
OLLAMA_CLOUD_HOST=http://localhost:11434     # T1-CLOUD endpoint (same machine, larger model)
T1_LOCAL_TIMEOUT_MS=90000
T1_CLOUD_TIMEOUT_MS=300000

# Gemini (T2) — pick one auth method
GEMINI_API_KEY=...             # API key (optional — Google account auth used if unset)
GOOGLE_GENAI_USE_GCA=true      # Use Google Cloud account auth
T2_TIMEOUT_MS=60000

# Claude (T3)
ANTHROPIC_API_KEY=...          # API key (optional — claude CLI auth used if unset)
CLAUDE_MODEL=claude-sonnet-4-6
T3_TIMEOUT_MS=120000

# Quality Gate
QUALITY_THRESHOLD=0.75         # 0.0–1.0 — escalate if output scores below this

# Tier Enforcer Log
TIER_LOG=~/.tier-enforcer/routing.log
```

---

## Native Tool Permission Map

| Tool | Permitted? | Rule |
|------|-----------|------|
| `Bash` (read-only: ls, cat, git, grep) | ✅ Always | Gather context for T1/T2 prompt |
| `Bash` (write/execute) | ✅ Apply only | Apply T1/T2 output. EPIC tasks. |
| `Read` file | ✅ Always | Build context for T1/T2 prompt. Never substitute T1 work. |
| `Write` / `Edit` file | ⚠️ Restricted | ONLY to apply content generated by T1/T2/T3. NEVER to self-generate for SIMPLE/MODERATE. |
| Generate content (SIMPLE) | ❌ Banned | Must call T1-LOCAL Ollama API. |
| Generate content (MODERATE) | ❌ Banned | Must call T1-CLOUD Ollama API. |
| Generate content (COMPLEX) | ⚠️ T2 only | Must call Gemini API. |
| Generate content (EPIC) | ✅ T3 only | Claude generates directly. Only legitimate T3 case. |

---

## Anti-Patterns (B-01 to B-10)

| ID | What Went Wrong | Correct Behaviour |
|----|----------------|------------------|
| B-01 | SIMPLE + unmapped type → T3 fallthrough | SIMPLE = T1-LOCAL, always, all task types |
| B-02 | T3 edits config claiming T3 is the correct tier | SIMPLE config edit → T1-LOCAL Ollama call |
| B-03 | T3 reads file then generates content directly | Read is OK; generate = must call Ollama |
| B-04 | Routing header says T1 but zero Ollama calls made | `API Call Made` field must say YES + endpoint |
| B-05 | T1-CLOUD credited; only one call made for many sub-tasks | Each sub-task gets its own tier assignment |
| B-06 | Unmapped task type → T3 as catch-all | Use complexity default row: SIMPLE→T1-LOCAL |
| B-07 | "When in doubt" → escalate up to T3 | "When in doubt" → classify DOWN to T1-LOCAL |
| B-08 | T1-LOCAL offline → silently use T3 | Notify user → try T1-CLOUD → advance ONE step |
| B-09 | Routing header written after T3 work is complete | Classify FIRST, then call tier, then write header |
| B-10 | Sub-tasks not individually routed | Each distinct action gets its own complexity + tier |

---

## Development

```bash
# tier-router-mcp (TypeScript)
cd ~/tier-router-mcp
npm run build                                          # Compile TypeScript
npm test                                               # Unit tests (43 tests, no network)
INTEGRATION=true npx vitest run tests/integration/    # Integration tests (requires Ollama/Gemini)

# tier-enforcer-mcp (Python)
cd ~/tier-enforcer-mcp
pip install fastmcp                                    # Install dependency
python3 server.py                                      # Run MCP server directly

# Verify tier health
curl -s http://localhost:11434/api/tags \
  | python3 -c "import sys,json; [print(x['name']) for x in json.load(sys.stdin)['models']]"
```

---

## Health Check

```bash
# Check Ollama models available
curl -s http://localhost:11434/api/tags | python3 -c "
import sys, json
m = json.load(sys.stdin).get('models', [])
[print(f'✅ {x[\"name\"]}') for x in m if 'qwen' in x['name']] or print('❌ No qwen models')
"

# Quick T1-LOCAL test
curl -s http://localhost:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-coder:7b","stream":false,"messages":[{"role":"user","content":"say: T1-LOCAL OK"}]}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['message']['content'])"
```

---

*Mac Mini · Apple Silicon · macOS · Claude CLI v4.1 · Strict Tier Routing*
