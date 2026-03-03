# Architecture — Claude-Tier-MacMini 4-Tier AI Routing

**Version:** v4.1 | **Platform:** Mac Mini (Apple Silicon, macOS) | **Updated:** 2026-03-04

---

## Design Philosophy

> **"Always attempt the cheapest, fastest, local-first option. Escalate only on proven need."**

The system is built on four principles:

1. **Local-first** — Ollama (free, private, fast) is always attempted before cloud
2. **Quality-gated** — every tier output is scored (0.0–1.0); escalate only if below 0.75
3. **Fraud-proof** — Claude cannot self-generate content for SIMPLE/MODERATE tasks and call it T1 (v4.0 patch)
4. **Honest routing** — every response header must show the actual tier that produced the content, with a real API call made

---

## Component Map

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     CLAUDE-TIER-MACMINI SYSTEM                              │
│                                                                              │
│  ┌─────────────────────────────────┐    ┌──────────────────────────────┐   │
│  │   PATH A — Claude CLI           │    │   PATH B — Claude Desktop    │   │
│  │   Soft Enforcement              │    │   Hard Gate                  │   │
│  │   (system prompt based)         │    │   (MCP execution gate)       │   │
│  │                                 │    │                              │   │
│  │  tier-router-mcp                │    │  tier-enforcer-mcp           │   │
│  │  TypeScript · Node 20+          │    │  Python · fastmcp 3.1.0     │   │
│  │  18 tools · 3 resources         │    │  7 tools                     │   │
│  │  43/43 unit tests passing       │    │  T3 physically blocked       │   │
│  └─────────────────────────────────┘    └──────────────────────────────┘   │
│                    │                                   │                     │
│                    └─────────────┬─────────────────────┘                    │
│                                  ▼                                           │
│         ┌────────────────────────────────────────────────┐                  │
│         │           TIER EXECUTION LAYER                  │                  │
│         │                                                  │                  │
│         │  T1-LOCAL: qwen2.5-coder:7b @ localhost:11434  │                  │
│         │  T1-CLOUD: qwen3-coder:480b @ localhost:11434  │                  │
│         │  T2-PRO:   gemini-2.5-pro   @ Google API       │                  │
│         │  T2-FLASH: gemini-2.5-flash @ Google API       │                  │
│         │  T3:       claude-sonnet-4-6 (self — EPIC only)│                  │
│         └────────────────────────────────────────────────┘                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Tier Architecture

| Tier | Model | Endpoint | Complexity | Task Examples |
|------|-------|----------|-----------|---------------|
| **T1-LOCAL** | `qwen2.5-coder:7b` | `localhost:11434/api/chat` | SIMPLE | Single file edit, shell commands, config change, rename, format, unit test for one function |
| **T1-CLOUD** | `qwen3-coder:480b` | `localhost:11434/api/chat` | MODERATE | 2–10 file changes, API integration, feature-sized refactor, multi-function work |
| **T2-PRO** | `gemini-2.5-pro` | Google Generative AI | COMPLEX | Architecture design, security audit, ML/statistics, long-context analysis (50+ files) |
| **T2-FLASH** | `gemini-2.5-flash` | Google Generative AI | COMPLEX | Debug iterations, fast code review, quick analysis cycles |
| **T3** | `claude-sonnet-4-6` | Anthropic (self) | EPIC | Greenfield apps, multi-service platforms, 10+ files from scratch, system architecture |

> Both T1-LOCAL and T1-CLOUD run on the same Ollama instance at localhost:11434 — different model names serve different complexity tiers.

---

## Routing Decision Engine (3 Steps, Always in Order)

