import type { TierName, TierMetrics } from "../types.js";

interface RoutingLogEntry {
  ts:          string;
  tier:        TierName;
  taskType:    string;
  complexity:  string;
  quality:     number;
  latencyMs:   number;
  success:     boolean;
  escalation?: boolean;
  reason?:     string;
}

export class MetricsTracker {
  private metrics: Map<TierName, TierMetrics> = new Map();
  private log: RoutingLogEntry[] = [];
  private readonly LOG_LIMIT = 100;

  constructor() {
    const tiers: TierName[] = ["T1-LOCAL","T1-CLOUD","T2-PRO","T2-FLASH","T2-LITE","T3"];
    for (const tier of tiers) {
      this.metrics.set(tier, { tier, calls:0, successes:0, errors:0, escalations:0, avgQuality:0, avgLatencyMs:0 });
    }
  }

  recordSuccess(tier: TierName, quality: number, latencyMs: number, taskType = "UNKNOWN", complexity = "UNKNOWN"): void {
    const m = this._get(tier);
    const n = m.successes;
    m.calls++;
    m.successes++;
    m.avgQuality   = (m.avgQuality   * n + quality)   / (n + 1);
    m.avgLatencyMs = (m.avgLatencyMs * n + latencyMs) / (n + 1);
    this._log({ tier, taskType, complexity, quality, latencyMs, success: true });
  }

  recordError(tier: TierName, err: Error, taskType = "UNKNOWN"): void {
    const m = this._get(tier);
    m.calls++;
    m.errors++;
    this._log({ tier, taskType, complexity: "UNKNOWN", quality: 0, latencyMs: 0, success: false, reason: err.message });
  }

  recordSkip(tier: TierName, reason: string): void {
    this._log({ tier, taskType: "UNKNOWN", complexity: "UNKNOWN", quality: 0, latencyMs: 0, success: false, reason });
  }

  recordEscalation(tier: TierName, reason: string, quality: number): void {
    const m = this._get(tier);
    m.escalations++;
    this._log({ tier, taskType: "UNKNOWN", complexity: "UNKNOWN", quality, latencyMs: 0, success: false, escalation: true, reason });
  }

  getAll(): TierMetrics[] {
    return Array.from(this.metrics.values());
  }

  getLog(): RoutingLogEntry[] {
    return this.log.slice(-this.LOG_LIMIT);
  }

  /** Returns per-tier metrics augmented with a successRate (0–1). */
  getSummary(): Record<string, TierMetrics & { successRate: number }> {
    const result: Record<string, TierMetrics & { successRate: number }> = {};
    for (const [tier, m] of this.metrics) {
      result[tier] = { ...m, successRate: m.calls > 0 ? m.successes / m.calls : 0 };
    }
    return result;
  }

  /** Returns the full routing log (last LOG_LIMIT entries). */
  getRoutingLog(): RoutingLogEntry[] {
    return this.getLog();
  }

  private _get(tier: TierName): TierMetrics {
    return this.metrics.get(tier) ?? { tier, calls:0, successes:0, errors:0, escalations:0, avgQuality:0, avgLatencyMs:0 };
  }

  private _log(entry: Omit<RoutingLogEntry,"ts">): void {
    this.log.push({ ts: new Date().toISOString(), ...entry });
    if (this.log.length > this.LOG_LIMIT * 2) {
      this.log = this.log.slice(-this.LOG_LIMIT);
    }
  }
}
