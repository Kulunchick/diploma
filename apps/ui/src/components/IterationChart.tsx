import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type { FormationAlgorithm } from '@/api/types';

/** Line colour per algorithm (matches the Solve.tsx convergence palette). */
export const ALGO_COLOR: Record<FormationAlgorithm, string> = {
  ant_colony: '#0f172a',
  probabilistic: '#2563eb',
};

/** Distinct colours for comparing several scenarios on one chart. */
export const SERIES_PALETTE = ['#2563eb', '#16a34a', '#dc2626', '#9333ea', '#ea580c', '#0891b2'];

export interface IterationSeries {
  name: string;
  color: string;
  data: { iteration: number; value: number }[];
}

const fmt = (v: number) => Math.round(v).toLocaleString('uk');

export default function IterationChart({
  series,
  showLegend = false,
}: {
  series: IterationSeries[];
  showLegend?: boolean;
}) {
  // Merge into rows keyed by iteration; missing keys leave a line ending where
  // that series' data ends (no padding / interpolation across different Kmax).
  const iterations = [...new Set(series.flatMap((s) => s.data.map((d) => d.iteration)))].sort(
    (a, b) => a - b,
  );
  const lookup = series.map((s) => new Map(s.data.map((d) => [d.iteration, d.value])));
  const rows = iterations.map((iteration) => {
    const row: Record<string, number> = { iteration };
    series.forEach((s, i) => {
      const v = lookup[i].get(iteration);
      if (v !== undefined) row[s.name] = v;
    });
    return row;
  });

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={rows} margin={{ left: 12, right: 12 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="iteration" tickMargin={8} />
        <YAxis width={80} domain={['auto', 'auto']} tickFormatter={fmt} />
        <Tooltip formatter={(v: number) => fmt(v)} labelFormatter={(l) => `Ітерація ${l}`} />
        {showLegend && <Legend />}
        {series.map((s) => (
          <Line
            key={s.name}
            type="monotone"
            dataKey={s.name}
            stroke={s.color}
            dot={false}
            connectNulls={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