```
┌─ STEP 1: COMPLEXITY CLASSIFICATION ────────────────────────────────────────┐
│                                                                              │
│  Runs FIRST — before task type analysis                                     │
│                                                                              │
│  SIMPLE?   Single file, <20 lines, shell cmd, config, one function          │
│    → T1-LOCAL. STOP. No further analysis needed.                             │
│                                                                              │
│  MODERATE? 2–10 files, feature-sized, multi-function, API integration       │
│    → T1-CLOUD. Proceed to Step 2 only to confirm task type.                 │
│                                                                              │
│  COMPLEX?  50+ files, security audit, ML, algorithm design                  │
│    → T2. Check task type for PRO vs FLASH.                                  │
│                                                                              │
│  EPIC?     Greenfield, 10+ files from scratch, platform design              │
│    → T3.                                                                     │
└──────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─ STEP 2: ROUTING MATRIX ────────────────────────────────────────────────────┐
│                                                                              │
│  SIMPLE   + ANY task type              → T1-LOCAL  (no exceptions)          │
│  MODERATE + CODE_GEN/FIX/REFACTOR      → T1-CLOUD                           │
│  MODERATE + INTEGRATION/DEBUG/QA       → T1-CLOUD                           │
│  MODERATE + ARCHITECTURE/ANALYTICS     → T2-PRO                             │
│  COMPLEX  + ANALYTICS/ARCH/SECURITY    → T2-PRO                             │
│  COMPLEX  + DEBUG/CODEGEN/OTHER        → T2-FLASH                           │
│  EPIC     + ANY type                   → T3                                  │
└──────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─ STEP 3: EXECUTION PROTOCOL ────────────────────────────────────────────────┐
│                                                                              │
│  [A] Use Bash (read-only) to gather context — allowed always                 │
│  [B] Build prompt for assigned tier                                          │
│  [C] Make ACTUAL API call to assigned tier:                                  │
│        T1: POST localhost:11434/api/chat (curl or Python urllib)             │
│        T2: GOOGLE_GENAI_USE_GCA=true gemini --model gemini-2.5-... "..."    │
│        T3: Claude responds directly (EPIC only)                              │
│  [D] Score output quality (0.0–1.0)                                         │
│  [E] ≥ 0.75 → apply output via Write/Edit/Bash                              │
│       < 0.75 → escalate ONE step → repeat from [C]                          │
│  [F] Report in routing header with honest "API Call Made" field             │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## End-to-End Data Flow

### Path A — Claude CLI

```
User Request
    │
    ▼
zshrc claude() function
    │  claude-raw --append-system-prompt "$(cat ~/.claude/tier-routing.md)" "$@"
    ▼
Claude CLI Session starts
    │  tier-routing.md loaded as system prompt (v4.0 rules active)
    │  tier-router-mcp MCP server auto-connected (18 tools available)
    ▼
Classify Complexity [STEP 1]
    │
    ├─ SIMPLE  ──────────────────────────────────────────────────────────────┐
    │                                                                         │
    │  Bash: cat file.txt (context gathering — allowed)                      │
    │  Bash: curl -s localhost:11434/api/chat \                              │
    │         -d '{"model":"qwen2.5-coder:7b",...}'                          │
    │  ← qwen2.5-coder:7b output received                                    │
    │  Score: ≥ 0.75 → Write/Edit to apply output                           │
    │          < 0.75 → escalate to T1-CLOUD                                 │
    │                                                                         │
    ├─ MODERATE ─────────────────────────────────────────────────────────────┤
    │                                                                         │
    │  Read files, gather multi-file context                                 │
    │  Bash: curl -s localhost:11434/api/chat \                              │
    │         -d '{"model":"qwen3-coder:480b",...}'                          │
    │  ← qwen3-coder:480b output received                                    │
    │  Score: ≥ 0.75 → apply | < 0.75 → escalate to T2-FLASH               │
    │                                                                         │
    ├─ COMPLEX ──────────────────────────────────────────────────────────────┤
    │                                                                         │
    │  Call Gemini: GOOGLE_GENAI_USE_GCA=true gemini --model gemini-2.5-... │
    │  ← Gemini output received                                              │
    │  Score: ≥ 0.75 → apply | < 0.75 → escalate to T3                     │
    │                                                                         │
    └─ EPIC ─────────────────────────────────────────────────────────────────┤
                                                                              │
       Claude generates directly (this is T3 — legitimate)                   │
       Apply via Write/Edit/Bash                                              │
                                                                              │
       ◄────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
         Output applied to codebase/response
         Routing header written (honest API Call Made field)
