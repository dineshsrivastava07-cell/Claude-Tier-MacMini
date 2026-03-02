import { McpServer }   from "@modelcontextprotocol/sdk/server/mcp.js";
import { z }           from "zod";
import { TierRouter }  from "../core/router.js";
import type { TierName } from "../types.js";
import {
  RouteTaskInput,
  HealthCheckInput,
  ExplainInput,
  OverrideInput,
} from "../types.js";

export function registerRoutingTools(server: McpServer, router: TierRouter): void {

  // ── tier_route_task ────────────────────────────────────────────────────────
  server.tool(
    "tier_route_task",
    "Intelligently route a task through the optimal AI tier (T1-LOCAL → T1-CLOUD → T2 → T3) " +
    "with automatic quality-gate fallback. Returns the response plus routing metadata.",
    RouteTaskInput.shape,
    async (args: z.infer<typeof RouteTaskInput>) => {
      try {
        const result = await router.route({
          prompt:           args.prompt,
          context:          args.context,
          overrideTier:     args.override_tier as TierName | undefined,
          qualityThreshold: args.quality_threshold,
          options: {
            temperature: args.temperature,
          },
        });
        return {
          content: [{
            type: "text" as const,
            text: JSON.stringify({
              response:      result.content,
              tier:          result.tier,
              model:         result.model,
              quality:       result.quality,
              latencyMs:     result.latencyMs,
              tokensUsed:    result.tokensUsed,
              fallbackUsed:  result.fallbackUsed,
              fallbackReason: result.fallbackReason,
            }, null, 2),
          }],
        };
      } catch (err) {
        return {
          content: [{ type: "text" as const, text: `Error: ${err instanceof Error ? err.message : err}` }],
          isError: true,
        };
      }
    },
  );

  // ── tier_health_check ──────────────────────────────────────────────────────
  server.tool(
    "tier_health_check",
    "Probe the health of one or all tiers. Returns availability, latency, and model info. " +
    "Use 'ALL' to check everything, 'T2' for all Gemini variants, or a specific tier name.",
    HealthCheckInput.shape,
    async (args: z.infer<typeof HealthCheckInput>) => {
      const which = (args.tier ?? "ALL") as "ALL" | "T2" | TierName;
      const results = await router.checkHealth(which);
      const summary = results.map(r =>
        `${r.tier}: ${r.healthy ? "✓ HEALTHY" : "✗ UNHEALTHY"} | model=${r.model} | latency=${r.latencyMs}ms${r.error ? ` | error=${r.error}` : ""}`,
      ).join("\n");
      return {
        content: [{
          type: "text" as const,
          text: `Tier Health Report\n${"─".repeat(60)}\n${summary}\n\n${JSON.stringify(results, null, 2)}`,
        }],
      };
    },
  );

  // ── tier_explain_decision ──────────────────────────────────────────────────
  server.tool(
    "tier_explain_decision",
    "Classify a prompt and explain which tier would be selected and why — without executing it. " +
    "Useful for understanding routing logic and cost/latency estimates.",
    ExplainInput.shape,
    async (args: z.infer<typeof ExplainInput>) => {
      const decision = await router.explain({ prompt: args.prompt, context: args.context });
      const text = [
        `Routing Decision`,
        `${"─".repeat(60)}`,
        `Selected Tier  : ${decision.selectedTier}`,
        `Model          : ${decision.model}`,
        `Task Type      : ${decision.taskType}`,
        `Complexity     : ${decision.complexity}`,
        `Confidence     : ${(decision.confidence * 100).toFixed(1)}%`,
        `Reasoning      : ${decision.reasoning}`,
        `Fallback Path  : ${decision.fallbackPath.join(" → ")}`,
        `Est. Cost      : ${decision.estimatedCost}`,
        `Est. Latency   : ${decision.estimatedLatencyMs}ms`,
      ].join("\n");
      return { content: [{ type: "text" as const, text }] };
    },
  );

  // ── tier_override ──────────────────────────────────────────────────────────
  server.tool(
    "tier_override",
    "Force execution on a specific tier, bypassing automatic classification. " +
    "Useful for testing, debugging, or when you know exactly which tier you need.",
    OverrideInput.shape,
    async (args: z.infer<typeof OverrideInput>) => {
      try {
        const result = await router.route({
          prompt:       args.prompt,
          context:      args.context,
          overrideTier: args.tier as TierName,
          options: {
            maxTokens: args.max_tokens,
          },
        });
        return {
          content: [{
            type: "text" as const,
            text: JSON.stringify({
              response:  result.content,
              tier:      result.tier,
              model:     result.model,
              quality:   result.quality,
              latencyMs: result.latencyMs,
            }, null, 2),
          }],
        };
      } catch (err) {
        return {
          content: [{ type: "text" as const, text: `Error: ${err instanceof Error ? err.message : err}` }],
          isError: true,
        };
      }
    },
  );
}
