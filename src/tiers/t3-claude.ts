import { execFile }               from "node:child_process";
import { promisify }              from "node:util";
import { BaseTier }               from "./base-tier.js";
import type { TierName, TierOptions } from "../types.js";
import { TierError }              from "../types.js";

const execFileAsync = promisify(execFile);

/** T3 — Claude via Anthropic SDK (API key) OR claude CLI (account auth). */
export class T3ClaudeTier extends BaseTier {
  readonly modelId:  string;
  readonly tierName: TierName = "T3";

  private readonly timeout: number;
  private readonly useApiKey: boolean;
  private sdkClient: unknown = null;

  constructor() {
    super();
    this.modelId   = process.env.CLAUDE_MODEL ?? "claude-sonnet-4-6";
    this.timeout   = Number(process.env.T3_TIMEOUT_MS ?? 120_000);
    this.useApiKey = !!(process.env.ANTHROPIC_API_KEY);

    if (this.useApiKey) {
      this._initSdk();
    }
  }

  private _initSdk(): void {
    import("@anthropic-ai/sdk").then(({ default: Anthropic }) => {
      this.sdkClient = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY! });
    }).catch(() => { /* SDK not installed — fall through to CLI */ });
  }

  async isHealthy(): Promise<boolean> {
    if (this.useApiKey) return true;
    try {
      const { stdout } = await execFileAsync("which", ["claude"], { timeout: 3000 });
      return stdout.trim().length > 0;
    } catch { return false; }
  }

  async execute(prompt: string, context?: string, opts?: TierOptions): Promise<string> {
    const systemPrompt = `You are an elite software architect and senior engineer.
Produce complete, production-grade, fully-working implementations.
Apply: SOLID principles, security-by-design, async-first, comprehensive error handling.
${context ? `\nPROJECT CONTEXT:\n${context}` : ""}`;

    // SDK path
    if (this.useApiKey && this.sdkClient) {
      return this._runSdk(systemPrompt, prompt, opts);
    }

    // CLI path (account auth)
    return this._runCli(systemPrompt, prompt);
  }

  private async _runSdk(system: string, prompt: string, opts?: TierOptions): Promise<string> {
    const client = this.sdkClient as {
      messages: {
        create(req: unknown): Promise<{ content: Array<{ type: string; text?: string }> }>;
      };
    };
    const msg = await client.messages.create({
      model:      this.modelId,
      max_tokens: opts?.maxTokens ?? 8192,
      system,
      messages:   [{ role: "user", content: prompt }],
    });
    const text = (msg.content.find(b => b.type === "text") as { text?: string })?.text ?? "";
    if (!text.trim()) throw new TierError("T3-CLAUDE", 0, "Empty SDK response");
    return text;
  }

  private async _runCli(system: string, prompt: string): Promise<string> {
    const fullPrompt = `${system}\n\n---\n\n${prompt}`;
    try {
      const { stdout } = await execFileAsync(
        "claude",
        ["--model", this.modelId, "--print", "--output-format", "text"],
        {
          timeout:   this.timeout,
          maxBuffer: 20 * 1024 * 1024,
          input:     fullPrompt,
        } as Parameters<typeof execFileAsync>[2] & { input?: string },
      );
      const out = String(stdout);
      if (!out.trim()) throw new TierError("T3-CLAUDE", 0, "Empty CLI response");
      return out.trim();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      throw new TierError("T3-CLAUDE", 0, msg);
    }
  }
}
