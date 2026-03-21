import { TaskClassifier }         from "./classifier.js";
import { QualityScorer }          from "./quality-scorer.js";
import { MetricsTracker }         from "./metrics.js";
import { buildExecutionPlan }     from "./fallback-chain.js";
import { BaseTier }               from "../tiers/base-tier.js";
import { T1LocalTier }            from "../tiers/t1-local.js";
import { T1CloudTier }            from "../tiers/t1-cloud.js";
import { T2GeminiTier }           from "../tiers/t2-gemini.js";
import { T3ClaudeTier }           from "../tiers/t3-claude.js";
import type {
  TierName, TierResult, RouteRequest, RoutingDecision,
  TierHealthStatus, TaskType,
} from "../types.js";

export class TierRouter {
  private readonly classifier: TaskClassifier;
  private readonly scorer:     QualityScorer;
  readonly          metrics:   MetricsTracker;

  private readonly tiers: Map<TierName, BaseTier>;
  private readonly qualityThreshold: number;

  constructor() {
    this.classifier = new TaskClassifier();
    this.scorer     = new QualityScorer();
    this.metrics    = new MetricsTracker();
    this.qualityThreshold = Number(process.env.QUALITY_THRESHOLD ?? 0.75);

    const t1l  = new T1LocalTier();
    const t1c  = new T1CloudTier();
    const t2pro   = new T2GeminiTier("gemini-2.5-pro");
    const t2flash = new T2GeminiTier("gemini-2.5-flash");
    const t2lite  = new T2GeminiTier("gemini-2.5-flash-lite");
    const t3   = new T3ClaudeTier();

    this.tiers = new Map<TierName, BaseTier>();
    this.tiers.set("T1-LOCAL", t1l);
    this.tiers.set("T1-CLOUD", t1c);
    this.tiers.set("T2-PRO",   t2pro);
    this.tiers.set("T2-FLASH", t2flash);
    this.tiers.set("T2-LITE",  t2lite);
    this.tiers.set("T3",       t3);
  }

  // ── Core routing ────────────────────────────────────────────────────────────

  async route(req: RouteRequest): Promise<TierResult> {
    const classification = this.classifier.classify(req.prompt, req.context);
    const plan           = buildExecutionPlan(classification.recommendedTier, req.overrideTier);
    const qThreshold     = req.qualityThreshold ?? this.qualityThreshold;
    let   fallbackUsed   = false;
    let   fallbackReason: string | undefined;

    for (const tierName of plan) {
      const tier = this._getTier(tierName);
      if (!tier) continue;

      const healthy = await tier.isHealthy();
      if (!healthy) {
        this.metrics.recordSkip(tierName, "unhealthy");
        fallbackReason = `${tierName} unhealthy`;
        fallbackUsed   = true;
        continue;
      }

      const startMs = Date.now();
      try {
        const raw     = await tier.execute(req.prompt, req.context, {
          ...req.options,
          ...(this._geminiModelOpt(tierName)),
        });
        const quality = this.scorer.score(raw, classification.taskType);
        const latency = Date.now() - startMs;

        this.metrics.recordSuccess(tierName, quality, latency,
          classification.taskType, classification.complexity);

        if (quality >= qThreshold) {
          return {
            tier:         tierName,
            model:        tier.modelId,
            content:      raw,
            quality,
            tokensUsed:   this._estimateTokens(raw),
            latencyMs:    latency,
            fallbackUsed,
            fallbackReason,
          };
        }

        // Quality too low → escalate
        this.metrics.recordEscalation(tierName, "low_quality", quality);
        fallbackReason = `${tierName} quality ${quality.toFixed(2)} < ${qThreshold}`;
        fallbackUsed   = true;

      } catch (err) {
        this.metrics.recordError(tierName, err instanceof Error ? err : new Error(String(err)));
        fallbackReason = `${tierName} error: ${err instanceof Error ? err.message : err}`;
        fallbackUsed   = true;
      }
    }

    throw new Error(
      `All tiers exhausted (plan: ${plan.join("→")}). ` +
      `Last reason: ${fallbackReason ?? "unknown"}. ` +
      `Run tier_health_check to diagnose.`
    );
  }

  // ── Explain (classify only — no execution) ──────────────────────────────────

  async explain(req: { prompt: string; context?: string }): Promise<RoutingDecision> {
    const cl    = this.classifier.classify(req.prompt, req.context);
    const plan  = buildExecutionPlan(cl.recommendedTier);
    const tier  = this._getTier(cl.recommendedTier);
    return {
      selectedTier:       cl.recommendedTier,
      model:              tier?.modelId ?? cl.recommendedTier,
      taskType:           cl.taskType,
      complexity:         cl.complexity,
      reasoning:          cl.reasoning,
      confidence:         cl.confidence,
      fallbackPath:       plan,
      estimatedCost:      this.classifier.getEstimatedCost(cl.recommendedTier),
      estimatedLatencyMs: this.classifier.getEstimatedLatency(cl.recommendedTier),
    };
  }

  // ── Health check ─────────────────────────────────────────────────────────────

  async checkHealth(which: "ALL"|TierName|"T2"): Promise<TierHealthStatus[]> {
    const toCheck: TierName[] = which === "ALL"
      ? ["T1-LOCAL","T1-CLOUD","T2-PRO","T2-FLASH","T2-LITE","T3"]
      : which === "T2"
        ? ["T2-PRO","T2-FLASH","T2-LITE"]
        : [which as TierName];

    const results: TierHealthStatus[] = [];
    for (const tierName of toCheck) {
      const tier    = this._getTier(tierName);
      const startMs = Date.now();
      if (!tier) { results.push({ tier: tierName, healthy: false, model: "N/A", latencyMs: 0, error: "No executor" }); continue; }
      try {
        const healthy = await tier.isHealthy();
        results.push({ tier: tierName, healthy, model: tier.modelId, latencyMs: Date.now() - startMs });
      } catch (e) {
        results.push({ tier: tierName, healthy: false, model: tier.modelId, latencyMs: Date.now() - startMs, error: String(e) });
      }
    }
    return results;
  }

  // ── Helpers ─────────────────────────────────────────────────────────────────

  private _getTier(name: TierName) {
    return this.tiers.get(name);
  }

  private _geminiModelOpt(tierName: TierName): object {
    const map: Partial<Record<TierName, string>> = {
      "T2-PRO":   "gemini-2.5-pro",
      "T2-FLASH": "gemini-2.5-flash",
      "T2-LITE":  "gemini-2.5-flash-lite",
    };
    const m = map[tierName];
    return m ? { geminiModel: m } : {};
  }

  private _estimateTokens(text: string): number {
    return Math.ceil(text.split(/\s+/).length * 1.3);
  }

  getTaskType(prompt: string): TaskType {
    return this.classifier.classify(prompt).taskType;
  }
}
