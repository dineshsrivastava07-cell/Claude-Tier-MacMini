import { z } from "zod";

// ── Enumerations ─────────────────────────────────────────────────────────────

export const TaskComplexity = z.enum(["SIMPLE", "MODERATE", "COMPLEX", "EPIC"]);
export type  TaskComplexity = z.infer<typeof TaskComplexity>;

export const TaskType = z.enum([
  "CODE_GEN", "CODE_FIX", "ARCHITECTURE", "ANALYTICS",
  "REFACTOR", "QA", "DEBUG", "INTEGRATION", "FULLSTACK",
]);
export type TaskType = z.infer<typeof TaskType>;

export const TierName = z.enum([
  "T1-LOCAL", "T1-CLOUD", "T2-PRO", "T2-FLASH", "T2-LITE", "T3",
]);
export type TierName = z.infer<typeof TierName>;

// ── Classification ───────────────────────────────────────────────────────────

export interface ClassificationResult {
  complexity:       TaskComplexity;
  taskType:         TaskType;
  recommendedTier:  TierName;
  confidence:       number;   // 0.0 – 1.0
  reasoning:        string;
}

// ── Routing ──────────────────────────────────────────────────────────────────

export interface RouteRequest {
  prompt:            string;
  context?:          string;
  taskType?:         string;
  overrideTier?:     TierName;
  qualityThreshold?: number;
  options?: {
    temperature?: number;
    maxTokens?:   number;
    timeoutMs?:   number;
    seed?:        number;
  };
}

export interface RoutingDecision {
  selectedTier:        TierName;
  model:               string;
  taskType:            TaskType;
  complexity:          TaskComplexity;
  reasoning:           string;
  confidence:          number;
  fallbackPath:        TierName[];
  estimatedCost:       "free" | "low" | "medium" | "high";
  estimatedLatencyMs:  number;
}

// ── Execution ────────────────────────────────────────────────────────────────

export interface TierOptions {
  temperature?: number;
  maxTokens?:   number;
  maxContext?:  number;
  timeoutMs?:   number;
  seed?:        number;
  geminiModel?: "gemini-2.5-pro" | "gemini-2.5-flash" | "gemini-2.5-flash-lite";
}

export interface TierResult {
  tier:            TierName;
  model:           string;
  content:         string;
  quality:         number;         // 0.0 – 1.0
  tokensUsed:      number;
  latencyMs:       number;
  fallbackUsed:    boolean;
  fallbackReason?: string;
}

// ── Pipeline ─────────────────────────────────────────────────────────────────

export interface PipelineStage {
  tier:    TierName;
  output:  string;
  quality: number;
}

export interface PipelineResult {
  stages:         PipelineStage[];
  finalOutput:    string;
  tiersUsed:      TierName[];
  totalLatencyMs: number;
  finalReport?:   string;
  summary?:       string;
  fix?:           string;
}

// ── Health ────────────────────────────────────────────────────────────────────

export interface TierHealthStatus {
  tier:      TierName;
  healthy:   boolean;
  model:     string;
  latencyMs: number;
  error?:    string;
}

// ── Metrics ───────────────────────────────────────────────────────────────────

export interface TierMetrics {
  tier:          TierName;
  calls:         number;
  successes:     number;
  errors:        number;
  escalations:   number;
  avgQuality:    number;
  avgLatencyMs:  number;
}

// ── Zod Input Schemas (for MCP tools) ────────────────────────────────────────

export const RouteTaskInput = z.object({
  prompt:            z.string().describe("The task to execute"),
  context:           z.string().optional().describe("Existing code or project context"),
  task_type:         z.enum([
    "CODE_GEN","CODE_FIX","ARCHITECTURE","ANALYTICS",
    "REFACTOR","QA","DEBUG","INTEGRATION","FULLSTACK","AUTO",
  ]).default("AUTO").describe("Task category. AUTO = classifier decides"),
  override_tier:     TierName.optional().describe("Force a specific tier"),
  quality_threshold: z.number().min(0).max(1).default(0.75)
    .describe("Min quality 0–1 before escalating. Default 0.75"),
  temperature:       z.number().min(0).max(2).optional()
    .describe("Model temperature. Default 0.1 for code"),
});

export const HealthCheckInput = z.object({
  tier: z.enum(["ALL","T1-LOCAL","T1-CLOUD","T2","T3"]).default("ALL")
    .describe("Which tier(s) to probe"),
});

export const ExplainInput = z.object({
  prompt:  z.string().describe("Task to classify (no execution)"),
  context: z.string().optional().describe("Optional context for better classification"),
});

export const OverrideInput = z.object({
  tier:       TierName.describe("Tier to execute on directly"),
  prompt:     z.string().describe("Task prompt"),
  context:    z.string().optional(),
  max_tokens: z.number().optional().describe("Max output tokens"),
});

export const T1GenerateInput = z.object({
  prompt:    z.string().describe("Code generation prompt"),
  context:   z.string().optional().describe("Existing code context"),
  language:  z.string().default("python").describe("Target language"),
  use_cloud: z.boolean().default(false).describe("true = qwen3-coder:480b, false = qwen2.5-coder:7b"),
});

export const T2GeminiInput = z.object({
  prompt:  z.string().describe("Task for Gemini"),
  context: z.string().optional(),
  model:   z.enum(["gemini-2.5-pro","gemini-2.5-flash","gemini-2.5-flash-lite"])
             .default("gemini-2.5-pro"),
});

export const T3ClaudeInput = z.object({
  prompt:     z.string().describe("Architecture or EPIC task for Claude"),
  context:    z.string().optional(),
  max_tokens: z.number().default(8192),
});

export const CodeReviewInput = z.object({
  code:     z.string().describe("Full file contents to review"),
  language: z.string().default("typescript"),
  focus:    z.array(z.enum(["security","performance","correctness","style","architecture"]))
              .default(["correctness","security"]),
});

export const DebugChainInput = z.object({
  error_message: z.string().describe("Error or test failure output"),
  code_context:  z.string().describe("Relevant code or stack trace"),
  language:      z.string().default("typescript"),
});

export const FullstackBuildInput = z.object({
  requirements: z.string().describe("Application requirements in detail"),
  stack: z.object({
    language:  z.string().default("typescript"),
    framework: z.string().optional(),
    database:  z.string().optional(),
    auth:      z.string().optional(),
  }).default({}),
});

export const QAPipelineInput = z.object({
  code:     z.string().describe("Code to test"),
  language: z.string().default("typescript"),
  coverage_target: z.number().min(0).max(100).default(80),
});

// ── Errors ────────────────────────────────────────────────────────────────────

export class TierError extends Error {
  constructor(
    public readonly tier: string,
    public readonly statusCode: number,
    message: string,
  ) {
    super(`[${tier}] HTTP ${statusCode}: ${message}`);
    this.name = "TierError";
  }
}
