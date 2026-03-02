import { McpServer }   from "@modelcontextprotocol/sdk/server/mcp.js";
import { z }           from "zod";
import { TierRouter }  from "../core/router.js";
import { T1GenerateInput } from "../types.js";

export function registerT1Tools(server: McpServer, router: TierRouter): void {

  // ── t1_local_generate ─────────────────────────────────────────────────────
  server.tool(
    "t1_local_generate",
    "Generate code or text using T1-LOCAL (qwen2.5-coder:7b via local Ollama). " +
    "Fastest and free — ideal for short code snippets, completions, and quick tasks.",
    T1GenerateInput.shape,
    async (args: z.infer<typeof T1GenerateInput>) => {
      try {
        const result = await router.route({
          prompt:       args.prompt,
          context:      args.context,
          overrideTier: "T1-LOCAL",
          options: { temperature: args.use_cloud ? undefined : 0.1 },
        });
        return { content: [{ type: "text" as const, text: result.content }] };
      } catch (err) {
        return {
          content: [{ type: "text" as const, text: `T1-LOCAL error: ${err instanceof Error ? err.message : err}` }],
          isError: true,
        };
      }
    },
  );

  // ── t1_local_complete ─────────────────────────────────────────────────────
  server.tool(
    "t1_local_complete",
    "Complete a partial code snippet using T1-LOCAL (qwen2.5-coder:7b). " +
    "Optimised for fill-in-the-middle and autocomplete scenarios.",
    {
      code:     z.string().describe("Partial code to complete"),
      language: z.string().optional().describe("Programming language"),
      context:  z.string().optional().describe("Additional context"),
    },
    async (args: { code: string; language?: string; context?: string }) => {
      const prompt = args.language
        ? `Complete the following ${args.language} code:\n\`\`\`${args.language}\n${args.code}\n\`\`\``
        : `Complete the following code:\n\`\`\`\n${args.code}\n\`\`\``;
      try {
        const result = await router.route({
          prompt,
          context:      args.context,
          overrideTier: "T1-LOCAL",
          options: { temperature: 0.1 },
        });
        return { content: [{ type: "text" as const, text: result.content }] };
      } catch (err) {
        return {
          content: [{ type: "text" as const, text: `T1-LOCAL complete error: ${err instanceof Error ? err.message : err}` }],
          isError: true,
        };
      }
    },
  );

  // ── t1_cloud_generate ─────────────────────────────────────────────────────
  server.tool(
    "t1_cloud_generate",
    "Generate code using T1-CLOUD (qwen3-coder:480b via Ollama). " +
    "High-quality large model — ideal for complex algorithms, architecture, and production code.",
    T1GenerateInput.shape,
    async (args: z.infer<typeof T1GenerateInput>) => {
      try {
        const result = await router.route({
          prompt:       args.prompt,
          context:      args.context,
          overrideTier: "T1-CLOUD",
          options: { temperature: 0.1 },
        });
        return { content: [{ type: "text" as const, text: result.content }] };
      } catch (err) {
        return {
          content: [{ type: "text" as const, text: `T1-CLOUD error: ${err instanceof Error ? err.message : err}` }],
          isError: true,
        };
      }
    },
  );

  // ── t1_cloud_analyze ──────────────────────────────────────────────────────
  server.tool(
    "t1_cloud_analyze",
    "Analyze code or a technical problem using T1-CLOUD (qwen3-coder:480b). " +
    "Deep analysis: security review, performance audit, dependency inspection.",
    {
      code:        z.string().describe("Code or content to analyze"),
      analysisType: z.enum(["security", "performance", "quality", "dependencies", "general"])
                     .optional()
                     .default("general")
                     .describe("Type of analysis to perform"),
      context:     z.string().optional().describe("Project or file context"),
    },
    async (args: { code: string; analysisType?: string; context?: string }) => {
      const typeMap: Record<string, string> = {
        security:     "Perform a thorough security audit. Identify vulnerabilities, injection risks, auth flaws, and insecure patterns.",
        performance:  "Analyse performance bottlenecks, O(n) complexities, memory leaks, and optimisation opportunities.",
        quality:      "Review code quality: SOLID principles, readability, test coverage gaps, naming, and maintainability.",
        dependencies: "Inspect dependencies and imports: unused, outdated, circular, or risky packages.",
        general:      "Provide a comprehensive analysis covering correctness, style, and improvement suggestions.",
      };
      const prompt = `${typeMap[args.analysisType ?? "general"]}\n\nCode:\n\`\`\`\n${args.code}\n\`\`\``;
      try {
        const result = await router.route({
          prompt,
          context:      args.context,
          overrideTier: "T1-CLOUD",
          options: { temperature: 0.1 },
        });
        return { content: [{ type: "text" as const, text: result.content }] };
      } catch (err) {
        return {
          content: [{ type: "text" as const, text: `T1-CLOUD analyze error: ${err instanceof Error ? err.message : err}` }],
          isError: true,
        };
      }
    },
  );
}
