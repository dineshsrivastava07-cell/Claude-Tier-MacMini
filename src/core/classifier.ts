import type { ClassificationResult, TaskComplexity, TaskType, TierName } from "../types.js";

// ── Keyword maps ─────────────────────────────────────────────────────────────

const TYPE_KEYWORDS: Record<TaskType, string[]> = {
  QA:           ["test","unit test","pytest","jest","coverage","spec","mock","assert","fixture","integration test"],
  DEBUG:        ["bug","fix","error","exception","traceback","not working","crash","fail","debug","broken"],
  FULLSTACK:    ["full stack","fullstack","end-to-end app","full application","greenfield","complete platform"],
  ARCHITECTURE: ["design","architect","system design","pattern","microservice","scalable","infrastructure","trade-off","hld","lld","adr"],
  ANALYTICS:    ["analytics","analyze","statistics","metric","kpi","dashboard","report","pandas","numpy","clickhouse","forecast","spsf","sell-through","doi"],
  INTEGRATION:  ["integrate","wire","connect","webhook","sync","pipeline","workflow","orchestrate","api gateway","event"],
  REFACTOR:     ["refactor","restructure","extract","cleanup","clean up","improve code","rename","decouple"],
  CODE_GEN:     ["write","create","generate","implement","build","function","class","script","endpoint","boilerplate","scaffold"],
  CODE_FIX:     ["fix","patch","correct","resolve","update","adjust","change","modify"],
};

const EPIC_KEYWORDS    = ["full application","greenfield","end-to-end system","production-grade enterprise","complete platform","build entire","whole app"];
const COMPLEX_KEYWORDS = ["complex","advanced","sophisticated","distributed","multi-service","cross-domain","scalable production","enterprise-grade","microservices","machine learning","ml pipeline","neural","transformer","llm"];
const MODERATE_KEYWORDS= ["multi-file","multiple files","several","algorithm","integration","refactor","optimize","multi-step","security","performance-critical","api design","feature"];

// ── Routing matrix ────────────────────────────────────────────────────────────

const ROUTING_MATRIX: Record<TaskComplexity, Partial<Record<TaskType, TierName>>> & { _default: Record<TaskComplexity, TierName> } = {
  SIMPLE:   { CODE_GEN:"T1-LOCAL", CODE_FIX:"T1-LOCAL", DEBUG:"T1-LOCAL", QA:"T1-LOCAL", REFACTOR:"T1-LOCAL", ANALYTICS:"T1-LOCAL", INTEGRATION:"T1-LOCAL", ARCHITECTURE:"T1-LOCAL", FULLSTACK:"T1-LOCAL" },
  MODERATE: { CODE_GEN:"T1-CLOUD", CODE_FIX:"T1-CLOUD", DEBUG:"T1-CLOUD", QA:"T1-CLOUD", REFACTOR:"T1-CLOUD", ANALYTICS:"T2-PRO",   INTEGRATION:"T2-PRO",   ARCHITECTURE:"T2-PRO",   FULLSTACK:"T2-PRO"   },
  COMPLEX:  { CODE_GEN:"T1-CLOUD", CODE_FIX:"T1-CLOUD", DEBUG:"T1-CLOUD", QA:"T2-PRO",   REFACTOR:"T1-CLOUD", ANALYTICS:"T2-PRO",   INTEGRATION:"T2-PRO",   ARCHITECTURE:"T2-PRO",   FULLSTACK:"T3"       },
  EPIC:     { CODE_GEN:"T3",       CODE_FIX:"T3",       DEBUG:"T3",       QA:"T3",       REFACTOR:"T3",       ANALYTICS:"T3",       INTEGRATION:"T3",       ARCHITECTURE:"T3",       FULLSTACK:"T3"       },
  _default: { SIMPLE:"T1-LOCAL",  MODERATE:"T1-CLOUD",  COMPLEX:"T2-PRO",  EPIC:"T3" },
};

// ── Cost / latency estimates ──────────────────────────────────────────────────

