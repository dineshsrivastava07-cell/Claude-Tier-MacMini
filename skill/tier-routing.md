---
name: tier-routing-ai-orchestration
description: >
  Master skill for the 4-Tier AI Routing Architecture integrating Ollama (Qwen), 
  Gemini, and Claude inside Claude CLI. Use this skill ALWAYS when any of these 
  apply: building or configuring a tier-routed AI system, routing tasks between 
  qwen2.5-coder:7b (T1-LOCAL), qwen3-coder:480b (T1-CLOUD), Gemini 2.5 (T2), 
  or Claude Opus (T3); implementing Ollama model integrations; developing 
  multi-model agentic pipelines; building analytical or statistical AI apps; 
  doing end-to-end fullstack AI development with intelligent model routing; 
  debugging or optimizing tier fallback chains; building MCP servers for tier 
  orchestration; any task requiring multi-chain coding from architecture to QA; 
  LiteLLM proxy configs, tier health checks, model routing logic, Qwen Ollama 
  setup, Gemini API integration, Claude subagent orchestration; or patterns like 
  pipeline_code_review, pipeline_debug_chain, or pipeline_build_fullstack. 
  Enforces strict tier discipline: never skip T1, always attempt local-first, 
  escalate by quality threshold 0.75.
---

# Tier Routing AI Orchestration Skill

Production-grade multi-model routing system. Intelligently dispatches every task
to the optimal AI tier — maximizing quality, minimizing cost and latency.
Enforces local-first execution with automatic quality-gated escalation.

---

## Tier Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  T1-LOCAL │ qwen2.5-coder:7b  │ Ollama  localhost:11434          │
│  T1-CLOUD │ qwen3-coder:480b  │ Ollama  $OLLAMA_CLOUD_HOST       │
│  T2-PRO   │ gemini-2.5-pro    │ Google  Generative AI API        │
│  T2-FLASH │ gemini-2.5-flash  │ Google  (fast iteration)         │
│  T2-LITE  │ gemini-2.5-f-lite │ Google  (validation/checks)      │
│  T3       │ claude-opus-4-5   │ Anthropic API  (self-tier)       │
└──────────────────────────────────────────────────────────────────┘

FALLBACK CHAIN (enforce always, quality gate = 0.75):
  T1-LOCAL → T1-CLOUD → T2-FLASH → T3
```

---

## Routing Decision Table

| Complexity | Task Category            | Tier       | Model                  |
|------------|--------------------------|------------|------------------------|
| SIMPLE     | Codegen, fix, docstring  | T1-LOCAL   | qwen2.5-coder:7b       |
| SIMPLE     | Unit test, boilerplate   | T1-LOCAL   | qwen2.5-coder:7b       |
| SIMPLE     | Config, Dockerfile       | T1-LOCAL   | qwen2.5-coder:7b       |
| MODERATE   | Multi-file, API design   | T1-CLOUD   | qwen3-coder:480b       |
| MODERATE   | Refactor, integration    | T1-CLOUD   | qwen3-coder:480b       |
| MODERATE   | OAuth, streaming, paging | T1-CLOUD   | qwen3-coder:480b       |
| COMPLEX    | Analytics, statistics    | T2-PRO     | gemini-2.5-pro         |
| COMPLEX    | Security/perf review     | T2-PRO     | gemini-2.5-pro         |
| COMPLEX    | Debug iteration          | T2-FLASH   | gemini-2.5-flash       |
| COMPLEX    | Schema validation        | T2-LITE    | gemini-2.5-flash-lite  |
| EPIC       | Full-stack app build     | T3         | claude-opus-4-5        |
| EPIC       | Architecture, greenfield | T3         | claude-opus-4-5        |

**Complexity keywords:**
- SIMPLE   → `fix`, `add`, `docstring`, `format`, `unit test`, `config`, `rename`
- MODERATE → `integrate`, `refactor`, `feature`, `schema`, `API`, `auth`, `component`
- COMPLEX  → `analytics`, `algorithm`, `optimize`, `security`, `statistical`, `ML`
- EPIC     → `application`, `platform`, `end-to-end`, `production`, `microservices`

---

## Non-Negotiable Behavior Rules

1. **NEVER skip T1** — always attempt Qwen first for SIMPLE/MODERATE tasks
2. **Announce tier** — show routing header before every output
3. **Health-check** — verify Ollama alive before any T1 call
4. **Quality gate 0.75** — escalate if output scores below threshold
5. **Actionable errors** — every error block contains `Suggestion:` with fix
6. **No hardcoded secrets** — all keys via `process.env` / env vars only
7. **Structured + text** — return both `content` (text) and `structuredContent`
8. **Local-first cost** — T3 only when T1+T2 genuinely insufficient

---

## Mandatory Response Format

Every tier-routed response MUST open with:
```
┌─ TIER ROUTING ──────────────────────────────────────────────────┐
│ Task Type    : [CODE_GEN|ARCHITECTURE|DEBUG|ANALYTICS|FULLSTACK] │
│ Complexity   : [SIMPLE|MODERATE|COMPLEX|EPIC]                   │
│ Tier Assigned: [T1-LOCAL|T1-CLOUD|T2-PRO|T2-FLASH|T2-LITE|T3] │
│ Model        : [exact model name]                               │
│ Fallback Path: [e.g. T1-LOCAL → T1-CLOUD → T2-FLASH → T3]     │
│ Confidence   : [0.0–1.0]                                        │
└─────────────────────────────────────────────────────────────────┘
```

And close with:
```
┌─ EXECUTION SUMMARY ─────────────────────────────────────────────┐
│ Tiers Used   : [list]                                           │
│ Files Created: [N — names]                                      │
│ Next Steps   : [numbered]                                       │
│ Ollama Setup : [pull command if T1 not installed]              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Tier Code Patterns

