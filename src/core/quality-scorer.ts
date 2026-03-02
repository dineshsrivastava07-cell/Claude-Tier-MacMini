import type { TaskType } from "../types.js";

/** Score model output 0.0–1.0. Below threshold → escalate to next tier. */
export class QualityScorer {
  score(output: string, taskType: TaskType): number {
    if (!output || output.trim().length < 10) return 0.0;

    const lower  = output.toLowerCase().trim();
    let   score  = 1.0;

    // ── Universal penalties ──────────────────────────────────────────────────
    if (output.trim().length < 30)                          score -= 0.40;
    if (lower.includes("i cannot") || lower.includes("i can't")) score -= 0.50;
    if (lower.includes("i'm unable") || lower.includes("i am unable")) score -= 0.40;
    if (lower.startsWith("error") || lower.startsWith("sorry")) score -= 0.20;

    // ── Code-specific penalties ──────────────────────────────────────────────
    if (["CODE_GEN","CODE_FIX","REFACTOR","QA","DEBUG"].includes(taskType)) {
      const hasCodeBlock = output.includes("```") || output.includes("    ") || output.includes("\t");
      if (!hasCodeBlock && output.length < 300)               score -= 0.15;
      if (lower.includes("todo") || lower.includes("fixme"))  score -= 0.15;
      if (output.trim() === "pass" || output.trim() === "...") score -= 0.40;
      if (output.includes("NotImplementedError"))              score -= 0.30;
      if ((output.match(/def |class |function |const |let |var /g) ?? []).length === 0
          && output.length < 200)                             score -= 0.10;
    }

    // ── Analytics / Architecture boost ──────────────────────────────────────
    if (["ANALYTICS","ARCHITECTURE"].includes(taskType)) {
      if (output.length > 500) score = Math.min(score + 0.05, 1.0);
    }

    // ── Quality bonuses ──────────────────────────────────────────────────────
    if (output.length > 1000) score = Math.min(score + 0.05, 1.0);

    return Math.max(0.0, Math.min(1.0, score));
  }
}
