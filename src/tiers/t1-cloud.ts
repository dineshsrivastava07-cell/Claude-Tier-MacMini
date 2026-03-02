import { BaseTier }              from "./base-tier.js";
import type { TierName, TierOptions } from "../types.js";
import { TierError }             from "../types.js";

interface OllamaMessage { role: "system"|"user"|"assistant"; content: string; }

export class T1CloudTier extends BaseTier {
  readonly modelId  = "qwen3-coder:480b-cloud";
  readonly tierName: TierName = "T1-CLOUD";

  private readonly baseUrl: string;
  private readonly timeout: number;

  constructor() {
    super();
    // If OLLAMA_CLOUD_HOST not set, fall back to local Ollama (we have the 480b model locally)
    this.baseUrl = process.env.OLLAMA_CLOUD_HOST ?? process.env.OLLAMA_LOCAL_HOST ?? "http://localhost:11434";
    this.timeout = Number(process.env.T1_CLOUD_TIMEOUT_MS ?? 300_000);
  }

  async isHealthy(): Promise<boolean> {
    try {
      const resp = await fetch(`${this.baseUrl}/api/tags`, {
        signal: AbortSignal.timeout(5_000),
      });
      if (!resp.ok) return false;
      const data = (await resp.json()) as { models?: Array<{ name: string }> };
      return (data.models ?? []).some(m =>
        m.name.includes("qwen3-coder") || m.name.includes("480b"),
      );
    } catch { return false; }
  }

  async execute(prompt: string, context?: string, opts?: TierOptions): Promise<string> {
    const messages: OllamaMessage[] = [
      { role: "system", content: this._systemPrompt(context) },
      { role: "user",   content: prompt },
    ];

    const resp = await fetch(`${this.baseUrl}/api/chat`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      signal:  AbortSignal.timeout(opts?.timeoutMs ?? this.timeout),
      body: JSON.stringify({
        model:    this.modelId,
        messages,
        stream:   false,
        options: {
          temperature: opts?.temperature ?? 0.1,
          num_ctx:     opts?.maxContext  ?? 131072,
          top_p:       0.9,
        },
      }),
    });

    if (!resp.ok) throw new TierError("T1-CLOUD", resp.status, await resp.text());
    const data = (await resp.json()) as { message?: { content?: string } };
    const content = data.message?.content ?? "";
    if (!content.trim()) throw new TierError("T1-CLOUD", 0, "Empty response");
    return content;
  }

  private _systemPrompt(context?: string): string {
    const base = `You are qwen3-coder:480b — a senior software architect and expert developer.
Produce complete, production-ready, well-structured code following SOLID principles.
Include: error handling, async/await, type safety, inline comments where logic is complex.`;
    return context ? `${base}\n\nCONTEXT:\n${context}` : base;
  }
}
