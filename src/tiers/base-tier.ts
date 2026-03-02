import type { TierName, TierOptions } from "../types.js";

export abstract class BaseTier {
  abstract readonly modelId:  string;
  abstract readonly tierName: TierName;

  abstract isHealthy(): Promise<boolean>;
  abstract execute(prompt: string, context?: string, opts?: TierOptions): Promise<string>;

  protected buildSystemPrompt(context?: string): string {
    const base = `You are an expert software engineer. Produce complete, production-ready, working code.
Follow: type safety, error handling, async-first, clean naming, SOLID principles.
Never use placeholder comments like "# TODO" or "pass" unless asked.`;
    return context ? `${base}\n\nCONTEXT:\n${context}` : base;
  }
}
