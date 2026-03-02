# T2 Gemini Reference — gemini-2.5-pro / flash / flash-lite

## Models

| Tier | Model | Context | Cost | Best For |
|---|---|---|---|---|
| T2-PRO | gemini-2.5-pro | 2M tokens | medium | Deep reasoning, architecture, research |
| T2-FLASH | gemini-2.5-flash | 1M tokens | low | General coding, explanations, iteration |
| T2-LITE | gemini-2.5-flash-lite | 500K tokens | low | Validation, linting, quick checks |

## Auth Options

### Option A — Account Auth (default, no API key needed)
```bash
# Requires gemini CLI v0.29.5+
gemini --model gemini-2.5-flash "Your prompt here"
GOOGLE_GENAI_USE_GCA=true gemini --model gemini-2.5-pro "prompt"
```

### Option B — API Key Auth
```bash
export GEMINI_API_KEY=your-key-here
```

## CLI Usage (Account Auth)

```typescript
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

type GeminiModel = "gemini-2.5-pro" | "gemini-2.5-flash" | "gemini-2.5-flash-lite";

async function t2GeminiCLI(prompt: string, model: GeminiModel = "gemini-2.5-flash"): Promise<string> {
  const env = { ...process.env, GOOGLE_GENAI_USE_GCA: "true" };
  const { stdout } = await execFileAsync(
    "gemini",
    ["--model", model, prompt],
    { env, timeout: 60_000, maxBuffer: 10 * 1024 * 1024 }
  );
  if (!stdout.trim()) throw new Error("Empty Gemini CLI response");
  return stdout.trim();
}
```

## SDK Usage (API Key Auth)

```typescript
import { GoogleGenerativeAI, GenerativeModel } from "@google/generative-ai";

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);

// Model instances (create once, reuse)
const models: Record<GeminiModel, GenerativeModel> = {
  "gemini-2.5-pro":        genAI.getGenerativeModel({ model: "gemini-2.5-pro" }),
  "gemini-2.5-flash":      genAI.getGenerativeModel({ model: "gemini-2.5-flash" }),
  "gemini-2.5-flash-lite": genAI.getGenerativeModel({ model: "gemini-2.5-flash-lite" }),
};

async function t2GeminiSDK(
  prompt: string,
  model: GeminiModel = "gemini-2.5-pro",
  opts: { temperature?: number; maxOutputTokens?: number } = {}
): Promise<string> {
  const result = await models[model].generateContent({
    contents: [{ role: "user", parts: [{ text: prompt }] }],
    generationConfig: {
      temperature:     opts.temperature ?? 0.2,
      maxOutputTokens: opts.maxOutputTokens ?? 8192,
      topP:            0.9,
    },
  });
  return result.response.text();
}
```

## Model Selection Guide

```typescript
function selectGeminiModel(taskType: string, complexity: string): GeminiModel {
  // Lite: pure validation/linting
  if (["QA"].includes(taskType) && complexity === "SIMPLE") return "gemini-2.5-flash-lite";

  // Flash: general iteration
  if (["CODE_GEN","DEBUG","CODE_FIX"].includes(taskType)) return "gemini-2.5-flash";

  // Pro: deep reasoning, analytics, architecture
  return "gemini-2.5-pro";
}
```

## Prompt Construction Patterns

### Code Generation
```typescript
const codePrompt = `You are a senior ${language} engineer.
Write production-ready, fully-typed, error-handled code.

Requirements: ${requirements}
${context ? `\nExisting code:\n\`\`\`\n${context}\n\`\`\`` : ""}

Output ONLY the implementation code with inline comments for non-obvious logic.`;
```

### Analytics / Reasoning
```typescript
const analyticsPrompt = `You are an expert data analyst and statistician.
Provide precise, quantitative analysis with concrete recommendations.

Data context: ${dataContext}
Question: ${question}

Structure your response: Analysis → Findings → Recommendations → Next Steps`;
```

### Security Review
```typescript
const securityPrompt = `You are an OWASP-certified security engineer.
Perform a comprehensive security audit of the following code.

Identify: injection risks, auth flaws, insecure patterns, data exposure, SSRF/CSRF vectors.
For each finding: severity (CRITICAL/HIGH/MEDIUM/LOW), location, explanation, fix.

Code:\n\`\`\`\n${code}\n\`\`\``;
```

## Rate Limits & Quotas (Free tier / Account auth)

| Model | RPM | TPM | TPD |
|---|---|---|---|
| gemini-2.5-pro | 5 | 250K | 1M |
| gemini-2.5-flash | 15 | 1M | 1M |
| gemini-2.5-flash-lite | 30 | 1M | 1.5M |

## Error Handling

```typescript
const GEMINI_RETRY_CODES = [429, 503, 500];

async function t2WithRetry(prompt: string, model: GeminiModel): Promise<string> {
  let lastErr: Error | null = null;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      return await t2GeminiSDK(prompt, model);
    } catch (err: unknown) {
      lastErr = err instanceof Error ? err : new Error(String(err));
      const is429 = lastErr.message.includes("429");
      if (!is429) throw lastErr;
      await new Promise(r => setTimeout(r, 2000 * (attempt + 1)));
    }
  }
  throw lastErr!;
}
```

## Environment Variables

```bash
GEMINI_API_KEY=...          # optional — account auth used if unset
T2_TIMEOUT_MS=60000
GOOGLE_GENAI_USE_GCA=true   # set by T2 tier for CLI auth
```

## Install

```bash
npm install @google/generative-ai
# CLI (account auth)
npm install -g @google/generative-ai-cli  # or via brew
```
