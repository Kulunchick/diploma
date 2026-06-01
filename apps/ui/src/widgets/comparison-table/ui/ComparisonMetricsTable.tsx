import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@shared/ui/table';
import { ALGO_LABEL } from '@shared/lib/algorithmParams';
import { cn } from '@shared/lib/utils';
import type { CompareScenario } from '@entities/formation';

const fmt = (n: number) => Math.round(n).toLocaleString('uk');

const maxOf = (vals: (number | null)[]): number | null => {
  const present = vals.filter((v): v is number => v != null);
  return present.length ? Math.max(...present) : null;
};

function valueRow(
  scenarios: CompareScenario[],
  label: string,
  pick: (s: CompareScenario) => number | null,
  highlight = true,
) {
  const vals = scenarios.map(pick);
  const max = highlight ? maxOf(vals) : null;
  return (
    <TableRow key={label}>
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
}

export default function ComparisonMetricsTable({ scenarios }: { scenarios: CompareScenario[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Показник</TableHead>
          {scenarios.map((s) => <TableHead key={s.id}>{s.name}</TableHead>)}
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell className="text-muted-foreground">Алгоритм</TableCell>
          {scenarios.map((s) => <TableCell key={s.id}>{ALGO_LABEL[s.algorithm]}</TableCell>)}
        </TableRow>
        {valueRow(scenarios, 'Дохід IT-компанії (F_IT)', (s) => s.value)}
        {valueRow(scenarios, 'Дохід провайдерів (F_prov)', (s) => s.provider_value)}
        {valueRow(scenarios, 'Прибуток провайдерів', (s) => s.provider_profit)}
        {valueRow(scenarios, 'Створена цінність (F_IT + прибуток пров.)', (s) => s.created_value)}
        {valueRow(scenarios, 'Сумарна вигода (F_IT + F_prov)', (s) => s.combined_benefit)}
        {valueRow(scenarios, 'Викор. ресурс', (s) => s.total_resource_used, false)}
      </TableBody>
    </Table>
  );
}