```

### Path B — Claude Desktop (via tier-enforcer-mcp)

```
Claude Desktop user prompt
    │
    ▼
tier-enforcer-mcp receives request
    │
    ▼
[1] tier_classify(prompt, context)
    │  Returns: complexity, next_tool, confidence
    │
    ├─ SIMPLE   → [2a] t1_local_execute(prompt, context)
    │                   Calls: POST localhost:11434/api/chat (qwen2.5-coder:7b)
    │                   Returns: output, quality, passed_gate
    │
    ├─ MODERATE → [2b] t1_cloud_execute(prompt, context)
    │                   Calls: POST localhost:11434/api/chat (qwen3-coder:480b)
    │                   Returns: output, quality, passed_gate
    │
    ├─ COMPLEX  → [2c] t2_gemini_execute(prompt, context)
    │                   Calls: gemini CLI (Google account auth)
    │                   Returns: output, quality, passed_gate
    │
    └─ EPIC     → [2d] t3_epic_gate(prompt, justification)
                        ├─ Non-EPIC? → status=BLOCKED, correct_tool=t1/t2
                        └─ EPIC?     → status=APPROVED → Claude generates

[3] If result.passed_gate=false → call result.escalate_to (one step up)

[4] Apply output using Edit/Write/Bash (APPLY only — never self-generate)

[5] tier_audit_log(tier, model, quality, task)  ← ALWAYS LAST
    Writes to: ~/.tier-enforcer/routing.log
```

---

## Full Routing Matrix

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
| **ANY (catch-all)** | **T1-LOCAL** | **T1-CLOUD** | **T2-FLASH** | **T3** |

> **Catch-all rule:** If task type is unclassified/unmapped, complexity alone determines tier. SIMPLE always → T1-LOCAL. This was the v3.0 bug (unmapped → T3) and is now patched.

---

## Native Tool Permission Map

| Tool | SIMPLE | MODERATE | COMPLEX | EPIC | Notes |
|------|--------|----------|---------|------|-------|
| `Bash` (read-only: ls, cat, git, grep) | ✅ | ✅ | ✅ | ✅ | Gather context always allowed |
| `Read` file | ✅ | ✅ | ✅ | ✅ | Build prompt context for T1/T2 |
| `Bash` (write/exec) | Apply only | Apply only | Apply only | ✅ | Apply T1/T2 output |
| `Write` file | Apply only | Apply only | Apply only | ✅ | Apply T1/T2/T3 output |
| `Edit` file | Apply only | Apply only | Apply only | ✅ | Apply T1/T2/T3 output |
| **Generate content** | ❌ T1-LOCAL | ❌ T1-CLOUD | ❌ T2 | ✅ T3 | Must call Ollama/Gemini API |

**Plain English Rule:**
> "If I use Read/Edit/Write to create content for a SIMPLE or MODERATE task without first making an Ollama API call and using THAT output — that is routing fraud. It is banned."

---

## Quality Gate & Fallback Chain

```
T1-LOCAL output
    │
    ├─ quality ≥ 0.75 → ✅ Apply output — DONE
    │
    └─ quality < 0.75 → Escalate ONE step
           │
           ▼
        T1-CLOUD call
           │
           ├─ quality ≥ 0.75 → ✅ Apply — DONE
           │
           └─ quality < 0.75 → Escalate ONE step
                  │
                  ▼
               T2-FLASH call
                  │
                  ├─ quality ≥ 0.75 → ✅ Apply — DONE
                  │
                  └─ quality < 0.75 → Escalate ONE step
                         │
                         ▼
                      T3 (Claude) — FINAL fallback
                         └─ Apply — DONE (no further fallback)

Offline handling:
  T1-LOCAL offline → NOTIFY USER → try T1-CLOUD
  T1-CLOUD offline → NOTIFY USER → try T2-FLASH
  NEVER silently skip to T3 without notifying user
