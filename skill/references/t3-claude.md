# T3 Claude Reference — claude-sonnet-4-6 / claude-opus-4-5

## When to Use T3

T3 is the last-resort tier. Only invoke when:
- Task is EPIC complexity (full application, greenfield, multi-service)
- T1+T2 quality scores both fell below 0.75
- Task requires architectural reasoning + production hardening simultaneously
- User explicitly requests Claude (override)

**Cost principle:** T3 only when T1+T2 genuinely insufficient.

## Models

| Model | Context | Cost | Best For |
|---|---|---|---|
| claude-sonnet-4-6 | 200K | high | Default T3 — balanced quality/cost |
| claude-opus-4-5 | 200K | very high | Reserved for true EPIC tasks |

## Auth Options

### Option A — Claude CLI (account auth, default)
```typescript
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

async function t3ClaudeCLI(systemPrompt: string, userPrompt: string): Promise<string> {
  const fullPrompt = `${systemPrompt}\n\n---\n\n${userPrompt}`;
  const { stdout } = await execFileAsync(
    "claude",
    ["--model", process.env.CLAUDE_MODEL ?? "claude-sonnet-4-6",
     "--print", "--output-format", "text"],
    { timeout: 120_000, maxBuffer: 20 * 1024 * 1024, input: fullPrompt } as never
  );
  const out = String(stdout);
  if (!out.trim()) throw new Error("Empty Claude CLI response");
  return out.trim();
}
```

### Option B — Anthropic SDK (API key)
```typescript
import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

async function t3ClaudeSDK(
  system: string,
  prompt: string,
  opts: { maxTokens?: number; temperature?: number } = {}
): Promise<string> {
  const msg = await client.messages.create({
    model:      process.env.CLAUDE_MODEL ?? "claude-sonnet-4-6",
    max_tokens: opts.maxTokens ?? 8192,
    system,
    messages:   [{ role: "user", content: prompt }],
  });
  const block = msg.content.find(b => b.type === "text") as { text?: string } | undefined;
  const text  = block?.text ?? "";
  if (!text.trim()) throw new Error("Empty SDK response");
  return text;
}
```

## System Prompt Patterns

### Architect Mode
```typescript
const ARCHITECT_SYSTEM = `You are an elite software architect with 20+ years of enterprise experience.
For every design decision:
1. State the decision clearly
2. Provide 2-3 alternatives with trade-offs
3. Justify your recommendation
4. Show concrete implementation path

Principles: SOLID, security-by-design, async-first, observability-first,
least-privilege, fail-fast, idempotency.`;
```

### EPIC Builder Mode
```typescript
const EPIC_SYSTEM = `You are an elite senior engineer building production-grade systems.
Deliver: Complete, working, fully-typed TypeScript implementation.
Include: Comprehensive error handling, input validation, retry logic,
structured logging, health checks, and unit test stubs.
Never use placeholder comments (TODO/FIXME/pass).
Always implement the full solution.`;
```

### Code Hardening Mode
```typescript
const HARDENING_SYSTEM = `You are a principal engineer performing production readiness review.
For every code block:
- Add missing error handling (try/catch, graceful degradation)
- Add input validation at system boundaries
- Add structured logging with correlation IDs
- Check for security vulnerabilities (injection, auth, SSRF)
- Add JSDoc for all public APIs
- Ensure all async operations are properly awaited`;
```

## Multi-Agent Orchestration Pattern

```typescript
// T3 as orchestrator — delegates sub-tasks to T1/T2
async function epicOrchestration(requirements: string) {
  // Step 1: T3 creates the blueprint
  const blueprint = await t3ClaudeSDK(
    ARCHITECT_SYSTEM,
    `Create a detailed technical blueprint for: ${requirements}
     Output: File list, API contracts, data models, sequence diagrams (ASCII).`
  );

  // Step 2: T1-CLOUD implements per blueprint
  const implementations = await Promise.all(
    extractFiles(blueprint).map(file =>
      t1CloudGenerate(`Implement exactly as specified:\n${file.spec}`)
    )
  );

  // Step 3: T2-PRO reviews integration
  const review = await t2GeminiSDK(
    `Security and integration review of this implementation:\n${implementations.join("\n\n")}`,
    "gemini-2.5-pro"
  );

  // Step 4: T3 finalises + hardens
  return t3ClaudeSDK(
    HARDENING_SYSTEM,
    `Harden and finalise:\n${implementations.join("\n\n")}\n\nReview findings:\n${review}`
  );
}
```

## Streaming (SDK only)

```typescript
async function t3Stream(system: string, prompt: string, onChunk: (text: string) => void): Promise<string> {
  const stream = await client.messages.stream({
    model:      process.env.CLAUDE_MODEL ?? "claude-sonnet-4-6",
    max_tokens: 8192,
    system,
    messages:   [{ role: "user", content: prompt }],
  });

  let full = "";
  for await (const chunk of stream) {
    if (chunk.type === "content_block_delta" && chunk.delta.type === "text_delta") {
      onChunk(chunk.delta.text);
      full += chunk.delta.text;
    }
  }
  return full;
}
```

## Environment Variables

```bash
ANTHROPIC_API_KEY=...              # optional — claude CLI used if unset
CLAUDE_MODEL=claude-sonnet-4-6     # default model
T3_TIMEOUT_MS=120000
```

## Token Budgeting

| Task Type | Recommended max_tokens |
|---|---|
| Code snippet | 2 048 |
| Feature implementation | 8 192 |
| Full-stack build | 16 384 |
| Architecture + code | 32 768 |

## Install

```bash
npm install @anthropic-ai/sdk
# Claude CLI (already installed if using Claude Code)
which claude
```
