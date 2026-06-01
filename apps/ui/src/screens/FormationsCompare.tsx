import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';

import { compareFormations } from '@/api/formations';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card.tsx';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table.tsx';
import { ALGO_LABEL, formatParamValue, orderedParams } from '@/lib/algorithmParams';
import { cn } from '@/lib/utils';
import type { CompareScenario } from '@/api/types';

const fmt = (n: number) => Math.round(n).toLocaleString('uk');

export default function FormationsCompare() {
  const [searchParams] = useSearchParams();
  // Accept both ?id=a&id=b and ?ids=a,b
  const ids = [
    ...searchParams.getAll('id'),
    ...(searchParams.get('ids')?.split(',').filter(Boolean) ?? []),
  ];

  const { data, isLoading } = useQuery({
    queryKey: ['compare', ids],
    queryFn: () => compareFormations(ids),
    enabled: ids.length > 0,
  });

  if (ids.length === 0) {
    return <p className="text-muted-foreground">Не вибрано сценаріїв для порівняння.</p>;
  }
  if (isLoading || !data) {
    return <p className="text-muted-foreground">Завантаження…</p>;
  }

  const scenarios = data.scenarios;

  // Per-scenario param map (label → formatted value), and the union of labels
  // across all scenarios in first-seen order (combined rows appear automatically).
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
      if (!seen.has(label)) {
        seen.add(label);
        paramLabels.push(label);
      }
    }
  }

  // Highlight the max cell(s) in a "higher is better" numeric row.
  const maxOf = (vals: (number | null)[]): number | null => {
    const present = vals.filter((v): v is number => v != null);
    return present.length ? Math.max(...present) : null;
  };

  const valueRow = (
    label: string,
    pick: (s: CompareScenario) => number | null,
    highlight = true,
  ) => {
    const vals = scenarios.map(pick);
    const max = highlight ? maxOf(vals) : null;
    return (
      <TableRow>
        <TableCell className="text-muted-foreground">{label}</TableCell>
        {scenarios.map((s, i) => {
          const v = vals[i];
          const isWinner = highlight && v != null && max != null && v === max;
          return (
            <TableCell key={s.id} className={cn(isWinner && 'bg-emerald-50 font-medium')}>
              {v != null ? fmt(v) : '—'}
            </TableCell>
          );
        })}
      </TableRow>
    );
  };

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Порівняння сценаріїв</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Показник</TableHead>
                {scenarios.map((s) => (
                  <TableHead key={s.id}>{s.name}</TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell className="text-muted-foreground">Алгоритм</TableCell>
                {scenarios.map((s) => (
                  <TableCell key={s.id}>{ALGO_LABEL[s.algorithm]}</TableCell>
                ))}
              </TableRow>
              {valueRow('Дохід IT-компанії (F_IT)', (s) => s.value)}
              {valueRow('Дохід провайдерів (F_prov)', (s) => s.provider_value)}
              {valueRow('Прибуток провайдерів', (s) => s.provider_profit)}
              {valueRow('Створена цінність (F_IT + прибуток пров.)', (s) => s.created_value)}
              {valueRow('Сумарна вигода (F_IT + F_prov)', (s) => s.combined_benefit)}
              {valueRow('Викор. ресурс', (s) => s.total_resource_used, false)}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Параметри алгоритму</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Параметр</TableHead>
                {scenarios.map((s) => (
                  <TableHead key={s.id}>{s.name}</TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell className="text-muted-foreground">T (загальний ресурс)</TableCell>
                {scenarios.map((s) => (
                  <TableCell key={s.id}>{fmt(s.b_total)}</TableCell>
                ))}
              </TableRow>
              {paramLabels.map((label) => (
                <TableRow key={label}>
                  <TableCell className="text-muted-foreground">{label}</TableCell>
                  {paramMaps.map((m, i) => (
                    <TableCell key={scenarios[i].id}>
                      {m.has(label) ? (
                        m.get(label)
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
