import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@shared/ui/table';
import { orderedParams, formatParamValue } from '@shared/lib/algorithmParams';
import type { CompareScenario } from '@entities/formation';

const fmt = (n: number) => Math.round(n).toLocaleString('uk');

export default function ComparisonParamsTable({ scenarios }: { scenarios: CompareScenario[] }) {
  // Per-scenario param map (label → formatted value), union of labels in first-seen order.
  const paramMaps = scenarios.map((s) => {
    const m = new Map<string, string>();
    for (const row of orderedParams(s.algorithm, s.params)) {
      m.set(row.label, formatParamValue(row.value));
    }
    return m;
  });
  const paramLabels: string[] = [];
  const seen = new Set<string>();
  for (const m of paramMaps) {
    for (const label of m.keys()) {
      if (!seen.has(label)) { seen.add(label); paramLabels.push(label); }
    }
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Параметр</TableHead>
          {scenarios.map((s) => <TableHead key={s.id}>{s.name}</TableHead>)}
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell className="text-muted-foreground">T (загальний ресурс)</TableCell>
          {scenarios.map((s) => <TableCell key={s.id}>{fmt(s.b_total)}</TableCell>)}
        </TableRow>
        {paramLabels.map((label) => (
          <TableRow key={label}>
            <TableCell className="text-muted-foreground">{label}</TableCell>
            {paramMaps.map((m, i) => (
              <TableCell key={scenarios[i].id}>
                {m.has(label) ? m.get(label) : <span className="text-muted-foreground">—</span>}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