```

---

## Routing Fraud Detection

### The Problem (Identified in v4.0)

Claude CLI has native tools: Read, Edit, Write, Bash. These are T3 capabilities. Before v4.0, Claude would:
1. Use `Read` to read a file (context)
2. Use its own intelligence to generate the fix
3. Use `Write` to apply it
4. Claim in the header: "T1-CLOUD generated the fix"

This is **routing fraud** — T3 work disguised as T1.

### Self-Audit Checklist (Before Every Action)

```
□ Am I about to use Read/Edit/Write to generate content for a SIMPLE task?
  → STOP. That is routing fraud. Call T1-LOCAL instead.

□ Am I about to use Read/Edit/Write to generate content for a MODERATE task?
  → STOP. That is routing fraud. Call T1-CLOUD instead.

□ Is my routing header claiming T1/T2 but I haven't made an API call?
  → STOP. Make the actual API call first.

□ Am I doing T3 work and calling it T1-CLOUD in the header?
  → STOP. This is the exact identified bug from v4.0.

□ Would a reviewer watching my tool calls see actual curl/Ollama calls?
  → If not, and task is SIMPLE/MODERATE, I am committing routing fraud.

□ Is T3 (Claude) generating file content for non-EPIC tasks?
  → Only permitted if T1 AND T2 are both offline/failed AND user is notified.
```

### Fraud vs Correct — Example

```
TASK: Edit entitlements.plist to add microphone permission (4 lines)

❌ FRAUDULENT (before v4.0):
   Tool calls made: Read → (Claude generates internally) → Write
   Header claims: "T1-CLOUD applied the fix"
   Reality: T3 did everything. Zero Ollama calls.

✅ CORRECT (after v4.0):
   Tool call 1: Bash → cat entitlements.plist  (context gathering — OK)
   Tool call 2: Bash → curl localhost:11434/api/chat
                        model: qwen2.5-coder:7b
                        prompt: "Add microphone entitlement to this plist: [content]"
   Receive: qwen2.5-coder:7b output
   Score: 0.87 → PASS
   Tool call 3: Write → apply qwen output to file
   Header: "API Call Made: YES → localhost:11434 ✅  qwen2.5-coder:7b"
