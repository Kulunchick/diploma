import { useQuery } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { compareFormations, getIterations } from '@/api/formations';
import IterationChart, { SERIES_PALETTE } from '@/components/IterationChart.tsx';
import { Button } from '@/components/ui/button.tsx';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card.tsx';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table.tsx';
import { cn } from '@/lib/utils';
import { ALGO_LABEL, formatParamValue, orderedParams } from '@/lib/algorithmParams';

export default function FormationsCompare() {
  const [params] = useSearchParams();
  const ids = (params.get('ids') ?? '').split(',').filter(Boolean);

  const { data, isLoading, error } = useQuery({
    queryKey: ['compare', ids],
    queryFn: () => compareFormations(ids),
    enabled: ids.length > 0,
  });

  // Convergence history per scenario, fetched in parallel.
  const { data: itersById = {} } = useQuery({
    queryKey: ['compare-iterations', ids],
    queryFn: async () => {
      const results = await Promise.all(ids.map((id) => getIterations(id)));
      return Object.fromEntries(ids.map((id, i) => [id, results[i]]));
    },
    enabled: ids.length > 0,
  });

  if (ids.length === 0) {
    return <p className="p-4 text-muted-foreground">Не вибрано сценаріїв для порівняння.</p>;
  }
  if (isLoading) return <p className="p-4 text-muted-foreground">Завантаження…</p>;
  if (error || !data) {
    return <p className="p-4 text-destructive">Не вдалося завантажити порівняння.</p>;
  }

  const scenarios = data.scenarios;
  const chartData = scenarios.map((s) => ({
    name: s.name,
    Дохід: Math.round(s.total_revenue),
    Ресурс: Math.round(s.total_resource_used),
  }));

  // One convergence line per scenario; scenarios without history are skipped
  // from the chart (but stay in the totals comparison).
  const convergenceSeries = scenarios
    .map((s, i) => ({
      name: s.name,
      color: SERIES_PALETTE[i % SERIES_PALETTE.length],
      data: (itersById[s.id] ?? []).map((it) => ({
        iteration: it.iteration,
        value: it.best_value,
      })),
    }))
    .filter((srs) => srs.data.length > 0);

  // Parameter comparison: per scenario label→value, then the union of labels
  // (first-seen order) as rows. null cell → em-dash.
  const perScenarioParams = scenarios.map((s) => {
    const map = new Map<string, string>();
    for (const r of orderedParams(s.algorithm, s.params)) map.set(r.label, formatParamValue(r.value));
    return map;
  });
  const labelOrder: string[] = [];
  const seenLabels = new Set<string>();
  scenarios.forEach((s) => {
    for (const r of orderedParams(s.algorithm, s.params)) {
      if (!seenLabels.has(r.label)) {
        seenLabels.add(r.label);
        labelOrder.push(r.label);
      }
    }
  });
  const paramRows: { label: string; values: (string | null)[] }[] = [
    { label: 'Алгоритм', values: scenarios.map((s) => ALGO_LABEL[s.algorithm]) },
    { label: 'T (загальний ресурс)', values: scenarios.map((s) => Math.round(s.b_total).toLocaleString('uk')) },
    ...labelOrder.map((label) => ({
      label,
      values: perScenarioParams.map((m) => m.get(label) ?? null),
    })),
  ];
  const rowDiffers = (values: (string | null)[]) =>
    new Set(values.map((v) => v ?? '—')).size > 1;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Порівняння сценаріїв</h2>
        <Button variant="outline" asChild>
          <Link to="/formations">До списку</Link>
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Підсумкові показники</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="relative w-full overflow-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b">
                  <th className="h-10 px-2 text-left font-medium text-muted-foreground">Показник</th>
                  {scenarios.map((s) => (
                    <th key={s.id} className="h-10 px-2 text-left font-medium">
                      {s.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr className="border-b">
                  <td className="p-2 text-muted-foreground">Алгоритм</td>
                  {scenarios.map((s) => (
                    <td key={s.id} className="p-2">
                      {ALGO_LABEL[s.algorithm] ?? s.algorithm}
                    </td>
                  ))}
                </tr>
                <tr className="border-b">
                  <td className="p-2 text-muted-foreground">Дохід IT-компанії (F)</td>
                  {scenarios.map((s) => (
                    <td key={s.id} className="p-2 font-medium">
                      {s.value != null ? Math.round(s.value).toLocaleString('uk') : '—'}
                    </td>
                  ))}
                </tr>
                <tr className="border-b">
                  <td className="p-2 text-muted-foreground">Загальний дохід</td>
                  {scenarios.map((s) => (
                    <td key={s.id} className="p-2">
                      {Math.round(s.total_revenue).toLocaleString('uk')}
                    </td>
                  ))}
                </tr>
                <tr className="border-b">
                  <td className="p-2 text-muted-foreground">Використано ресурсу</td>
                  {scenarios.map((s) => (
                    <td key={s.id} className="p-2">
                      {Math.round(s.total_resource_used).toLocaleString('uk')}
                    </td>
                  ))}
                </tr>
                <tr className="border-b align-top">
                  <td className="p-2 text-muted-foreground">Призначення за провайдерами</td>
                  {scenarios.map((s) => (
                    <td key={s.id} className="p-2">
                      <ul className="list-disc list-inside">
                        {s.per_provider.map((pp) => (
                          <li key={pp.provider_id}>
                            <span className="font-medium">{pp.provider_name}</span> ({pp.assignment_count}):{' '}
                            {pp.services.join(', ')}
                          </li>
                        ))}
                      </ul>
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
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
              {paramRows.map((row) => {
                const differs = rowDiffers(row.values);
                return (
                  <TableRow key={row.label}>
                    <TableCell className="text-muted-foreground">{row.label}</TableCell>
                    {row.values.map((v, i) => (
                      <TableCell
                        key={i}
                        className={cn('font-medium', differs && 'bg-amber-50')}
                      >
                        {v ?? <span className="text-muted-foreground font-normal">—</span>}
                      </TableCell>
                    ))}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {convergenceSeries.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Збіжність алгоритмів</CardTitle>
          </CardHeader>
          <CardContent>
            <IterationChart series={convergenceSeries} showLegend />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Графік порівняння підсумків</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="Дохід" fill="#2563eb" />
              <Bar dataKey="Ресурс" fill="#16a34a" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}
