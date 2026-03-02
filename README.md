# tier-router-mcp

A production-grade **Model Context Protocol (MCP) server** that implements intelligent 4-tier AI routing for Claude CLI. Routes every task to the optimal AI model automatically, with quality-gate fallback chains.

## Architecture

```
T1-LOCAL (qwen2.5-coder:7b)  ─┐
T1-CLOUD (qwen3-coder:480b)  ─┼─► Quality Gate (0.75) ──► Escalate if needed
T2-PRO   (gemini-2.5-pro)    ─┤
T2-FLASH (gemini-2.5-flash)  ─┤
T2-LITE  (gemini-2.5-flash-lite) ─┤
T3       (claude-sonnet-4-6) ─┘
```

**Routing logic:**
- Classifies task type (9 types) × complexity (4 levels) → selects optimal tier
- Executes tier → scores quality (0.0–1.0) → escalates if below threshold (default 0.75)
- Full fallback chains: e.g. `T1-LOCAL → T1-CLOUD → T2-FLASH → T3`

## Prerequisites

| Requirement | Purpose |
|---|---|
| Ollama + `qwen2.5-coder:7b` | T1-LOCAL |
| Ollama + `qwen3-coder:480b-cloud` | T1-CLOUD |
| `gemini` CLI (account auth) or `GEMINI_API_KEY` | T2 |
| `claude` CLI (account auth) or `ANTHROPIC_API_KEY` | T3 |
| Node.js 20+ | Runtime |

## Quick Start

```bash
# 1. Install
cd ~/tier-router-mcp && npm install && npm run build

# 2. Register with Claude CLI (already done if you followed setup)
claude mcp add tier-router node ~/tier-router-mcp/dist/index.js \
  -e OLLAMA_LOCAL_HOST=http://localhost:11434 \
  -e QUALITY_THRESHOLD=0.75

# 3. Verify connection
claude mcp list
# tier-router: ✓ Connected
```

## Tools (18 total)

### Routing Tools
| Tool | Description |
|---|---|
| `tier_route_task` | Auto-route with quality-gate fallback (main entry point) |
| `tier_health_check` | Probe tier availability and latency |
| `tier_explain_decision` | Classify prompt without executing (dry-run) |
| `tier_override` | Force a specific tier |

### T1 Tools (Ollama)
| Tool | Model |
|---|---|
| `t1_local_generate` | qwen2.5-coder:7b — fast, free |
| `t1_local_complete` | qwen2.5-coder:7b — fill-in-the-middle |
| `t1_cloud_generate` | qwen3-coder:480b — high-quality, free |
| `t1_cloud_analyze` | qwen3-coder:480b — security/perf audit |

### T2 Tools (Gemini)
| Tool | Model |
|---|---|
| `t2_gemini_pro_reason` | gemini-2.5-pro — deep reasoning |
| `t2_gemini_flash_generate` | gemini-2.5-flash — fast, balanced |
| `t2_gemini_lite_validate` | gemini-2.5-flash-lite — validation/linting |
| `t2_gemini_analyze_image` | gemini-2.5-pro — image/diagram analysis |

### T3 Tools (Claude)
| Tool | Model |
|---|---|
| `t3_claude_architect` | claude-sonnet-4-6 — architecture decisions |
| `t3_claude_epic` | claude-sonnet-4-6 — full feature builds |

### Pipeline Tools (Multi-tier)
| Tool | Tiers Used |
|---|---|
| `pipeline_code_review` | T1 lint → T2 semantic → T3 architecture |
| `pipeline_debug_chain` | T1 hypothesis → T2 analysis → T3 root-cause |
| `pipeline_build_fullstack` | T1 scaffold → T2 logic → T3 hardening |
| `pipeline_qa_full` | T1 unit → T2 integration → T3 E2E |

## Resources

| URI | Content |
|---|---|
| `tier://config` | Tier configuration, models, costs, fallback chains |
| `tier://metrics` | Per-tier call counts, success rates, avg quality/latency |
| `tier://routing-log` | Last 50 routing decisions |

## Environment Variables

```bash
# Ollama
OLLAMA_LOCAL_HOST=http://localhost:11434    # T1-LOCAL endpoint
OLLAMA_CLOUD_HOST=http://remote:11434      # T1-CLOUD endpoint (optional)
T1_LOCAL_TIMEOUT_MS=90000
T1_CLOUD_TIMEOUT_MS=300000

# Gemini (pick one)
GEMINI_API_KEY=...          # API key auth (optional — account auth used if unset)
T2_TIMEOUT_MS=60000

# Claude (pick one)
ANTHROPIC_API_KEY=...       # API key auth (optional — claude CLI used if unset)
CLAUDE_MODEL=claude-sonnet-4-6
T3_TIMEOUT_MS=120000

# Quality gate
QUALITY_THRESHOLD=0.75      # 0.0–1.0, escalate below this
```

