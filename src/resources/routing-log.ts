import { McpServer }     from "@modelcontextprotocol/sdk/server/mcp.js";
import { MetricsTracker } from "../core/metrics.js";

export function registerRoutingLogResource(server: McpServer, metrics: MetricsTracker): void {
  server.resource(
    "routing-log",
    "tier://routing-log",
    { mimeType: "application/json" },
    async () => {
      const log     = metrics.getRoutingLog();
      const recent  = log.slice().reverse().slice(0, 50); // last 50, newest first
      return {
        contents: [{
          uri:      "tier://routing-log",
          mimeType: "application/json",
          text:     JSON.stringify({ count: log.length, entries: recent }, null, 2),
        }],
      };
    },
  );
}
