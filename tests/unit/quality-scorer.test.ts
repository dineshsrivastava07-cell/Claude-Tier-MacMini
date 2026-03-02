import { describe, it, expect } from "vitest";
import { QualityScorer } from "../../src/core/quality-scorer.js";

const scorer = new QualityScorer();

describe("QualityScorer", () => {
  describe("basic scoring", () => {
    it("returns 0 for empty output", () => {
      expect(scorer.score("", "CODE_GEN")).toBe(0);
      expect(scorer.score("   ", "CODE_GEN")).toBe(0);
    });

    it("returns low score for refusal messages", () => {
      const score = scorer.score("I cannot help with that request.", "CODE_GEN");
      expect(score).toBeLessThanOrEqual(0.5);
    });

    it("returns low score for very short outputs", () => {
      const score = scorer.score("ok", "CODE_GEN");
      expect(score).toBeLessThan(0.6);
    });

    it("returns high score for code-containing outputs", () => {
      const code = `
Here is a TypeScript implementation:

\`\`\`typescript
function binarySearch(arr: number[], target: number): number {
  let left = 0;
  let right = arr.length - 1;
  while (left <= right) {
    const mid = Math.floor((left + right) / 2);
    if (arr[mid] === target) return mid;
    if (arr[mid] < target) left = mid + 1;
    else right = mid - 1;
  }
  return -1;
}
\`\`\`

This runs in O(log n) time.
      `;
      const score = scorer.score(code, "CODE_GEN");
      expect(score).toBeGreaterThan(0.7);
    });

    it("penalises TODO markers for code tasks", () => {
      const lazyOutput = "```\nfunction solve() {\n  // TODO: implement this\n  // TODO: add error handling\n}\n```";
      const full       = "```\nfunction solve() {\n  return 42;\n}\n```";
      // The TODO output should score lower than a complete implementation
      expect(scorer.score(lazyOutput, "CODE_GEN")).toBeLessThan(scorer.score(full, "CODE_GEN"));
    });
  });

  describe("task-type specific scoring", () => {
    it("rewards code blocks for CODE_GEN tasks", () => {
      const withCode    = "Here's the solution:\n```js\nconsole.log('hello');\n```";
      const withoutCode = "The solution involves using console.log to print hello to the screen.";
      expect(scorer.score(withCode, "CODE_GEN"))
        .toBeGreaterThan(scorer.score(withoutCode, "CODE_GEN"));
    });

    it("rewards detailed reasoning for ARCHITECTURE tasks", () => {
      const detailed = "## Architecture Decision\n\n" +
        "Using microservices because:\n1. Independent scaling\n2. Technology diversity\n3. Fault isolation\n\n" +
        "## Trade-offs\nPros: scalability, resilience\nCons: complexity, network overhead\n\n" +
        "## Implementation Plan\nPhase 1: Service decomposition\nPhase 2: API gateway\nPhase 3: Service mesh";
      expect(scorer.score(detailed, "ARCHITECTURE")).toBeGreaterThan(0.7);
    });
  });

  describe("score range", () => {
    it("always returns score between 0 and 1", () => {
      const samples = [
        "",
        "x",
        "Hello world",
        "```typescript\nconst x = 1;\n```",
        "I cannot and will not help with this.",
        "A".repeat(5000),
      ];
      for (const sample of samples) {
        const score = scorer.score(sample, "CODE_GEN");
        expect(score).toBeGreaterThanOrEqual(0);
        expect(score).toBeLessThanOrEqual(1);
      }
    });
  });
});
