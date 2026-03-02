# Routing Engine Reference — TypeScript Source

Full source lives at: `~/tier-router-mcp/src/`

## Classifier (`src/core/classifier.ts`)

### Task Type Keywords
```typescript
const TYPE_KEYWORDS = {
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
```

### Complexity Detection Logic
```typescript
function detectComplexity(text: string, words: number, ctxLines: number, type: TaskType): TaskComplexity {
  // EPIC: explicit keywords OR 500+ words OR 300+ context lines
  if (EPIC_KEYWORDS.some(k => text.includes(k)) || words >= 500 || ctxLines >= 300)
    return "EPIC";

  // COMPLEX: complex keywords OR (250+ words + complex task type) OR 400+ words
  const complexTypes = ["ARCHITECTURE","FULLSTACK","ANALYTICS"];
  if (COMPLEX_KEYWORDS.some(k => text.includes(k))
      || (words >= 250 && complexTypes.includes(type))
      || words >= 400 || ctxLines >= 100)
    return "COMPLEX";

  // MODERATE: moderate keywords OR complex task types OR 60+ words
  if (MODERATE_KEYWORDS.some(k => text.includes(k))
      || ["ARCHITECTURE","INTEGRATION","ANALYTICS","FULLSTACK"].includes(type)
      || words >= 60 || ctxLines >= 30)
    return "MODERATE";

  return "SIMPLE";
}
```

### Routing Matrix (full 32-cell table)
```typescript
const ROUTING_MATRIX = {
  SIMPLE:   { CODE_GEN:"T1-LOCAL", CODE_FIX:"T1-LOCAL", DEBUG:"T1-LOCAL", QA:"T1-LOCAL",    REFACTOR:"T1-LOCAL", ANALYTICS:"T1-LOCAL", INTEGRATION:"T1-LOCAL", ARCHITECTURE:"T1-LOCAL", FULLSTACK:"T1-LOCAL" },
  MODERATE: { CODE_GEN:"T1-CLOUD", CODE_FIX:"T1-CLOUD", DEBUG:"T1-CLOUD", QA:"T1-CLOUD",    REFACTOR:"T1-CLOUD", ANALYTICS:"T2-PRO",   INTEGRATION:"T2-PRO",   ARCHITECTURE:"T2-PRO",   FULLSTACK:"T2-PRO"   },
  COMPLEX:  { CODE_GEN:"T1-CLOUD", CODE_FIX:"T1-CLOUD", DEBUG:"T1-CLOUD", QA:"T2-PRO",      REFACTOR:"T1-CLOUD", ANALYTICS:"T2-PRO",   INTEGRATION:"T2-PRO",   ARCHITECTURE:"T2-PRO",   FULLSTACK:"T3"       },
  EPIC:     { CODE_GEN:"T3",       CODE_FIX:"T3",       DEBUG:"T3",       QA:"T3",           REFACTOR:"T3",       ANALYTICS:"T3",       INTEGRATION:"T3",       ARCHITECTURE:"T3",       FULLSTACK:"T3"       },
};
```

## Quality Scorer (`src/core/quality-scorer.ts`)

```typescript
function score(output: string, taskType: TaskType): number {
  if (!output || output.trim().length < 10) return 0.0;

  let score = 1.0;

  // Universal penalties
  if (output.trim().length < 30)                            score -= 0.40;
  if (output.toLowerCase().includes("i cannot"))            score -= 0.50;
  if (output.toLowerCase().includes("i'm unable"))          score -= 0.40;
  if (output.toLowerCase().startsWith("error"))             score -= 0.20;

  // Code-task penalties
  if (["CODE_GEN","CODE_FIX","REFACTOR","QA","DEBUG"].includes(taskType)) {
    const hasCode = output.includes("```") || output.includes("    ") || output.includes("\t");
    if (!hasCode && output.length < 300)                    score -= 0.15;
    if (/todo|fixme/i.test(output))                         score -= 0.15;
    if (output.trim() === "pass" || output.trim() === "...") score -= 0.40;
    if (output.includes("NotImplementedError"))             score -= 0.30;
  }

  // Bonuses
  if (["ANALYTICS","ARCHITECTURE"].includes(taskType) && output.length > 500)
    score = Math.min(score + 0.05, 1.0);
  if (output.length > 1000) score = Math.min(score + 0.05, 1.0);

  return Math.max(0.0, Math.min(1.0, score));
}
```

## Fallback Chains (`src/core/fallback-chain.ts`)

```typescript
const FALLBACK_CHAINS = {
  "T1-LOCAL": ["T1-LOCAL", "T1-CLOUD", "T2-FLASH", "T3"],
  "T1-CLOUD": ["T1-CLOUD", "T2-FLASH", "T3"],
  "T2-PRO":   ["T2-PRO",  "T2-FLASH", "T3"],
  "T2-FLASH": ["T2-FLASH","T2-PRO",   "T3"],
  "T2-LITE":  ["T2-LITE", "T2-FLASH", "T1-CLOUD"],
  "T3":       ["T3"],
};
```

## Router (`src/core/router.ts`) — Route Loop

```typescript
async function route(req: RouteRequest): Promise<TierResult> {
  const classification = classifier.classify(req.prompt, req.context);
  const plan           = buildExecutionPlan(classification.recommendedTier, req.overrideTier);
  const qThreshold     = req.qualityThreshold ?? 0.75;
  let   fallbackUsed   = false;
  let   fallbackReason: string | undefined;

  for (const tierName of plan) {
    const tier = tiers.get(tierName);
    if (!tier) continue;

    if (!await tier.isHealthy()) {
      metrics.recordSkip(tierName, "unhealthy");
      fallbackReason = `${tierName} unhealthy`;
      fallbackUsed   = true;
      continue;
    }

    const startMs = Date.now();
    try {
      const raw     = await tier.execute(req.prompt, req.context, req.options);
      const quality = scorer.score(raw, classification.taskType);
      const latency = Date.now() - startMs;

      metrics.recordSuccess(tierName, quality, latency, classification.taskType, classification.complexity);

      if (quality >= qThreshold) {
        return { tier: tierName, model: tier.modelId, content: raw, quality, latencyMs: latency, fallbackUsed, fallbackReason };
      }

      // Escalate
      metrics.recordEscalation(tierName, "low_quality", quality);
      fallbackReason = `${tierName} quality ${quality.toFixed(2)} < ${qThreshold}`;
      fallbackUsed   = true;

    } catch (err) {
      metrics.recordError(tierName, err instanceof Error ? err : new Error(String(err)));
      fallbackReason = `${tierName} error: ${err instanceof Error ? err.message : err}`;
      fallbackUsed   = true;
    }
  }

  throw new Error(`All tiers exhausted (plan: ${plan.join("→")}). Last: ${fallbackReason}`);
}
```

## Cost / Latency Estimates

```typescript
const TIER_COST = {
  "T1-LOCAL": "free",   "T1-CLOUD": "free",
  "T2-PRO":   "medium", "T2-FLASH": "low",  "T2-LITE": "low",
  "T3":       "high",
};

const TIER_LATENCY_MS = {
  "T1-LOCAL": 8_000,  "T1-CLOUD": 45_000,
  "T2-PRO":   12_000, "T2-FLASH": 5_000,  "T2-LITE": 2_000,
  "T3":       25_000,
};
```

## Running Tests

```bash
cd ~/tier-router-mcp
npm run build                                          # compile
npx vitest run tests/unit/                             # 43 unit tests (no network)
INTEGRATION=true npx vitest run tests/integration/    # live tier tests
```
