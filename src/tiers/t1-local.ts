import { BaseTier }              from "./base-tier.js";
import type { TierName, TierOptions } from "../types.js";
import { TierError }             from "../types.js";

interface OllamaMessage { role: "system"|"user"|"assistant"; content: string; }

export class T1LocalTier extends BaseTier {
  readonly modelId  = "qwen2.5-coder:7b";
  readonly tierName: TierName = "T1-LOCAL";

  private readonly baseUrl: string;
  private readonly timeout: number;

  constructor() {
    super();
    this.baseUrl = process.env.OLLAMA_LOCAL_HOST ?? "http://localhost:11434";
    this.timeout = Number(process.env.T1_LOCAL_TIMEOUT_MS ?? 90_000);
  }

  async isHealthy(): Promise<boolean> {
    try {
      const resp = await fetch(`${this.baseUrl}/api/tags`, {
        signal: AbortSignal.timeout(3_000),
      });
      if (!resp.ok) return false;
      const data = (await resp.json()) as { models?: Array<{ name: string }> };
      return (data.models ?? []).some(m => m.name.includes("qwen2.5-coder"));
    } catch { return false; }
  }

  async execute(prompt: string, context?: string, opts?: TierOptions): Promise<string> {
    const messages: OllamaMessage[] = [
      { role: "system", content: this._codeSystemPrompt(context) },
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
          num_ctx:     opts?.maxContext  ?? 32768,
          top_p:       0.9,
          seed:        opts?.seed ?? 42,
        },
      }),
    });

    if (!resp.ok) throw new TierError("T1-LOCAL", resp.status, await resp.text());
    const data = (await resp.json()) as { message?: { content?: string } };
    const content = data.message?.content ?? "";
    if (!content.trim()) throw new TierError("T1-LOCAL", 0, "Empty response");
    return content;
  }

  private _codeSystemPrompt(context?: string): string {
    const base = `You are qwen2.5-coder:7b — a precise, fast code generation model.
Output ONLY working, production-ready code. No unnecessary explanations.
Use: type safety, error handling, async/await, clean naming.`;
    return context ? `${base}\n\nCONTEXT:\n${context}` : base;
  }
}
