import { McpServer }     from "@modelcontextprotocol/sdk/server/mcp.js";
import { MetricsTracker } from "../core/metrics.js";

export function registerTierMetricsResource(server: McpServer, metrics: MetricsTracker): void {
  server.resource(
    "tier-metrics",
    "tier://metrics",
    { mimeType: "application/json" },
    async () => {
      const summary = metrics.getSummary();
      const entries = Object.entries(summary);
      const totalCalls = entries.reduce((s, [, m]) => s + m.calls, 0);
      const report = {
        timestamp:  new Date().toISOString(),
        totalCalls,
        byTier: summary,
        topTier: entries
          .sort(([, a], [, b]) => b.calls - a.calls)
          .map(([name, m]) => ({
            tier:         name,
            calls:        m.calls,
            successRate:  `${(m.successRate * 100).toFixed(1)}%`,
            avgQuality:   m.avgQuality.toFixed(2),
            avgLatencyMs: Math.round(m.avgLatencyMs),
          })),
      };
      return {
        contents: [{
          uri:      "tier://metrics",
          mimeType: "application/json",
          text:     JSON.stringify(report, null, 2),
        }],
      };
    },
  );
}
