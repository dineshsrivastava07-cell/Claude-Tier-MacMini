# Pipeline Implementations Reference

Complete multi-tier pipeline patterns. Each pipeline chains tiers sequentially,
passing context forward and stopping early when quality threshold is met.

---

## 1. Code Review Pipeline  (`pipeline_code_review`)

**Chain:** T1-LOCAL lint → T2-FLASH semantic → T3 architectural (conditional)

```typescript
async function pipelineCodeReview(code: string, language = "typescript", focus: string[] = ["security","correctness"]) {
  const report: string[] = [];

  // Stage 1 — T1-LOCAL: fast lint
  report.push("## Stage 1: Quick Lint (T1-LOCAL)");
  let t1Output = "";
  try {
    t1Output = await t1LocalGenerate(
      `Quick lint check — identify obvious bugs, syntax issues, and style violations only.\n\nCode (${language}):\n\`\`\`\n${code}\n\`\`\``
    );
    report.push(t1Output);
  } catch (e) { report.push(`⚠ T1-LOCAL unavailable: ${e}`); }

  // Stage 2 — T2-FLASH: semantic review
  report.push("\n## Stage 2: Semantic Review (T2-FLASH)");
  let t2Output = "";
  try {
    t2Output = await t2GeminiCLI(
      `Perform a ${focus.join(", ")} review of this ${language} code. ` +
      `Cite line numbers. Provide fix for each issue.\n\nCode:\n\`\`\`\n${code}\n\`\`\``,
      "gemini-2.5-flash"
    );
    report.push(t2Output);

    // Stage 3 — T3: only when critical issues found
    const hasCritical = /critical|high severity|vulnerability|injection|exploit/i.test(t2Output);
    if (hasCritical && focus.includes("architecture")) {
      report.push("\n## Stage 3: Architectural Deep-Dive (T3)");
      const t3Output = await t3ClaudeSDK(
        "You are a principal engineer performing security and architecture review.",
        `Review and harden:\n\`\`\`\n${code}\n\`\`\`\n\nPrior findings:\n${t2Output}`
      );
      report.push(t3Output);
    }
  } catch (e) { report.push(`⚠ T2-FLASH unavailable: ${e}`); }

  return report.join("\n\n");
}
```

---

## 2. Debug Escalation Chain  (`pipeline_debug_chain`)

**Chain:** T1-LOCAL hypothesis → T2-FLASH deep analysis → T3 root cause (if needed)

```typescript
async function pipelineDebugChain(
  code: string,
  errorMessage: string,
  language = "typescript"
) {
  const ctx    = `Language: ${language}\nError: ${errorMessage}`;
  const prompt = `Debug this error. Provide root cause and complete fix.`;
  const report: string[] = [];

  // T1: fast hypothesis
  report.push("## Tier 1 — Quick Diagnosis (T1-LOCAL)");
  let t1Quality = 0;
  try {
    const t1 = await t1LocalGenerate(prompt, `${ctx}\n\nCode:\n\`\`\`\n${code}\n\`\`\``);
    t1Quality = scoreOutput(t1, "DEBUG");
    report.push(t1, `*quality=${t1Quality.toFixed(2)}*`);
  } catch (e) { report.push(`⚠ T1-LOCAL: ${e}`); }

  if (t1Quality >= 0.80) return report.join("\n\n"); // resolved

  // T2: deeper analysis
  report.push("\n## Tier 2 — Deep Analysis (T2-FLASH)");
  let t2Quality = 0;
  try {
    const t2 = await t2GeminiCLI(
      `${prompt}\nTrace the full execution path. Provide corrected implementation.\n\n${ctx}\n\nCode:\n\`\`\`\n${code}\n\`\`\``,
      "gemini-2.5-flash"
    );
    t2Quality = scoreOutput(t2, "DEBUG");
    report.push(t2, `*quality=${t2Quality.toFixed(2)}*`);
  } catch (e) { report.push(`⚠ T2-FLASH: ${e}`); }

  if (t2Quality >= 0.80) return report.join("\n\n"); // resolved

  // T3: root cause + redesign
  report.push("\n## Tier 3 — Root Cause (T3)");
  try {
    const t3 = await t3ClaudeSDK(
      "You are an expert debugger. Identify root cause, all contributing factors, and provide a production-grade fix with tests.",
      `${ctx}\n\nCode:\n\`\`\`\n${code}\n\`\`\``
    );
    report.push(t3);
  } catch (e) { report.push(`⚠ T3: ${e}`); }

  return report.join("\n\n");
}
```

---

## 3. Full-Stack Build Pipeline  (`pipeline_build_fullstack`)

**Chain:** T1-CLOUD scaffold → T2-PRO implement → T3 harden

```typescript
async function pipelineFullstackBuild(requirements: string, stack: {
  language?: string; framework?: string; database?: string;
} = {}) {
  const tech = [stack.language ?? "TypeScript", stack.framework, stack.database].filter(Boolean).join(", ");
  const report: string[] = [];

  // Phase 1: T1-CLOUD scaffold
  report.push("## Phase 1: Scaffold (T1-CLOUD)");
  let scaffold = "";
  try {
    scaffold = await t1CloudGenerate(
      `Create a complete project scaffold.\nStack: ${tech}\nRequirements: ${requirements}\nOutput: folder structure + boilerplate code + package.json + Dockerfile`
    );
    report.push(scaffold);
  } catch (e) { report.push(`⚠ T1-CLOUD: ${e}`); }

  // Phase 2: T2-PRO business logic
  report.push("\n## Phase 2: Business Logic (T2-PRO)");
  let logic = "";
  try {
    logic = await t2GeminiSDK(
      `Implement full business logic.\nStack: ${tech}\nRequirements: ${requirements}\n\nScaffold:\n${scaffold}`,
      "gemini-2.5-pro",
      { maxOutputTokens: 8192 }
    );
    report.push(logic);
  } catch (e) { report.push(`⚠ T2-PRO: ${e}`); }

  // Phase 3: T3 production hardening
  report.push("\n## Phase 3: Production Hardening (T3)");
  try {
    const t3 = await t3ClaudeSDK(
      "You are a principal engineer. Apply security-by-design, observability, SOLID principles, and comprehensive error handling.",
      `Requirements: ${requirements}\n\nImplementation:\n${logic || scaffold}`
    );
    report.push(t3);
  } catch (e) { report.push(`⚠ T3: ${e}`); }

  return report.join("\n\n");
}
```

---

## 4. QA Pipeline  (`pipeline_qa_full`)

**Chain:** T1-CLOUD unit tests → T2-FLASH integration → T3 E2E (when coverage ≥ 90%)

```typescript
async function pipelineQAFull(code: string, language = "typescript", coverageTarget = 80) {
  const fw     = language === "python" ? "pytest" : "vitest";
  const report: string[] = [];

  // Unit tests — T1-CLOUD
  report.push("## Unit Tests (T1-CLOUD)");
  try {
    const t1 = await t1CloudGenerate(
      `Write comprehensive unit tests using ${fw} targeting ${coverageTarget}% coverage.\n` +
      `Cover: happy path, edge cases, error conditions.\n\nCode:\n\`\`\`\n${code}\n\`\`\``
    );
    report.push(t1);
  } catch (e) { report.push(`⚠ T1-CLOUD: ${e}`); }

  // Integration tests — T2-FLASH
  report.push("\n## Integration Tests (T2-FLASH)");
  try {
    const t2 = await t2GeminiCLI(
      `Write integration tests using ${fw}. Focus on API contracts, service interactions, async flows.\n\nCode:\n\`\`\`\n${code}\n\`\`\``,
      "gemini-2.5-flash"
    );
    report.push(t2);
  } catch (e) { report.push(`⚠ T2-FLASH: ${e}`); }

  // E2E — T3 (only for high coverage targets)
  if (coverageTarget >= 90) {
    report.push("\n## E2E + Performance Tests (T3)");
    try {
      const t3 = await t3ClaudeSDK(
        "You are a QA engineer. Write E2E tests and performance benchmarks.",
        `Write E2E tests using ${fw}. Cover full user flows and SLA validation.\n\nCode:\n\`\`\`\n${code}\n\`\`\``
      );
      report.push(t3);
    } catch (e) { report.push(`⚠ T3: ${e}`); }
  }

  return report.join("\n\n");
}
```

---

## 5. Analytics Pipeline  (RIECT / ClickHouse)

**Chain:** T1-LOCAL SQL → T1-CLOUD ML → T2-PRO statistical validation → T3 architecture

```typescript
async function pipelineAnalytics(dataSpec: string, kpis: string[]) {
  const report: string[] = [];

  // SQL boilerplate — T1-LOCAL
  report.push("## SQL & Data Pipeline (T1-LOCAL)");
  try {
    report.push(await t1LocalGenerate(
      `Generate ClickHouse SQL queries for these KPIs: ${kpis.join(", ")}\n\nData schema: ${dataSpec}`
    ));
  } catch (e) { report.push(`⚠ T1-LOCAL: ${e}`); }

  // ML pipeline — T1-CLOUD
  report.push("\n## ML / Feature Engineering (T1-CLOUD)");
  try {
    report.push(await t1CloudGenerate(
      `Implement a Python ML pipeline for: ${kpis.join(", ")}\nUse pandas, scikit-learn. Include feature engineering and model evaluation.`
    ));
  } catch (e) { report.push(`⚠ T1-CLOUD: ${e}`); }

  // Statistical validation — T2-PRO
  report.push("\n## Statistical Analysis (T2-PRO)");
  try {
    report.push(await t2GeminiSDK(
      `Validate statistical methodology for: ${kpis.join(", ")}\n` +
      `Check: confidence intervals, significance testing, seasonality, outlier treatment.\n` +
      `Data spec: ${dataSpec}`,
      "gemini-2.5-pro"
    ));
  } catch (e) { report.push(`⚠ T2-PRO: ${e}`); }

  return report.join("\n\n");
}
```

---

## Quality Score Helper (shared across pipelines)

```typescript
function scoreOutput(output: string, taskType: string): number {
  if (!output?.trim() || output.trim().length < 10) return 0.0;
  let score = 1.0;
  if (output.trim().length < 30)                          score -= 0.40;
  if (/i cannot|i can't|i'm unable/i.test(output))        score -= 0.50;
  if (/^(error|sorry)/i.test(output.trim()))              score -= 0.20;
  if (["CODE_GEN","CODE_FIX","REFACTOR","QA","DEBUG"].includes(taskType)) {
    const hasCode = /```|    |\t/.test(output);
    if (!hasCode && output.length < 300)                  score -= 0.15;
    if (/todo|fixme/i.test(output))                       score -= 0.15;
  }
  if (output.length > 1000) score = Math.min(score + 0.05, 1.0);
  return Math.max(0, Math.min(1, score));
}
```
