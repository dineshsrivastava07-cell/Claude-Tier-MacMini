import { McpServer }  from "@modelcontextprotocol/sdk/server/mcp.js";
import { z }          from "zod";
import { TierRouter } from "../core/router.js";
import { T2GeminiInput } from "../types.js";

export function registerT2Tools(server: McpServer, router: TierRouter): void {

  // ── t2_gemini_pro_reason ──────────────────────────────────────────────────
  server.tool(
    "t2_gemini_pro_reason",
    "Use Gemini 2.5 Pro (T2-PRO) for deep reasoning, architecture decisions, complex analysis, " +
    "or any task requiring advanced multi-step thinking.",
    T2GeminiInput.shape,
    async (args: z.infer<typeof T2GeminiInput>) => {
      try {
        const result = await router.route({
          prompt:       args.prompt,
          context:      args.context,
          overrideTier: "T2-PRO",
          options: { temperature: 0.2 },
        });
        return { content: [{ type: "text" as const, text: result.content }] };
      } catch (err) {
        return {
          content: [{ type: "text" as const, text: `T2-PRO error: ${err instanceof Error ? err.message : err}` }],
          isError: true,
        };
      }
    },
  );

  // ── t2_gemini_flash_generate ──────────────────────────────────────────────
  server.tool(
    "t2_gemini_flash_generate",
    "Generate text or code using Gemini 2.5 Flash (T2-FLASH) — fast, balanced quality/speed. " +
    "Good for standard coding tasks, explanations, and medium-complexity problems.",
    T2GeminiInput.shape,
    async (args: z.infer<typeof T2GeminiInput>) => {
      try {
        const result = await router.route({
          prompt:       args.prompt,
          context:      args.context,
          overrideTier: "T2-FLASH",
          options: { temperature: 0.2 },
        });
        return { content: [{ type: "text" as const, text: result.content }] };
      } catch (err) {
        return {
          content: [{ type: "text" as const, text: `T2-FLASH error: ${err instanceof Error ? err.message : err}` }],
          isError: true,
        };
      }
    },
  );

  // ── t2_gemini_lite_validate ───────────────────────────────────────────────
  server.tool(
    "t2_gemini_lite_validate",
    "Validate, lint, or check content using Gemini 2.5 Flash-Lite (T2-LITE) — lightest Gemini. " +
    "Ideal for schema validation, syntax checking, and quick yes/no assessments.",
    {
      content:       z.string().describe("Content to validate"),
      validationType: z.enum(["json", "yaml", "typescript", "python", "sql", "general"])
                       .optional()
                       .default("general")
                       .describe("Type of validation"),
      rules:         z.string().optional().describe("Custom validation rules or schema"),
      context:       z.string().optional(),
    },
    async (args: { content: string; validationType?: string; rules?: string; context?: string }) => {
      const typeInstructions: Record<string, string> = {
        json:       "Validate the JSON structure. Check for syntax errors, missing required fields, and type mismatches.",
        yaml:       "Validate the YAML. Check indentation, key conflicts, and structural correctness.",
        typescript: "Check TypeScript for type errors, missing imports, and syntax issues.",
        python:     "Check Python for syntax errors, undefined variables, and style violations.",
        sql:        "Validate SQL syntax, check for injection risks, and verify query structure.",
        general:    "Validate content quality, correctness, and completeness.",
      };
      const instructions = typeInstructions[args.validationType ?? "general"];
      const rulesSection = args.rules ? `\n\nValidation Rules:\n${args.rules}` : "";
      const prompt = `${instructions}${rulesSection}\n\nContent to validate:\n\`\`\`\n${args.content}\n\`\`\`\n\nProvide: PASS/FAIL status, list of issues found (if any), and brief explanation.`;
      try {
        const result = await router.route({
          prompt,
          context:      args.context,
          overrideTier: "T2-LITE",
          options: { temperature: 0.0 },
        });
        return { content: [{ type: "text" as const, text: result.content }] };
      } catch (err) {
        return {
          content: [{ type: "text" as const, text: `T2-LITE error: ${err instanceof Error ? err.message : err}` }],
          isError: true,
        };
      }
    },
  );

  // ── t2_gemini_analyze_image ───────────────────────────────────────────────
  server.tool(
    "t2_gemini_analyze_image",
    "Analyze an image or diagram using Gemini 2.5 Pro vision capabilities. " +
    "Supports architecture diagrams, UI mockups, ERDs, and screenshots.",
    {
      imageUrl:     z.string().describe("URL or base64 data URI of the image"),
      question:     z.string().describe("What to analyze or extract from the image"),
      outputFormat: z.enum(["description", "code", "json", "markdown"])
                     .optional()
                     .default("description")
                     .describe("Desired output format"),
    },
    async (args: { imageUrl: string; question: string; outputFormat?: string }) => {
      const prompt = `Analyze the image at: ${args.imageUrl}\n\nQuestion: ${args.question}\n\nOutput format: ${args.outputFormat ?? "description"}`;
      try {
        const result = await router.route({
          prompt,
          overrideTier: "T2-PRO",
          options: { temperature: 0.2 },
        });
        return { content: [{ type: "text" as const, text: result.content }] };
      } catch (err) {
        return {
          content: [{ type: "text" as const, text: `T2 image analyze error: ${err instanceof Error ? err.message : err}` }],
          isError: true,
        };
      }
    },
  );
}
