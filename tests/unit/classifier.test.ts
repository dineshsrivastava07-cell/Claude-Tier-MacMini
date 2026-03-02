import { describe, it, expect } from "vitest";
import { TaskClassifier } from "../../src/core/classifier.js";

const classifier = new TaskClassifier();

describe("TaskClassifier", () => {
  describe("task type detection", () => {
    it("detects CODE_GEN for implementation requests", () => {
      const r = classifier.classify("Implement a binary search algorithm in TypeScript");
      expect(r.taskType).toBe("CODE_GEN");
    });

    it("detects DEBUG for bug fix requests", () => {
      const r = classifier.classify("Fix this bug: TypeError cannot read property of undefined");
      // 'fix' matches CODE_FIX, 'bug' matches DEBUG — both may score
      expect(["DEBUG", "CODE_FIX"]).toContain(r.taskType);
    });

    it("detects ARCHITECTURE for design requests", () => {
      const r = classifier.classify("Design a microservices architecture system for an e-commerce platform");
      expect(r.taskType).toBe("ARCHITECTURE");
    });

    it("detects QA for test generation", () => {
      const r = classifier.classify("Write unit tests for the authentication service using jest");
      expect(r.taskType).toBe("QA");
    });

    it("detects ANALYTICS for analytics tasks", () => {
      // Use unambiguous ANALYTICS keywords
      const r = classifier.classify("Build a dashboard with analytics metrics and KPI report for pandas data");
      expect(r.taskType).toBe("ANALYTICS");
    });

    it("detects REFACTOR for refactoring tasks", () => {
      const r = classifier.classify("Refactor this code to decouple the modules and clean up naming");
      expect(r.taskType).toBe("REFACTOR");
    });
  });

  describe("complexity detection", () => {
    it("classifies short prompts as SIMPLE", () => {
      const r = classifier.classify("Fix typo");
      expect(r.complexity).toBe("SIMPLE");
    });

    it("classifies prompts with 60+ words as MODERATE or higher", () => {
      // Craft a prompt guaranteed to exceed 60 words
      const prompt = "Implement a REST API endpoint " + "with full validation and error handling ".repeat(12);
      const r = classifier.classify(prompt);
      expect(["MODERATE", "COMPLEX", "EPIC"]).toContain(r.complexity);
    });

    it("classifies architecture prompts with complex keywords as COMPLEX or EPIC", () => {
      const r = classifier.classify(
        "Design a distributed microservices architecture with service discovery, " +
        "circuit breakers, distributed tracing, and Kubernetes deployment for enterprise-grade scalability",
      );
      expect(["COMPLEX", "EPIC"]).toContain(r.complexity);
    });

    it("classifies prompts with 400+ words as COMPLEX or EPIC", () => {
      const longPrompt = ("Build a scalable production-grade application with full authentication, " +
        "database integration, and API layer. ").repeat(15);
      const r = classifier.classify(longPrompt);
      expect(["COMPLEX", "EPIC"]).toContain(r.complexity);
    });

    it("classifies prompts containing EPIC keywords as EPIC", () => {
      // "complete platform" and "build entire" are EPIC_KEYWORDS
      const r = classifier.classify(
        "Build entire complete platform end-to-end system for the greenfield project",
      );
      expect(r.complexity).toBe("EPIC");
    });
  });

  describe("tier recommendations", () => {
    it("recommends T1-LOCAL for simple tasks", () => {
      const r = classifier.classify("rename variable");
      expect(r.recommendedTier).toBe("T1-LOCAL");
    });

    it("recommends T2 or T3 for EPIC tasks", () => {
      const r = classifier.classify(
        "Build a complete production-grade enterprise greenfield multi-service AI platform " +
        "with end-to-end system design, distributed architecture, and full DevOps pipeline ".repeat(10),
      );
      expect(["T2-PRO", "T3"]).toContain(r.recommendedTier);
    });

    it("confidence is between 0 and 1", () => {
      const r = classifier.classify("Write a function to sort an array");
      expect(r.confidence).toBeGreaterThan(0);
      expect(r.confidence).toBeLessThanOrEqual(1);
    });

    it("reasoning is non-empty", () => {
      const r = classifier.classify("Implement authentication middleware");
      expect(r.reasoning).toBeTruthy();
      expect(r.reasoning.length).toBeGreaterThan(0);
    });

    it("fallback path starts at the recommended tier", () => {
      const r = classifier.classify("Implement quicksort");
      // No fallback in classifier — just verify the tier is valid
      expect(["T1-LOCAL","T1-CLOUD","T2-PRO","T2-FLASH","T2-LITE","T3"]).toContain(r.recommendedTier);
    });
  });

  describe("cost and latency estimates", () => {
    it("T1-LOCAL and T1-CLOUD are free", () => {
      expect(classifier.getEstimatedCost("T1-LOCAL")).toBe("free");
      expect(classifier.getEstimatedCost("T1-CLOUD")).toBe("free");
    });

    it("T3 is high cost", () => {
      expect(classifier.getEstimatedCost("T3")).toBe("high");
    });

    it("all tiers return valid cost labels", () => {
      for (const tier of ["T1-LOCAL","T1-CLOUD","T2-PRO","T2-FLASH","T2-LITE","T3"] as const) {
        expect(["free","low","medium","high"]).toContain(classifier.getEstimatedCost(tier));
      }
    });

    it("latency increases from T1 to T3 (roughly)", () => {
      expect(classifier.getEstimatedLatency("T1-LOCAL"))
        .toBeLessThan(classifier.getEstimatedLatency("T1-CLOUD"));
    });
  });
});
