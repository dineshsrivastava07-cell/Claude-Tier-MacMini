import type { TierName } from "../types.js";

export const FALLBACK_CHAINS: Record<TierName, TierName[]> = {
  "T1-LOCAL": ["T1-LOCAL", "T1-CLOUD", "T2-FLASH", "T3"],
  "T1-CLOUD": ["T1-CLOUD", "T2-FLASH", "T3"],
  "T2-PRO":   ["T2-PRO",  "T2-FLASH", "T3"],
  "T2-FLASH": ["T2-FLASH","T2-PRO",   "T3"],
  "T2-LITE":  ["T2-LITE", "T2-FLASH", "T1-CLOUD"],
  "T3":       ["T3"],
};

export function buildExecutionPlan(recommended: TierName, override?: TierName): TierName[] {
  if (override) return [override];
  return FALLBACK_CHAINS[recommended];
}
