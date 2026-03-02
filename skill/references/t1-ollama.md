# T1 Ollama Reference — qwen2.5-coder:7b & qwen3-coder:480b

## Models

| Tier | Model | Context | Timeout | Best For |
|---|---|---|---|---|
| T1-LOCAL | qwen2.5-coder:7b | 32 768 | 90s | Completions, snippets, quick fixes |
| T1-CLOUD | qwen3-coder:480b-cloud | 131 072 | 300s | Multi-file, architecture, production code |

## Health Check (always run before T1 calls)

```bash
# T1-LOCAL
curl -s http://localhost:11434/api/tags | python3 -c \
  "import json,sys; models=[m['name'] for m in json.load(sys.stdin).get('models',[])]; \
   print('✅ T1-LOCAL OK' if any('qwen2.5-coder' in m for m in models) else '❌ Run: ollama pull qwen2.5-coder:7b')"

# T1-CLOUD
curl -s "${OLLAMA_CLOUD_HOST:-http://localhost:11434}/api/tags" | python3 -c \
  "import json,sys; models=[m['name'] for m in json.load(sys.stdin).get('models',[])]; \
   print('✅ T1-CLOUD OK' if any('qwen3-coder' in m or '480b' in m for m in models) else '❌ T1-CLOUD OFFLINE')"
```

## /api/chat  (streaming disabled for MCP)

```typescript
interface OllamaRequest {
  model:    string;
  messages: { role: "system"|"user"|"assistant"; content: string }[];
  stream:   false;
  options:  OllamaOptions;
}

interface OllamaOptions {
  temperature: number;   // 0.0–1.0  (default: 0.1 for code)
  num_ctx:     number;   // context window tokens
  top_p?:      number;   // 0.9
  seed?:       number;   // reproducibility
  num_predict?:number;   // max output tokens (-1 = unlimited)
  stop?:       string[]; // stop sequences
}

interface OllamaResponse {
  model:    string;
  message:  { role: "assistant"; content: string };
  done:     boolean;
  eval_count?:    number;  // tokens generated
  prompt_eval_count?: number;  // tokens in prompt
  total_duration?:    number;  // nanoseconds
}
```

## Full TypeScript Client (T1-LOCAL)

```typescript
const OLLAMA_LOCAL = process.env.OLLAMA_LOCAL_HOST ?? "http://localhost:11434";

async function t1LocalGenerate(
  prompt: string,
  context?: string,
  opts: { temperature?: number; maxTokens?: number; seed?: number } = {}
): Promise<string> {
  const messages = [];
  if (context) messages.push({ role: "system" as const, content: context });
  messages.push({ role: "user" as const, content: prompt });

  const resp = await fetch(`${OLLAMA_LOCAL}/api/chat`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    signal:  AbortSignal.timeout(90_000),
    body: JSON.stringify({
      model:    "qwen2.5-coder:7b",
      messages,
      stream:   false,
      options: {
        temperature: opts.temperature ?? 0.1,
        num_ctx:     32768,
        top_p:       0.9,
        seed:        opts.seed,
        num_predict: opts.maxTokens ?? -1,
      },
    }),
  });

  if (!resp.ok) throw new Error(`T1-LOCAL HTTP ${resp.status}: ${await resp.text()}`);
  const data = await resp.json() as OllamaResponse;
  return data.message.content;
}
```

## Full TypeScript Client (T1-CLOUD)

```typescript
const OLLAMA_CLOUD = process.env.OLLAMA_CLOUD_HOST
  ?? process.env.OLLAMA_LOCAL_HOST
  ?? "http://localhost:11434";

async function t1CloudGenerate(
  prompt: string,
  context?: string,
  opts: { temperature?: number } = {}
): Promise<string> {
  const messages = [];
  const systemPrompt = `You are qwen3-coder:480b — a senior software architect and expert developer.
Produce complete, production-ready, well-structured code following SOLID principles.
Include: error handling, async/await, type safety, inline comments where logic is complex.
${context ? `\nCONTEXT:\n${context}` : ""}`;

  messages.push({ role: "system" as const, content: systemPrompt });
  messages.push({ role: "user" as const, content: prompt });

  const resp = await fetch(`${OLLAMA_CLOUD}/api/chat`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    signal:  AbortSignal.timeout(300_000),
    body: JSON.stringify({
      model:    "qwen3-coder:480b-cloud",
      messages,
      stream:   false,
      options: {
        temperature: opts.temperature ?? 0.1,
        num_ctx:     131072,
        top_p:       0.9,
      },
    }),
  });

  if (!resp.ok) throw new Error(`T1-CLOUD HTTP ${resp.status}: ${await resp.text()}`);
  const data = await resp.json() as OllamaResponse;
  return data.message.content;
}
```

## Ollama CLI Commands

```bash
# Install models
ollama pull qwen2.5-coder:7b
ollama pull qwen3-coder:480b-cloud

# Check running
ollama list
ollama ps

# Start server (if not running via launchd)
ollama serve

# Test directly
ollama run qwen2.5-coder:7b "Write a quicksort in TypeScript"

# Inspect model metadata
ollama show qwen2.5-coder:7b

# Remove model
ollama rm qwen2.5-coder:7b
```

## Performance Tuning

| Option | T1-LOCAL | T1-CLOUD | Notes |
|---|---|---|---|
| `temperature` | 0.0–0.15 | 0.1–0.2 | Lower = more deterministic code |
| `num_ctx` | 32768 | 131072 | Match to prompt size |
| `top_p` | 0.9 | 0.9 | Nucleus sampling |
| `seed` | 42 | — | Set for reproducible tests |
| `num_predict` | -1 | -1 | -1 = unlimited |

## Error Handling

```typescript
const RETRIABLE = [503, 429];

async function withRetry<T>(fn: () => Promise<T>, maxRetries = 2): Promise<T> {
  for (let i = 0; i <= maxRetries; i++) {
    try {
      return await fn();
    } catch (err) {
      const isLast = i === maxRetries;
      if (isLast) throw err;
      // Brief back-off before retry
      await new Promise(r => setTimeout(r, 1000 * (i + 1)));
    }
  }
  throw new Error("Unreachable");
}
```

## Environment Variables

```bash
OLLAMA_LOCAL_HOST=http://localhost:11434
OLLAMA_CLOUD_HOST=http://remote-server:11434   # optional
T1_LOCAL_TIMEOUT_MS=90000
T1_CLOUD_TIMEOUT_MS=300000
```
