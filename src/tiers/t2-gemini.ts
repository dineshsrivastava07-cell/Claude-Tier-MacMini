import { execFile }               from "node:child_process";
import { promisify }              from "node:util";
import { BaseTier }               from "./base-tier.js";
import type { TierName, TierOptions } from "../types.js";
import { TierError }              from "../types.js";

const execFileAsync = promisify(execFile);

type GeminiSubModel = "gemini-2.5-pro" | "gemini-2.5-flash" | "gemini-2.5-flash-lite";

/** T2 — Gemini via google-generativeai SDK (API key) OR gemini CLI (account auth). */
export class T2GeminiTier extends BaseTier {
  readonly tierName: TierName = "T2-PRO";
  readonly modelId: string;

  private readonly timeout: number;
  private readonly useApiKey: boolean;
  private sdkClients: Map<GeminiSubModel, unknown> = new Map();

  constructor(modelId: string = "gemini-2.5-pro") {
    super();
    this.modelId   = modelId;
    this.timeout   = Number(process.env.T2_TIMEOUT_MS ?? 60_000);
    this.useApiKey = !!(process.env.GEMINI_API_KEY);

    // If API key is present, initialise SDK clients
    if (this.useApiKey) {
      this._initSdk();
    }
  }

  private _initSdk(): void {
    try {
      // Dynamic import to avoid crash when package missing
      import("@google/generative-ai").then(({ GoogleGenerativeAI }) => {
        const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);
        const models: GeminiSubModel[] = ["gemini-2.5-pro","gemini-2.5-flash","gemini-2.5-flash-lite"];
        for (const m of models) {
          this.sdkClients.set(m, genAI.getGenerativeModel({ model: m }));
        }
      }).catch(() => { /* SDK not installed — fall through to CLI */ });
    } catch { /* ignore */ }
  }

  async isHealthy(): Promise<boolean> {
    if (this.useApiKey) return true;
    // CLI auth check
    try {
      const { stdout } = await execFileAsync("which", ["gemini"], { timeout: 3000 });
      return stdout.trim().length > 0;
    } catch { return false; }
  }

  async execute(
    prompt: string,
    context?: string,
    opts?: TierOptions & { geminiModel?: GeminiSubModel },
  ): Promise<string> {
    const model: GeminiSubModel = opts?.geminiModel ?? "gemini-2.5-pro";
    const fullPrompt = context ? `CONTEXT:\n${context}\n\nTASK:\n${prompt}` : prompt;

    // SDK path (when GEMINI_API_KEY set)
    if (this.useApiKey && this.sdkClients.has(model)) {
      return this._runSdk(model, fullPrompt, opts);
    }

    // CLI path (account auth — GOOGLE_GENAI_USE_GCA=true)
    return this._runCli(model, fullPrompt);
  }

  private async _runSdk(model: GeminiSubModel, prompt: string, opts?: TierOptions): Promise<string> {
    const client = this.sdkClients.get(model) as {
      generateContent(req: unknown): Promise<{ response: { text(): string } }>;
    };
    const result = await client.generateContent({
      contents: [{ role: "user", parts: [{ text: prompt }] }],
      generationConfig: {
        temperature:     opts?.temperature ?? 0.2,
        maxOutputTokens: opts?.maxTokens   ?? 8192,
        topP: 0.9,
      },
    });
    return result.response.text();
  }

  private async _runCli(model: GeminiSubModel, prompt: string): Promise<string> {
    const env = { ...process.env, GOOGLE_GENAI_USE_GCA: "true" };
    try {
      const { stdout } = await execFileAsync(
        "gemini",
        ["--model", model, prompt],
        { env, timeout: this.timeout, maxBuffer: 10 * 1024 * 1024 },
      );
      if (!stdout.trim()) throw new TierError("T2-GEMINI", 0, "Empty CLI response");
      return stdout.trim();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      throw new TierError("T2-GEMINI", 0, msg);
    }
  }
}
