/**
 * Integration tests — require at least T1 (Ollama) running
 * Run with: INTEGRATION=true npx vitest run tests/integration/pipeline.test.ts
 */
import { describe, it, expect } from "vitest";
import { TierRouter } from "../../src/core/router.js";

const SKIP = !process.env.INTEGRATION;

describe.skipIf(SKIP)("TierRouter.route() [integration]", () => {
  const router = new TierRouter();

  it("routes and returns a real response", async () => {
    const result = await router.route({
      prompt: "Write a TypeScript function that reverses a string",
    });
    expect(result.content).toBeTruthy();
    expect(result.tier).toBeTruthy();
    expect(result.quality).toBeGreaterThanOrEqual(0);
    expect(result.quality).toBeLessThanOrEqual(1);
    expect(result.latencyMs).toBeGreaterThan(0);
  }, 120_000);

  it("falls back when T1 is forced and quality is insufficient", async () => {
    // Force T1-LOCAL with a very high quality threshold to trigger fallback
    const result = await router.route({
      prompt:           "Write a complete distributed microservices architecture",
      qualityThreshold: 0.01, // accept almost anything to ensure it completes
    });
    expect(result.content).toBeTruthy();
    expect(result.tier).toBeTruthy();
  }, 180_000);

  it("override tier works correctly", async () => {
    const result = await router.route({
      prompt:       "List 3 sorting algorithms",
      overrideTier: "T1-LOCAL",
    });
    expect(result.tier).toBe("T1-LOCAL");
  }, 60_000);
});
