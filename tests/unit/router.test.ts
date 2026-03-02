import { describe, it, expect } from "vitest";
import { TierRouter } from "../../src/core/router.js";

describe("TierRouter", () => {
  const router = new TierRouter();

  describe("explain()", () => {
    it("returns a routing decision without executing", async () => {
      const decision = await router.explain({ prompt: "Write a hello world function" });
      expect(decision.selectedTier).toBeTruthy();
      expect(decision.taskType).toBeTruthy();
      expect(decision.complexity).toBeTruthy();
      expect(decision.reasoning).toBeTruthy();
      expect(Array.isArray(decision.fallbackPath)).toBe(true);
      expect(decision.fallbackPath.length).toBeGreaterThan(0);
    });

    it("routes simple tasks to lower tiers", async () => {
      const decision = await router.explain({ prompt: "fix typo" });
      expect(["T1-LOCAL", "T1-CLOUD", "T2-FLASH"]).toContain(decision.selectedTier);
    });

    it("routes epic architecture tasks to higher tiers", async () => {
      const decision = await router.explain({
        prompt:
          "Design and implement a complete distributed AI orchestration platform " +
          "with microservices, Kubernetes, service mesh, distributed tracing, " +
          "and multi-region failover. Enterprise-grade, production-grade system ".repeat(5),
      });
      expect(["T2-PRO", "T3"]).toContain(decision.selectedTier);
    });

    it("fallback path starts with recommended tier", async () => {
      const decision = await router.explain({ prompt: "Implement quicksort in Python" });
      expect(decision.fallbackPath[0]).toBe(decision.selectedTier);
    });

    it("estimatedCost is a valid cost label", async () => {
      const decision = await router.explain({ prompt: "Write a function" });
      expect(["free","low","medium","high"]).toContain(decision.estimatedCost);
    });
  });

  describe("checkHealth()", () => {
    it("returns health status for all 6 tiers", async () => {
      const results = await router.checkHealth("ALL");
      expect(results).toHaveLength(6);
      const names = results.map(r => r.tier);
      for (const t of ["T1-LOCAL","T1-CLOUD","T2-PRO","T2-FLASH","T2-LITE","T3"]) {
        expect(names).toContain(t);
      }
    }, 15_000);

    it("returns 3 results for T2 group", async () => {
      const results = await router.checkHealth("T2");
      expect(results).toHaveLength(3);
      expect(results.every(r => r.tier.startsWith("T2"))).toBe(true);
    }, 15_000);

    it("returns 1 result for a single tier", async () => {
      const results = await router.checkHealth("T3");
      expect(results).toHaveLength(1);
      expect(results[0].tier).toBe("T3");
    }, 10_000);

    it("each result has required shape", async () => {
      const results = await router.checkHealth("ALL");
      for (const r of results) {
        expect(r).toHaveProperty("tier");
        expect(r).toHaveProperty("healthy");
        expect(r).toHaveProperty("model");
        expect(r).toHaveProperty("latencyMs");
        expect(typeof r.healthy).toBe("boolean");
      }
    }, 15_000);
  });

  describe("getTaskType()", () => {
    it("returns valid TaskType enum values", () => {
      const validTypes = ["CODE_GEN","CODE_FIX","ARCHITECTURE","ANALYTICS",
                          "REFACTOR","QA","DEBUG","INTEGRATION","FULLSTACK"];
      expect(validTypes).toContain(router.getTaskType("Write a sort function"));
      expect(validTypes).toContain(router.getTaskType("Fix this bug in my code"));
    });

    it("returns CODE_GEN for generic generation prompts", () => {
      expect(router.getTaskType("Write a sort function")).toBe("CODE_GEN");
    });

    it("returns DEBUG for bug/error prompts", () => {
      expect(router.getTaskType("Debug this error crash")).toBe("DEBUG");
    });

    it("returns QA for test prompts", () => {
      expect(router.getTaskType("Write unit tests with jest coverage")).toBe("QA");
    });
  });

  describe("metrics", () => {
    it("exposes a metrics tracker with required methods", () => {
      expect(typeof router.metrics.getSummary).toBe("function");
      expect(typeof router.metrics.getRoutingLog).toBe("function");
      expect(typeof router.metrics.getAll).toBe("function");
    });

    it("getSummary returns an object keyed by tier name", () => {
      const summary = router.metrics.getSummary();
      expect(typeof summary).toBe("object");
      for (const tier of ["T1-LOCAL","T1-CLOUD","T2-PRO","T2-FLASH","T2-LITE","T3"]) {
        expect(summary).toHaveProperty(tier);
        expect(summary[tier]).toHaveProperty("calls");
        expect(summary[tier]).toHaveProperty("successRate");
      }
    });
  });
});