const TIER_COST: Record<TierName, "free"|"low"|"medium"|"high"> = {
  "T1-LOCAL": "free", "T1-CLOUD": "free",
  "T2-PRO": "medium", "T2-FLASH": "low", "T2-LITE": "low",
  "T3": "high",
};

const TIER_LATENCY: Record<TierName, number> = {
  "T1-LOCAL": 8000, "T1-CLOUD": 45000,
  "T2-PRO": 12000, "T2-FLASH": 5000, "T2-LITE": 2000,
  "T3": 25000,
};

// ── Classifier ────────────────────────────────────────────────────────────────

export class TaskClassifier {
  classify(prompt: string, context?: string): ClassificationResult {
    const lower      = prompt.toLowerCase();
    const wordCount  = prompt.split(/\s+/).length;
    const ctxLines   = (context ?? "").split("\n").length;

    const taskType   = this._detectType(lower);
    const complexity = this._detectComplexity(lower, wordCount, ctxLines, taskType);
    const tier       = this._mapToTier(complexity, taskType);
    const confidence = this._scoreConfidence(lower, complexity, taskType);
    const reasoning  = this._buildReasoning(complexity, taskType, wordCount, ctxLines);

    return { complexity, taskType, recommendedTier: tier, confidence, reasoning };
  }

  private _detectType(text: string): TaskType {
    const scores: Partial<Record<TaskType, number>> = {};
    for (const [t, keywords] of Object.entries(TYPE_KEYWORDS) as [TaskType, string[]][]) {
      scores[t] = keywords.filter(k => text.includes(k)).length;
    }
    const best = (Object.entries(scores) as [TaskType, number][]).reduce((a, b) => b[1] > a[1] ? b : a);
    return best[1] > 0 ? best[0] : "CODE_GEN";
  }

  private _detectComplexity(text: string, words: number, ctxLines: number, type: TaskType): TaskComplexity {
    if (EPIC_KEYWORDS.some(k => text.includes(k)) || words >= 500 || ctxLines >= 300)
      return "EPIC";

    const complexTypes: TaskType[] = ["ARCHITECTURE", "FULLSTACK", "ANALYTICS"];
    if (COMPLEX_KEYWORDS.some(k => text.includes(k))
        || (words >= 250 && complexTypes.includes(type))
        || words >= 400 || ctxLines >= 100)
      return "COMPLEX";

    if (MODERATE_KEYWORDS.some(k => text.includes(k))
        || ["ARCHITECTURE","INTEGRATION","ANALYTICS","FULLSTACK"].includes(type)
        || words >= 60 || ctxLines >= 30)
      return "MODERATE";

    return "SIMPLE";
  }

  private _mapToTier(complexity: TaskComplexity, taskType: TaskType): TierName {
    return (ROUTING_MATRIX[complexity] as Partial<Record<TaskType, TierName>>)[taskType]
      ?? ROUTING_MATRIX._default[complexity];
  }

  private _scoreConfidence(text: string, complexity: TaskComplexity, type: TaskType): number {
    const keywords = [...(TYPE_KEYWORDS[type] ?? []), ...EPIC_KEYWORDS, ...COMPLEX_KEYWORDS];
    const hits = keywords.filter(k => text.includes(k)).length;
    return Math.min(0.95, 0.5 + hits * 0.08);
  }

  private _buildReasoning(c: TaskComplexity, t: TaskType, words: number, ctxLines: number): string {
    const tier = this._mapToTier(c, t);
    const costLabel = TIER_COST[tier];
    return `${c} ${t} (${words}w prompt, ${ctxLines} ctx lines) → ${tier} [cost:${costLabel}, ~${TIER_LATENCY[tier]}ms]`;
  }

  getEstimatedCost(tier: TierName): "free"|"low"|"medium"|"high" {
    return TIER_COST[tier];
  }

  getEstimatedLatency(tier: TierName): number {
    return TIER_LATENCY[tier];
  }
}
