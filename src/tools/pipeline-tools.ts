import { McpServer }  from "@modelcontextprotocol/sdk/server/mcp.js";
import { z }          from "zod";
import { TierRouter } from "../core/router.js";
import {
  CodeReviewInput,
  DebugChainInput,
  FullstackBuildInput,
  QAPipelineInput,
} from "../types.js";

export function registerPipelineTools(server: McpServer, router: TierRouter): void {

  // ── pipeline_code_review ───────────────────────────────────────────────────
  server.tool(
    "pipeline_code_review",
    "Multi-tier code review pipeline: T1-LOCAL quick linting → T2-FLASH semantic review → " +
    "T3 deep architectural review (only if issues found). Returns consolidated report.",
    CodeReviewInput.shape,
    async (args: z.infer<typeof CodeReviewInput>) => {
      const sections: string[] = [];

      // Stage 1 — T1 quick check
      sections.push("## Stage 1: Quick Lint (T1-LOCAL)");
      try {
        const t1 = await router.route({
          prompt: `Quick lint check — identify obvious bugs, syntax issues, and style violations only.\n\nCode (${args.language}):\n\`\`\`\n${args.code}\n\`\`\``,
          overrideTier: "T1-LOCAL",
          options: { temperature: 0.0 },
        });
        sections.push(t1.content, `*Tier: ${t1.tier} | Quality: ${t1.quality.toFixed(2)} | ${t1.latencyMs}ms*`);
      } catch (e) {
        sections.push(`⚠ T1-LOCAL unavailable: ${e instanceof Error ? e.message : e}`);
      }

      // Stage 2 — T2 semantic review
      sections.push("\n## Stage 2: Semantic Review (T2-FLASH)");
      try {
        const focus = args.focus.join(", ");
        const t2 = await router.route({
          prompt: `Perform a ${focus} code review of this ${args.language} code. Be specific about line numbers and provide actionable fixes.\n\nCode:\n\`\`\`\n${args.code}\n\`\`\``,
          overrideTier: "T2-FLASH",
          options: { temperature: 0.1 },
        });
        sections.push(t2.content, `*Tier: ${t2.tier} | Quality: ${t2.quality.toFixed(2)} | ${t2.latencyMs}ms*`);

        // Stage 3 — T3 only when significant security/architecture issues found
        const hasIssues = /critical|high|severe|vulnerability|injection|exploit/i.test(t2.content);
        if (hasIssues && args.focus.includes("architecture")) {
          sections.push("\n## Stage 3: Architectural Deep-Dive (T3)");
          try {
            const t3 = await router.route({
              prompt: `Architecture review and hardening. Focus on: design patterns, SOLID violations, long-term maintainability, and production readiness.\n\nCode:\n\`\`\`\n${args.code}\n\`\`\`\n\nPrevious findings:\n${t2.content}`,
              overrideTier: "T3",
              options: { temperature: 0.2 },
            });
            sections.push(t3.content, `*Tier: ${t3.tier} | Quality: ${t3.quality.toFixed(2)} | ${t3.latencyMs}ms*`);
          } catch (e) {
            sections.push(`⚠ T3 unavailable: ${e instanceof Error ? e.message : e}`);
          }
        }
      } catch (e) {
        sections.push(`⚠ T2-FLASH unavailable: ${e instanceof Error ? e.message : e}`);
      }

      return { content: [{ type: "text" as const, text: `# Code Review Report\n\n${sections.join("\n\n")}` }] };
    },
  );

  // ── pipeline_debug_chain ───────────────────────────────────────────────────
  server.tool(
    "pipeline_debug_chain",
    "Progressive debug pipeline: T1 quick hypothesis → T2 deep analysis → T3 root-cause if needed. " +
    "Escalates automatically when lower tiers can't resolve the issue.",
    DebugChainInput.shape,
    async (args: z.infer<typeof DebugChainInput>) => {
      const context = [
        `Language: ${args.language}`,
        `Error: ${args.error_message}`,
        `Code/stack trace:\n${args.code_context}`,
      ].join("\n");

      const sections: string[] = [];

      // T1 — fast hypothesis
      sections.push("## Tier 1 — Quick Diagnosis (T1-LOCAL)");
      let t1Quality = 0;
      try {
        const t1 = await router.route({
          prompt: `Quick debug: What is the most likely cause of this bug and what is the fix?`,
          context,
          overrideTier: "T1-LOCAL",
          options: { temperature: 0.1 },
        });
        sections.push(t1.content, `*${t1.tier} | quality=${t1.quality.toFixed(2)} | ${t1.latencyMs}ms*`);
        t1Quality = t1.quality;
      } catch (e) {
        sections.push(`⚠ T1 unavailable: ${e instanceof Error ? e.message : e}`);
      }

      // T2 — deeper analysis if T1 low quality
      if (t1Quality < 0.80) {
        sections.push("\n## Tier 2 — Deep Analysis (T2-FLASH)");
        let t2Quality = 0;
        try {
          const t2 = await router.route({
            prompt: `Thorough debug analysis. Identify root cause, explain why it fails, and provide a complete corrected implementation.`,
            context,
            overrideTier: "T2-FLASH",
            options: { temperature: 0.1 },
          });
          sections.push(t2.content, `*${t2.tier} | quality=${t2.quality.toFixed(2)} | ${t2.latencyMs}ms*`);
          t2Quality = t2.quality;
        } catch (e) {
          sections.push(`⚠ T2 unavailable: ${e instanceof Error ? e.message : e}`);
        }

        // T3 — root cause if still unresolved
        if (t2Quality < 0.80) {
          sections.push("\n## Tier 3 — Root Cause Analysis (T3)");
          try {
            const t3 = await router.route({
              prompt: `Root cause analysis. Trace through execution, identify all contributing factors, and provide a production-grade fix with tests.`,
              context,
              overrideTier: "T3",
              options: { temperature: 0.2 },
            });
            sections.push(t3.content, `*${t3.tier} | quality=${t3.quality.toFixed(2)} | ${t3.latencyMs}ms*`);
          } catch (e) {
            sections.push(`⚠ T3 unavailable: ${e instanceof Error ? e.message : e}`);
          }
        }
      }

      return { content: [{ type: "text" as const, text: `# Debug Chain Report\n\n${sections.join("\n\n")}` }] };
    },
  );

  // ── pipeline_build_fullstack ───────────────────────────────────────────────
  server.tool(
    "pipeline_build_fullstack",
    "Multi-tier full-stack build pipeline: T1-CLOUD scaffolds structure → T2-PRO implements " +
    "business logic → T3 finalises production-grade code. Builds complete features end-to-end.",
    FullstackBuildInput.shape,
    async (args: z.infer<typeof FullstackBuildInput>) => {
      const sections: string[] = [];
      const techStack = [
        args.stack.language,
        args.stack.framework,
        args.stack.database,
        args.stack.auth,
      ].filter(Boolean).join(", ");

      // Phase 1 — T1-CLOUD: scaffold
      sections.push("## Phase 1: Scaffold & Structure (T1-CLOUD)");
      let scaffold = "";
      try {
        const t1 = await router.route({
          prompt: `Create a complete project scaffold for the following requirements.\nTech stack: ${techStack}\nRequirements: ${args.requirements}\nInclude: folder structure, file list, boilerplate code, and dependency list.`,
          overrideTier: "T1-CLOUD",
          options: { temperature: 0.15 },
        });
        scaffold = t1.content;
        sections.push(t1.content, `*${t1.tier} | quality=${t1.quality.toFixed(2)} | ${t1.latencyMs}ms*`);
      } catch (e) {
        sections.push(`⚠ T1-CLOUD unavailable: ${e instanceof Error ? e.message : e}`);
      }

      // Phase 2 — T2-PRO: business logic
      sections.push("\n## Phase 2: Business Logic (T2-PRO)");
      let logic = "";
      try {
        const t2 = await router.route({
          prompt: `Implement full business logic.\nTech stack: ${techStack}\nRequirements: ${args.requirements}\n\nBuild upon this scaffold:\n${scaffold}`,
          overrideTier: "T2-PRO",
          options: { temperature: 0.2, maxTokens: 8192 },
        });
        logic = t2.content;
        sections.push(t2.content, `*${t2.tier} | quality=${t2.quality.toFixed(2)} | ${t2.latencyMs}ms*`);
      } catch (e) {
        sections.push(`⚠ T2-PRO unavailable: ${e instanceof Error ? e.message : e}`);
      }

      // Phase 3 — T3: production hardening
      sections.push("\n## Phase 3: Production Hardening (T3)");
      try {
        const t3 = await router.route({
          prompt: `Review and harden for production. Apply: security-by-design, comprehensive error handling, observability, SOLID principles, and complete tests.\n\nRequirements: ${args.requirements}\n\nCurrent implementation:\n${logic || scaffold}`,
          overrideTier: "T3",
          options: { temperature: 0.2, maxTokens: 16384 },
        });
        sections.push(t3.content, `*${t3.tier} | quality=${t3.quality.toFixed(2)} | ${t3.latencyMs}ms*`);
      } catch (e) {
        sections.push(`⚠ T3 unavailable: ${e instanceof Error ? e.message : e}`);
      }

      return {
        content: [{ type: "text" as const, text: `# Full-Stack Build\n\n${sections.join("\n\n")}` }],
      };
    },
  );

  // ── pipeline_qa_full ───────────────────────────────────────────────────────
  server.tool(
    "pipeline_qa_full",
    "Full QA pipeline: T1 unit tests → T2 integration tests → T3 E2E tests. " +
    "Returns a complete test suite targeting the specified coverage.",
    QAPipelineInput.shape,
    async (args: z.infer<typeof QAPipelineInput>) => {
      const sections: string[] = [];
      const framework = args.language === "python" ? "pytest" : "vitest";

      // Unit tests — T1-CLOUD
      sections.push("## Unit Tests (T1-CLOUD)");
      try {
        const t1 = await router.route({
          prompt: `Write comprehensive unit tests using ${framework} targeting ${args.coverage_target}% coverage.\nCover: happy path, edge cases, and error conditions.\n\nCode (${args.language}):\n\`\`\`\n${args.code}\n\`\`\``,
          overrideTier: "T1-CLOUD",
          options: { temperature: 0.1 },
        });
        sections.push(t1.content, `*${t1.tier} | quality=${t1.quality.toFixed(2)} | ${t1.latencyMs}ms*`);
      } catch (e) {
        sections.push(`⚠ T1-CLOUD unavailable: ${e instanceof Error ? e.message : e}`);
      }

      // Integration tests — T2-FLASH
      sections.push("\n## Integration Tests (T2-FLASH)");
      try {
        const t2 = await router.route({
          prompt: `Write integration tests using ${framework}. Focus on: API contracts, service interactions, and async flows.\n\nCode (${args.language}):\n\`\`\`\n${args.code}\n\`\`\``,
          overrideTier: "T2-FLASH",
          options: { temperature: 0.1 },
        });
        sections.push(t2.content, `*${t2.tier} | quality=${t2.quality.toFixed(2)} | ${t2.latencyMs}ms*`);
      } catch (e) {
        sections.push(`⚠ T2-FLASH unavailable: ${e instanceof Error ? e.message : e}`);
      }

      // E2E tests — T3 (only for large coverage targets)
      if (args.coverage_target >= 90) {
        sections.push("\n## E2E Tests (T3)");
        try {
          const t3 = await router.route({
            prompt: `Write E2E tests and performance benchmarks using ${framework}.\nCover: full user flows and SLA validation.\n\nCode (${args.language}):\n\`\`\`\n${args.code}\n\`\`\``,
            overrideTier: "T3",
            options: { temperature: 0.2 },
          });
          sections.push(t3.content, `*${t3.tier} | quality=${t3.quality.toFixed(2)} | ${t3.latencyMs}ms*`);
        } catch (e) {
          sections.push(`⚠ T3 unavailable: ${e instanceof Error ? e.message : e}`);
        }
      }

      return {
        content: [{ type: "text" as const, text: `# QA Test Suite\n\n${sections.join("\n\n")}` }],
      };
    },
  );
}