## Fallback Chains

```
T1-LOCAL  → T1-CLOUD → T2-FLASH → T3
T1-CLOUD  → T2-FLASH → T3
T2-PRO    → T2-FLASH → T3
T2-FLASH  → T2-PRO   → T3
T2-LITE   → T2-FLASH → T1-CLOUD
T3        → T3 (no fallback)
```

## Development

```bash
npm run build         # Compile TypeScript
npm test              # Unit tests (43 tests, no network required)
INTEGRATION=true npx vitest run tests/integration/   # Integration tests (requires Ollama/Gemini)
```

## Task Types → Routing Matrix

| Task Type | SIMPLE | MODERATE | COMPLEX | EPIC |
|---|---|---|---|---|
| CODE_GEN | T1-LOCAL | T1-CLOUD | T1-CLOUD | T3 |
| DEBUG | T1-LOCAL | T1-CLOUD | T1-CLOUD | T3 |
| ARCHITECTURE | T1-LOCAL | T2-PRO | T2-PRO | T3 |
| ANALYTICS | T1-LOCAL | T2-PRO | T2-PRO | T3 |
| QA | T1-LOCAL | T1-CLOUD | T2-PRO | T3 |
| FULLSTACK | T1-LOCAL | T2-PRO | T3 | T3 |
| REFACTOR | T1-LOCAL | T1-CLOUD | T1-CLOUD | T3 |
| INTEGRATION | T1-LOCAL | T2-PRO | T2-PRO | T3 |

## System Prompt v3.0 — Strict Tier Routing Enforcement

The `prompts/` directory contains the Claude CLI system prompt that enforces strict tier routing on every session.

### v3.0 Critical Bug Fix

| | Before v3.0 | After v3.0 |
|---|---|---|
| SIMPLE + unmapped task type | → T3 (fallthrough) ❌ | → T1-LOCAL (correct) ✅ |
| "connect to project" | → INTEGRATION → T3 ❌ | → ls+git = SIMPLE → T1-LOCAL ✅ |
| "explore directory" | → INTEGRATION → T3 ❌ | → ls = SIMPLE → T1-LOCAL ✅ |
| T3 usage | Catch-all default ❌ | EPIC only ✅ |

### v3.0 Routing Rules

```
STRICT ROUTING DECISION ENGINE (3 steps, always in order):

  Step 1 — COMPLEXITY CHECK (runs FIRST, before task-type):
    SIMPLE?  → T1-LOCAL. STOP. No further analysis.
    Not simple? → continue to Step 2.

  Step 2 — ROUTING MATRIX:
    SIMPLE   + ANY type   → T1-LOCAL  (all task types, no exceptions)
    MODERATE + ANY type   → T1-CLOUD
    COMPLEX  + analytics/arch/security → T2-PRO
    COMPLEX  + debug/codegen/other     → T2-FLASH
    EPIC     + ANY type   → T3

  Step 3 — ROUTING PROTOCOL:
    [3-A] Complexity check → [3-B] Task-type detect → [3-C] Tier assign
    [3-D] Health verify   → [3-E] Execute + quality score

FALLBACK CHAIN: T1-LOCAL → T1-CLOUD → T2-FLASH → T3 (quality gate 0.75)
ANTI-PATTERN:   "When in doubt" → classify DOWN (SIMPLE), never UP (EPIC)
```

### Shell/Explore Remapping (always SIMPLE → T1-LOCAL)

| User says | Real operation | Tier |
|---|---|---|
| "connect to project" | `ls + git log` | T1-LOCAL |
| "explore directory" | `ls -la` | T1-LOCAL |
| "check git history" | `git log` | T1-LOCAL |
| "what's in this file" | `cat` | T1-LOCAL |
| "inspect project" | `ls + git status` | T1-LOCAL |

### Installation

```bash
# Copy system prompt to Claude CLI config
cp prompts/system-prompt-v3.md ~/.claude/tier-routing.md

# It is injected automatically via the claude() shell function in ~/.zshrc:
# claude() {
#   "$CLAUDE_BINARY" --append-system-prompt "$(cat ~/.claude/tier-routing.md)" "$@"
# }
```

### Prompt Files

| File | Purpose |
|---|---|
| `prompts/system-prompt-v3.md` | **Active** — merged v3.0 system prompt (install to `~/.claude/tier-routing.md`) |
| `prompts/specs/strict-routing-v3-spec.md` | Strict enforcement spec (v3.0 source) |
| `prompts/specs/base-routing-prompt-v2.md` | Base routing prompt (v2.0 source) |
