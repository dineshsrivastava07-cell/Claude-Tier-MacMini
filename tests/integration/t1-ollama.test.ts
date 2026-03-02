/**
 * Integration tests — require Ollama running with qwen2.5-coder:7b and qwen3-coder:480b-cloud
 * Run with: INTEGRATION=true npx vitest run tests/integration/t1-ollama.test.ts
 */
import { describe, it, expect, beforeAll } from "vitest";
import { T1LocalTier } from "../../src/tiers/t1-local.js";
import { T1CloudTier } from "../../src/tiers/t1-cloud.js";

const SKIP = !process.env.INTEGRATION;

describe.skipIf(SKIP)("T1-LOCAL (Ollama qwen2.5-coder:7b) [integration]", () => {
  let t1: T1LocalTier;

  beforeAll(() => {
    t1 = new T1LocalTier();
  });

  it("reports healthy when Ollama is running with qwen2.5-coder", async () => {
    const healthy = await t1.isHealthy();
    expect(healthy).toBe(true);
  }, 10_000);

  it("generates a valid code response", async () => {
    const result = await t1.execute("Write a TypeScript function that returns the sum of an array of numbers");
    expect(result).toBeTruthy();
    expect(result.length).toBeGreaterThan(50);
    expect(result).toMatch(/function|const|=>/);
  }, 30_000);

  it("handles context correctly", async () => {
    const result = await t1.execute(
      "Add error handling to the existing function",
      "// TypeScript, Node.js project\nfunction sum(arr: number[]) { return arr.reduce((a,b) => a+b, 0); }",
    );
    expect(result).toBeTruthy();
  }, 30_000);
});

describe.skipIf(SKIP)("T1-CLOUD (Ollama qwen3-coder:480b-cloud) [integration]", () => {
  let t1c: T1CloudTier;

  beforeAll(() => {
    t1c = new T1CloudTier();
  });

  it("reports healthy when Ollama has qwen3-coder:480b-cloud", async () => {
    const healthy = await t1c.isHealthy();
    expect(healthy).toBe(true);
  }, 10_000);

  it("generates a high-quality code response", async () => {
    const result = await t1c.execute(
      "Implement a production-ready Redis cache wrapper in TypeScript with TTL, invalidation, and error handling",
    );
    expect(result).toBeTruthy();
    expect(result.length).toBeGreaterThan(200);
  }, 120_000);
});
