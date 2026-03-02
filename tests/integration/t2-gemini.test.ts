/**
 * Integration tests — require Gemini CLI or GEMINI_API_KEY
 * Run with: INTEGRATION=true npx vitest run tests/integration/t2-gemini.test.ts
 */
import { describe, it, expect, beforeAll } from "vitest";
import { T2GeminiTier } from "../../src/tiers/t2-gemini.js";

const SKIP = !process.env.INTEGRATION;

describe.skipIf(SKIP)("T2-GeminiTier [integration]", () => {
  let t2: T2GeminiTier;

  beforeAll(() => {
    t2 = new T2GeminiTier();
  });

  it("reports healthy (CLI or API key present)", async () => {
    const healthy = await t2.isHealthy();
    expect(healthy).toBe(true);
  }, 10_000);

  it("generates a response via flash model", async () => {
    const result = await t2.execute(
      "Explain the difference between async/await and Promises in TypeScript in 3 bullet points",
      undefined,
      { geminiModel: "gemini-2.5-flash" },
    );
    expect(result).toBeTruthy();
    expect(result.length).toBeGreaterThan(100);
  }, 60_000);

  it("generates a deep reasoning response via pro model", async () => {
    const result = await t2.execute(
      "Analyse the trade-offs between event sourcing and CRUD for a high-throughput retail system",
      undefined,
      { geminiModel: "gemini-2.5-pro" },
    );
    expect(result).toBeTruthy();
    expect(result.length).toBeGreaterThan(200);
  }, 120_000);
});
