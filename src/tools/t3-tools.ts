import { McpServer }  from "@modelcontextprotocol/sdk/server/mcp.js";
import { z }          from "zod";
import { TierRouter } from "../core/router.js";
import { T3ClaudeInput } from "../types.js";

export function registerT3Tools(server: McpServer, router: TierRouter): void {

  // ── t3_claude_architect ────────────────────────────────────────────────────
  server.tool(
    "t3_claude_architect",
    "Use Claude (T3) for complex architectural design, system planning, and high-stakes decisions. " +
    "Best for: multi-service architecture, security design, scalability planning, ADR creation.",
    T3ClaudeInput.shape,
    async (args: z.infer<typeof T3ClaudeInput>) => {
      const systemContext = [
        "You are an elite software architect.",
        "Produce detailed, production-grade architectural decisions with:",
        "- Clear rationale and trade-off analysis",
        "- Concrete implementation guidance",
        "- Security-by-design principles",
        "- Scalability and observability considerations",
        args.context ? `\nProject context:\n${args.context}` : "",
      ].filter(Boolean).join("\n");

      try {
        const result = await router.route({
          prompt:       args.prompt,
          context:      systemContext,
          overrideTier: "T3",
          options: {
            maxTokens:   args.max_tokens,
            temperature: 0.3,
          },
        });
        return { content: [{ type: "text" as const, text: result.content }] };
      } catch (err) {
        return {
          content: [{ type: "text" as const, text: `T3 architect error: ${err instanceof Error ? err.message : err}` }],
          isError: true,
        };
      }
    },
  );

  // ── t3_claude_epic ─────────────────────────────────────────────────────────
  server.tool(
    "t3_claude_epic",
    "Use Claude (T3) to build complete, production-ready implementations for large, complex tasks. " +
    "Ideal for: full feature implementation, multi-file refactors, comprehensive solutions requiring " +
    "deep reasoning across many constraints simultaneously.",
    {
      task:        z.string().describe("The complete task or feature to implement"),
      context:     z.string().optional().describe("Codebase context, constraints, or requirements"),
      outputStyle: z.enum(["implementation", "plan_then_implement", "analysis_then_implement"])
                    .optional()
                    .default("implementation")
                    .describe("How to structure the output"),
      maxTokens:   z.number().int().positive().optional().default(16384),
    },
    async (args: { task: string; context?: string; outputStyle?: string; maxTokens?: number }) => {
      const stylePrefix: Record<string, string> = {
        implementation:          "",
        plan_then_implement:     "First create a detailed implementation plan, then provide the full implementation.\n\n",
        analysis_then_implement: "First analyse requirements and constraints, then provide the full implementation.\n\n",
      };
      const prompt = `${stylePrefix[args.outputStyle ?? "implementation"]}${args.task}`;
      try {
        const result = await router.route({
          prompt,
          context:      args.context,
          overrideTier: "T3",
          options: {
            maxTokens:   args.maxTokens ?? 16384,
            temperature: 0.2,
          },
        });
        return { content: [{ type: "text" as const, text: result.content }] };
      } catch (err) {
        return {
          content: [{ type: "text" as const, text: `T3 epic error: ${err instanceof Error ? err.message : err}` }],
          isError: true,
        };
      }
    },
  );
}