### T1-LOCAL (qwen2.5-coder:7b)
```typescript
const r = await fetch('http://localhost:11434/api/chat', {
  method: 'POST',
  body: JSON.stringify({
    model: 'qwen2.5-coder:7b', stream: false,
    messages: [{ role: 'user', content: prompt }],
    options: { temperature: 0.1, num_ctx: 32768, seed: 42 }
  })
});
return (await r.json()).message.content;
```

### T1-CLOUD (qwen3-coder:480b)
```typescript
const r = await fetch(`${process.env.OLLAMA_CLOUD_HOST}/api/chat`, {
  method: 'POST',
  body: JSON.stringify({
    model: 'qwen3-coder:480b', stream: false,
    messages: [{ role: 'user', content: prompt }],
    options: { temperature: 0.1, num_ctx: 131072 }
  })
});
return (await r.json()).message.content;
```

### T2 (Gemini 2.5)
```typescript
import { GoogleGenerativeAI } from '@google/generative-ai';
const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);
const model = genAI.getGenerativeModel({ model: 'gemini-2.5-pro' });
// also: 'gemini-2.5-flash' | 'gemini-2.5-flash-lite'
const result = await model.generateContent(prompt);
return result.response.text();
```

### T3 (Claude Opus)
```typescript
import Anthropic from '@anthropic-ai/sdk';
const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
const msg = await client.messages.create({
  model: process.env.CLAUDE_MODEL ?? 'claude-opus-4-5',
  max_tokens: 8192,
  messages: [{ role: 'user', content: prompt }]
});
return (msg.content[0] as { text: string }).text;
```

---

## Pipeline Patterns

### Debug Escalation Chain
```
T1-LOCAL  → quick fix (syntax/simple logic)     — stop if resolved
T1-CLOUD  → multi-file analysis                  — stop if resolved
T2-FLASH  → pattern recognition + alternatives  — stop if resolved
T3        → root cause + architectural redesign  — always resolves
```

### Code Review Pipeline
```
Stage 1: T1-CLOUD  → syntax, types, style
Stage 2: T2-PRO    → security, performance, architecture
Stage 3: T3        → synthesis + prioritized fix list
```

### Fullstack Build Pipeline
```
T3       → architecture + file structure + API contracts
T1-CLOUD → implement all files per T3 spec
T2-PRO   → integration + security review
T1-LOCAL → unit tests + Dockerfile + README
```

### Analytics App Pipeline
```
T1-LOCAL → data pipeline boilerplate, transforms, SQL
T1-CLOUD → ML pipeline, feature engineering, sklearn
T2-PRO   → statistical modeling, formula validation
T3       → ClickHouse schema + dashboard architecture
```

---

## Ollama Health Check (run before every T1 call)

```bash
# Check T1-LOCAL
curl -s http://localhost:11434/api/tags | grep qwen2.5 \
  && echo "✅ T1-LOCAL OK" || echo "❌ Run: ollama pull qwen2.5-coder:7b"

# Check T1-CLOUD
curl -s "$OLLAMA_CLOUD_HOST/api/tags" | grep qwen3 \
  && echo "✅ T1-CLOUD OK" || echo "❌ T1-CLOUD OFFLINE — routing to T2"
```

**If T1-LOCAL offline:** show `ollama pull qwen2.5-coder:7b` → route to T1-CLOUD
**If T1-CLOUD offline:** skip silently → route to T2-FLASH

---

## Quality Scoring

Score output before presenting. If below 0.75, escalate with prior output as context.

| Signal                               | Score Penalty |
|--------------------------------------|---------------|
| Contains `TODO` / `pass` / `...`     | -0.2 each     |
| Output < 50 chars for code task      | -0.5          |
| Malformed JSON / SyntaxError         | -0.4          |
| Incomplete function signature        | -0.3          |
| No error handling (production code)  | -0.15         |
| Missing type annotations             | -0.1          |

---

## Reference Files

| File                              | Load When                                               |
|-----------------------------------|---------------------------------------------------------|
| `references/t1-ollama.md`         | Deep T1 client: streaming, batching, options tuning    |
| `references/t2-gemini.md`         | Gemini 2.5 API: all models, config, multimodal         |
| `references/t3-claude.md`         | Claude Opus orchestration, multi-agent, system prompts |
| `references/routing-engine.md`    | Full router/classifier/quality-scorer TypeScript code  |
| `references/pipelines.md`         | Complete pipeline implementations (debug/review/build) |
| `references/mcp-integration.md`   | tier-router-mcp tools, resources, claude_desktop_config|
| `references/retail-analytics.md`  | ClickHouse, INR, SPSF, Indian retail KPI stack         |
| `references/litellm-config.md`    | LiteLLM proxy config for unified tier endpoint         |
