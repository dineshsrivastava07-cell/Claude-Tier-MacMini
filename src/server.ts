import { McpServer }  from "@modelcontextprotocol/sdk/server/mcp.js";
import { TierRouter } from "./core/router.js";

import {
  registerRoutingTools,
  registerT1Tools,
  registerT2Tools,
  registerT3Tools,
  registerPipelineTools,
} from "./tools/index.js";

import { registerTierConfigResource } from "./resources/tier-config.js";
import { registerTierMetricsResource } from "./resources/tier-metrics.js";
import { registerRoutingLogResource }  from "./resources/routing-log.js";

export function createServer(): { server: McpServer; router: TierRouter } {
  const router = new TierRouter();

  const server = new McpServer({
    name:    "tier-router-mcp",
    version: "1.0.0",
  });

  // ── Tools ──────────────────────────────────────────────────────────────────
  registerRoutingTools(server, router);   // 4 tools: route, health, explain, override
  registerT1Tools(server, router);        // 4 tools: t1-local-gen, t1-local-complete, t1-cloud-gen, t1-cloud-analyze
  registerT2Tools(server, router);        // 4 tools: t2-pro, t2-flash, t2-lite, t2-image
  registerT3Tools(server, router);        // 2 tools: t3-architect, t3-epic
  registerPipelineTools(server, router);  // 4 tools: code-review, debug-chain, build-fullstack, qa-full

  // ── Resources ─────────────────────────────────────────────────────────────
  registerTierConfigResource(server);              // tier://config
  registerTierMetricsResource(server, router.metrics); // tier://metrics
  registerRoutingLogResource(server, router.metrics);  // tier://routing-log

  return { server, router };
}
