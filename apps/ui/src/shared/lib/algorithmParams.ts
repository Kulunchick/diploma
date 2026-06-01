/**
 * Human-readable labels + ordering for the algorithm parameter sets stored on a
 * formation scenario (`params`). Keys match what the API persists
 * (AntColony/Probabilistic/CombinedParameters). Unknown keys fall back to the
 * raw key so future params still render.
 */
import type { FormationAlgorithm } from '@shared/types/formation';

export const ALGO_LABEL: Record<FormationAlgorithm, string> = {
  probabilistic: 'Ймовірнісно-жадібний',
  ant_colony: 'Мурашиних колоній',
  combined: 'Комбінований метод',
};

const PARAM_LABELS: Record<FormationAlgorithm, Record<string, string>> = {
  probabilistic: {
    Kmax: 'K_max',
  },
  ant_colony: {
    Kmax: 'K_max',
    num_ants: 'L (кількість мурашок)',
    alpha: 'α (важливість феромонного сліду)',
    beta: 'β (важливість цінності пари)',
    p: 'ρ (коефіцієнт випаровування)',
    tau: 'τ₀ (початковий рівень феромону)',
  },
  combined: {
    kmax_subproblem: 'K_max підзадач',
    discount_step: 'Крок знижки',
    ignore_discounts: 'Ігнорувати межу знижок',
    local_search_restarts: 'Додаткові рестарти',
  },
};

// Stable display order per algorithm; keys not listed here are appended after.
const PARAM_ORDER: Record<FormationAlgorithm, string[]> = {
  probabilistic: ['Kmax'],
  ant_colony: ['Kmax', 'num_ants', 'alpha', 'beta', 'p', 'tau'],
  combined: ['kmax_subproblem', 'discount_step', 'ignore_discounts', 'local_search_restarts'],
};

export function paramLabel(algorithm: FormationAlgorithm, key: string): string {
  return PARAM_LABELS[algorithm]?.[key] ?? key;
}

/** Booleans → Так/Ні; integers as-is; floats to ≤2 decimals, trailing zeros stripped. */
export function formatParamValue(value: number | boolean): string {
  if (typeof value === 'boolean') return value ? 'Так' : 'Ні';
  if (Number.isInteger(value)) return String(value);
  return String(Number(value.toFixed(2)));
}

export interface ParamRow {
  key: string;
  label: string;
  value: number | boolean;
}

/** Ordered (label, value) rows for a scenario's params: known keys first in the
 * canonical order, then any unknown keys (raw label) for forward compatibility. */
export function orderedParams(
  algorithm: FormationAlgorithm,
  params: Record<string, number | boolean>,
): ParamRow[] {
  const known = PARAM_ORDER[algorithm] ?? [];
  const seen = new Set<string>();
  const rows: ParamRow[] = [];
  for (const key of known) {
    if (key in params) {
      rows.push({ key, label: paramLabel(algorithm, key), value: params[key] });
      seen.add(key);
    }
  }
  for (const key of Object.keys(params)) {
    if (!seen.has(key)) rows.push({ key, label: key, value: params[key] });
  }
  return rows;
}
