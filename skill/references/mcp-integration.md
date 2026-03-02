# MCP Integration Reference — tier-router-mcp

## Location & Status

```bash
# Server location
~/tier-router-mcp/

# Build
cd ~/tier-router-mcp && npm run build

# Verify registration
claude mcp list
# tier-router: ✓ Connected
```

## 18 MCP Tools

### Routing Tools (4)

| Tool | Input | Purpose |
|---|---|---|
| `tier_route_task` | `prompt`, `context?`, `quality_threshold?` | Auto-route with fallback chain |
| `tier_health_check` | `tier?` (ALL/T1-LOCAL/T2/T3) | Probe tier availability |
| `tier_explain_decision` | `prompt`, `context?` | Classify without executing |
| `tier_override` | `tier`, `prompt`, `context?`, `max_tokens?` | Force specific tier |

### T1 Tools (4)

| Tool | Model | Purpose |
|---|---|---|
| `t1_local_generate` | qwen2.5-coder:7b | Fast code generation |
| `t1_local_complete` | qwen2.5-coder:7b | Code completion / fill-in-middle |
| `t1_cloud_generate` | qwen3-coder:480b | High-quality production code |
| `t1_cloud_analyze` | qwen3-coder:480b | Security / performance audit |

### T2 Tools (4)

| Tool | Model | Purpose |
|---|---|---|
| `t2_gemini_pro_reason` | gemini-2.5-pro | Deep reasoning, architecture |
| `t2_gemini_flash_generate` | gemini-2.5-flash | Fast, balanced generation |
| `t2_gemini_lite_validate` | gemini-2.5-flash-lite | Validation, linting, quick checks |
| `t2_gemini_analyze_image` | gemini-2.5-pro | Image / diagram analysis |

### T3 Tools (2)

| Tool | Model | Purpose |
|---|---|---|
| `t3_claude_architect` | claude-sonnet-4-6 | Architecture decisions, ADRs |
| `t3_claude_epic` | claude-sonnet-4-6 | Full feature implementation |

### Pipeline Tools (4)

| Tool | Chain | Purpose |
|---|---|---|
| `pipeline_code_review` | T1 → T2 → T3 | Multi-tier code review |
| `pipeline_debug_chain` | T1 → T2 → T3 | Progressive debug escalation |
| `pipeline_build_fullstack` | T1 → T2 → T3 | End-to-end feature build |
| `pipeline_qa_full` | T1 → T2 → T3 | Complete test suite generation |

## 3 MCP Resources

| URI | Content | When to read |
|---|---|---|
| `tier://config` | Tier config, models, costs, fallback chains | Start of session |
| `tier://metrics` | Per-tier success rate, avg quality, avg latency | Performance tuning |
| `tier://routing-log` | Last 50 routing decisions with timestamps | Debugging routing issues |

## Claude CLI Registration

```bash
# Register (already done)
claude mcp add tier-router node ~/tier-router-mcp/dist/index.js \
  -e OLLAMA_LOCAL_HOST=http://localhost:11434 \
  -e CLAUDE_MODEL=claude-sonnet-4-6 \
  -e QUALITY_THRESHOLD=0.75

# Remove
claude mcp remove tier-router

# Re-register with API keys
claude mcp add tier-router node ~/tier-router-mcp/dist/index.js \
  -e OLLAMA_LOCAL_HOST=http://localhost:11434 \
  -e GEMINI_API_KEY=your-key \
  -e ANTHROPIC_API_KEY=your-key \
  -e CLAUDE_MODEL=claude-sonnet-4-6
```

## Claude Desktop Config

```json
{
  "mcpServers": {
    "tier-router": {
      "command": "node",
      "args": ["/Users/dsr-ai-lab/tier-router-mcp/dist/index.js"],
      "env": {
        "OLLAMA_LOCAL_HOST": "http://localhost:11434",
        "CLAUDE_MODEL": "claude-sonnet-4-6",
        "QUALITY_THRESHOLD": "0.75"
      }
    }
  }
}
```

Location: `~/tier-router-mcp/claude_desktop_config.json`
Copy to: `~/Library/Application Support/Claude/claude_desktop_config.json`

## Tool Input Schemas

### tier_route_task
```typescript
{
  prompt:            string;          // Task to execute
  context?:          string;          // Existing code or project context
  task_type?:        "AUTO" | TaskType;  // Default: AUTO
  override_tier?:    TierName;        // Force a specific tier
  quality_threshold?: number;         // 0–1, default 0.75
  temperature?:      number;          // 0–2, default 0.1
}
```

### tier_health_check
```typescript
{
  tier?: "ALL" | "T1-LOCAL" | "T1-CLOUD" | "T2" | "T3";  // default: ALL
}
```

### pipeline_code_review
```typescript
{
  code:     string;
  language: string;                  // default: "typescript"
  focus:    ("security"|"performance"|"correctness"|"style"|"architecture")[];
}
```

### pipeline_debug_chain
```typescript
{
  error_message: string;
  code_context:  string;
  language:      string;             // default: "typescript"
}
```

## Development

```bash
cd ~/tier-router-mcp

# Rebuild after changes
npm run build

# Unit tests (no network)
npx vitest run tests/unit/

# Integration tests (requires Ollama + Gemini)
INTEGRATION=true npx vitest run tests/integration/

# Eval
cat eval.xml   # 10 QA test pairs
```

## Project Structure

```
~/tier-router-mcp/
├── src/
│   ├── types.ts          — Zod schemas + TS interfaces
│   ├── core/             — classifier, quality-scorer, metrics, fallback-chain, router
│   ├── tiers/            — T1Local, T1Cloud, T2Gemini, T3Claude (+ BaseTier)
│   ├── tools/            — 18 MCP tool registrations
│   ├── resources/        — tier://config, tier://metrics, tier://routing-log
│   ├── server.ts         — McpServer wiring
│   └── index.ts          — stdio entry point
├── tests/unit/           — 43 tests, no network
├── tests/integration/    — live tier tests
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── eval.xml
└── README.md
```
