import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";

const TIER_CONFIG = {
  version: "1.0.0",
  tiers: {
    "T1-LOCAL": {
      name:        "T1-LOCAL",
      model:       "qwen2.5-coder:7b",
      provider:    "Ollama (local)",
      endpoint:    process.env.OLLAMA_LOCAL_HOST ?? "http://localhost:11434",
      costPerToken: 0,
      avgLatencyMs: 2000,
      maxContextTokens: 32768,
      bestFor:     ["code completion", "quick fixes", "short snippets", "syntax checks"],
      timeout:     Number(process.env.T1_LOCAL_TIMEOUT_MS ?? 90_000),
    },
    "T1-CLOUD": {
      name:        "T1-CLOUD",
      model:       "qwen3-coder:480b-cloud",
      provider:    "Ollama (cloud/local large)",
      endpoint:    process.env.OLLAMA_CLOUD_HOST ?? process.env.OLLAMA_LOCAL_HOST ?? "http://localhost:11434",
      costPerToken: 0,
      avgLatencyMs: 15000,
      maxContextTokens: 131072,
      bestFor:     ["complex algorithms", "architecture", "refactoring", "production code"],
      timeout:     Number(process.env.T1_CLOUD_TIMEOUT_MS ?? 300_000),
    },
    "T2-PRO": {
      name:        "T2-PRO",
      model:       "gemini-2.5-pro",
      provider:    "Google Gemini",
      auth:        process.env.GEMINI_API_KEY ? "API Key" : "Account Auth (GCA)",
      costPerToken: 0.0000035,
      avgLatencyMs: 8000,
      maxContextTokens: 2000000,
      bestFor:     ["deep reasoning", "research", "multi-step analysis", "architecture decisions"],
    },
    "T2-FLASH": {
      name:        "T2-FLASH",
      model:       "gemini-2.5-flash",
      provider:    "Google Gemini",
      auth:        process.env.GEMINI_API_KEY ? "API Key" : "Account Auth (GCA)",
      costPerToken: 0.00000035,
      avgLatencyMs: 3000,
      maxContextTokens: 1000000,
      bestFor:     ["general coding", "explanations", "medium complexity", "balanced speed/quality"],
    },
    "T2-LITE": {
      name:        "T2-LITE",
      model:       "gemini-2.5-flash-lite",
      provider:    "Google Gemini",
      auth:        process.env.GEMINI_API_KEY ? "API Key" : "Account Auth (GCA)",
      costPerToken: 0.0000001,
      avgLatencyMs: 1500,
      maxContextTokens: 500000,
      bestFor:     ["validation", "linting", "quick yes/no", "lightweight checks"],
    },
    "T3": {
      name:        "T3",
      model:       process.env.CLAUDE_MODEL ?? "claude-sonnet-4-6",
      provider:    "Anthropic Claude",
      auth:        process.env.ANTHROPIC_API_KEY ? "API Key" : "Claude CLI (account auth)",
      costPerToken: 0.000003,
      avgLatencyMs: 12000,
      maxContextTokens: 200000,
      bestFor:     ["epic tasks", "architecture", "production hardening", "complex reasoning"],
    },
  },
  fallbackChains: {
    "T1-LOCAL": ["T1-LOCAL", "T1-CLOUD", "T2-FLASH", "T3"],
    "T1-CLOUD": ["T1-CLOUD", "T2-FLASH", "T3"],
    "T2-PRO":   ["T2-PRO", "T2-FLASH", "T3"],
    "T2-FLASH": ["T2-FLASH", "T2-PRO", "T3"],
    "T2-LITE":  ["T2-LITE", "T2-FLASH", "T1-CLOUD"],
    "T3":       ["T3"],
  },
  qualityThreshold: Number(process.env.QUALITY_THRESHOLD ?? 0.75),
  environment: {
    hasGeminiApiKey:    !!(process.env.GEMINI_API_KEY),
    hasAnthropicApiKey: !!(process.env.ANTHROPIC_API_KEY),
    ollamaLocalHost:    process.env.OLLAMA_LOCAL_HOST ?? "http://localhost:11434",
    ollamaCloudHost:    process.env.OLLAMA_CLOUD_HOST ?? "(not set)",
    claudeModel:        process.env.CLAUDE_MODEL ?? "claude-sonnet-4-6",
  },
};

export function registerTierConfigResource(server: McpServer): void {
  server.resource(
    "tier-config",
    "tier://config",
    { mimeType: "application/json" },
    async () => ({
      contents: [{
        uri:      "tier://config",
        mimeType: "application/json",
        text:     JSON.stringify(TIER_CONFIG, null, 2),
      }],
    }),
  );
}
