# Skill Installation Guide

## Install `/tier-routing` as a Claude CLI Slash Command

```bash
# 1. Create directories
mkdir -p ~/.claude/commands/tier-routing/references

# 2. Copy main skill
cp skill/tier-routing.md ~/.claude/commands/tier-routing.md

# 3. Copy reference files
cp skill/references/*.md ~/.claude/commands/tier-routing/references/

# 4. Verify (in a new terminal)
claude "/tier-routing"
```

The skill becomes available as `/tier-routing` in every Claude CLI session globally.

## What the skill provides

- Mandatory routing header on every dev response
- Full tier decision table + complexity keywords
- Inline code patterns for T1/T2/T3
- Pipeline patterns (debug chain, code review, fullstack build, QA, analytics)
- Ollama health check commands
- Quality scoring reference (0.75 threshold)

## Reference files (auto-loaded on demand)

| File | Content |
|---|---|
| `t1-ollama.md` | Ollama client patterns, options, health checks |
| `t2-gemini.md` | Gemini SDK + CLI, model selection guide |
| `t3-claude.md` | Claude SDK + CLI, orchestration, streaming |
| `routing-engine.md` | Full TypeScript source of classifier/scorer/router |
| `pipelines.md` | 5 pipeline implementations |
| `mcp-integration.md` | 18 MCP tools, 3 resources, config snippets |
| `retail-analytics.md` | ClickHouse SQL, FY engine, RIECT KPIs |
| `litellm-config.md` | LiteLLM proxy config (OpenAI-compatible endpoint) |