```

---

## Sub-Task Routing

A single user request may contain multiple distinct actions. Each sub-task is independently classified and routed.

**Example — "Fix the microphone permissions in my Electron app":**

| Sub-task | Operation | Complexity | Tier |
|---------|-----------|-----------|------|
| 1 | Read entitlements.plist for context | Read-only | Bash tool (allowed) |
| 2 | Edit entitlements.plist (+3 lines) | SIMPLE | T1-LOCAL |
| 3 | Edit electron-builder.yml (+2 lines) | SIMPLE | T1-LOCAL |
| 4 | Fix getUserMedia across 4 files | MODERATE | T1-CLOUD |
| 5 | Run tccutil reset Microphone | Shell command | Bash tool (allowed) |

Each sub-task gets its own routing header entry:
```
│ Sub-task 2: Edit plist → SIMPLE → T1-LOCAL → API Called ✅         │
│ Sub-task 4: getUserMedia fix → MODERATE → T1-CLOUD → API Called ✅  │
```

---

## Routing Header Format (v4.1)

Every response opens with a planning header and closes with an execution result:

### Planning Header (before API call)
```
┌─ TIER ROUTING DECISION ─────────────────────────────────────────┐
│ Task            : [exact description]                           │
│ Real Operation  : [stripped-down what this actually requires]   │
│ Complexity      : SIMPLE | MODERATE | COMPLEX | EPIC            │
│ Assigned Tier   : T1-LOCAL | T1-CLOUD | T2-PRO | T2-FLASH | T3 │
│ Model           : [exact model ID]                              │
│ API Call Made   : IN PROGRESS → [endpoint]/api/chat            │
│ Routing Reason  : [one sentence]                                │
│ Fallback Path   : [assigned tier] → [...] → T3                 │
└─────────────────────────────────────────────────────────────────┘
```

### Result Header (after API call)
```
┌─ EXECUTION RESULT ──────────────────────────────────────────────┐
│ API Call Made   : YES → [endpoint] ✅  [N] tokens out          │
│ Content Source  : [tier + model that generated the output]      │
│ Quality Score   : [0.0–1.0]  [PASS ≥0.75 | ESCALATE <0.75]    │
│ Fallback Used   : NO | YES → [reason] → escalated to [tier]    │
│ Next Steps      : [numbered]                                    │
└─────────────────────────────────────────────────────────────────┘
```

**v4.1 Header Precision Rules:**
- `API Call Made` says `IN PROGRESS` before the call, `YES` after it completes — never `YES` before the call
- Endpoint and model must match: T1-LOCAL = `localhost:11434` + `qwen2.5-coder:7b`; T1-CLOUD = same host + `qwen3-coder:480b`
- `Fallback Path` starts from the **assigned tier**, not always from T1-LOCAL

---

## Anti-Patterns Reference

| ID | Pattern | Root Cause | Fix |
|----|---------|-----------|-----|
| B-01 | SIMPLE + unmapped task type → T3 | Task type drove routing instead of complexity | Complexity first — SIMPLE always T1-LOCAL |
| B-02 | T3 edits config claiming T3 is correct | Config edit = SIMPLE, T3 not justified | SIMPLE config → T1-LOCAL Ollama call |
| B-03 | T3 reads file, generates 4 lines, writes file | Native Read/Write used as T3 generator | Read=OK; generate=must call Ollama |
| B-04 | Header says T1, zero Ollama calls made | Header written without actually calling T1 | `API Call Made: YES` requires actual curl/API call |
| B-05 | T1-CLOUD credited; only one of many sub-tasks routed | Sub-tasks not individually routed | Each sub-task = independent tier assignment |
| B-06 | Unmapped task type → T3 as safe catch-all | No default row for unmapped types | Complexity default: SIMPLE→T1, MODERATE→T1-CLOUD |
| B-07 | "When in doubt" → escalate UP to T3 | Conservative escalation mindset | "When in doubt" → classify DOWN to T1-LOCAL |
| B-08 | T1-LOCAL offline → silently use T3 | No offline notification | Notify user → advance ONE step in fallback chain |
| B-09 | Routing header written after T3 completes work | Decision made after work done | Classify FIRST → assign tier → call tier → header |
| B-10 | One request, one tier for all sub-tasks | Bulk routing | Each distinct action = independently classified |

---

## Version Evolution

| Version | Date | Key Addition | Bug Fixed |
|---------|------|-------------|-----------|
| v1.0 | 2026-02 | TypeScript MCP server (18 tools) | — |
| v2.0 | 2026-02 | Base routing prompt, skill layer | — |
| v3.0 | 2026-03-02 | Strict SIMPLE→T1-LOCAL enforcement, shell remapping | B-01, B-06: SIMPLE+unmapped→T3 |
| v4.0 | 2026-03-04 | Native Tool Fraud patch, sub-task routing, API Call Made field | B-02, B-03, B-04, B-09, B-10 |
| v4.1 | 2026-03-04 | Header Precision Rules (timing, endpoint-model match, fallback path) | B-04 (partial), B-05, B-07 |

---

## Security Model

| Layer | Mechanism | Covers |
|-------|-----------|--------|
| **System Prompt** | `~/.claude/tier-routing.md` injected via `--append-system-prompt` | Instructs Claude to follow routing rules; soft enforcement |
| **MCP Server (soft)** | `tier-router-mcp` — 18 tools with routing logic | Claude CLI — tools available, routing by convention |
| **MCP Server (hard)** | `tier-enforcer-mcp` — `t3_epic_gate` physically blocks | Claude Desktop — T3 cannot be used without explicit EPIC approval |
| **Audit Log** | `~/.tier-enforcer/routing.log` | Every routing decision logged with tier, model, quality, timestamp |
| **Quality Gate** | Threshold 0.75 per tier | Prevents low-quality output from propagating |
| **No API Keys in Repo** | `.env.example` only; credentials via env vars | Secrets never committed |
| **Ollama Local-only** | T1 models run on-device (localhost) | No data leaves the machine for T1 tasks |

---

*Architecture document for Claude-Tier-MacMini · v4.1 · Mac Mini Apple Silicon · 2026-03-04*
