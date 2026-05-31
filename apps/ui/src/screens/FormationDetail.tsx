import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { toast } from 'sonner';

import {
  exportCsv,
  exportJson,
  getFormation,
  getIterations,
} from '@/api/formations';
import type { FormationDetail as FormationDetailType } from '@/api/types';
import { Badge } from '@/components/ui/badge.tsx';
import { Button } from '@/components/ui/button.tsx';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card.tsx';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible.tsx';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table.tsx';
import IterationChart, { ALGO_COLOR } from '@/components/IterationChart.tsx';
import StatusBadge from '@/components/StatusBadge.tsx';
import { ALGO_LABEL, formatParamValue, orderedParams } from '@/lib/algorithmParams';

const POLL_MS = 1500;

const COMBINED_SOURCE_LABEL: Record<string, string> = {
  subtask_a_improved: 'Покращено з підзадачі ІТ-компанії',
  subtask_b_improved: 'Покращено з підзадачі провайдерів',
};

const fmt = (n: number) => Math.round(n).toLocaleString('uk');

export default function FormationDetail() {
  const { id = '' } = useParams();
  const [paramsOpen, setParamsOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['formation', id],
    queryFn: () => getFormation(id),
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s === 'pending' || s === 'running' ? POLL_MS : false;
    },
  });

  const { data: iterations = [] } = useQuery({
    queryKey: ['formation', id, 'iterations'],
    queryFn: () => getIterations(id),
    enabled: !!data && (data.status === 'completed' || data.status === 'failed'),
  });

  const totalsMemo = useMemo(() => data?.totals, [data]);

  if (isLoading || !data) {
    return <p className="text-muted-foreground">Завантаження…</p>;
  }

  const d: FormationDetailType = data;
  const isCombined = d.algorithm === 'combined';

  const handleExport = async (kind: 'json' | 'csv') => {
    try {
      if (kind === 'json') await exportJson(id);
      else await exportCsv(id);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Помилка експорту');
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>{d.name}</CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              {ALGO_LABEL[d.algorithm]} · <StatusBadge status={d.status} />
            </p>
            {isCombined && d.combined_source && (
              <Badge variant="secondary" className="mt-2">
                {COMBINED_SOURCE_LABEL[d.combined_source] ?? d.combined_source}
              </Badge>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => handleExport('json')}>Експорт JSON</Button>
            <Button variant="outline" onClick={() => handleExport('csv')}>Експорт CSV</Button>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {d.error && <p className="text-destructive text-sm">{d.error}</p>}

          {isCombined ? (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <Stat label="Дохід IT-компанії (F_IT)" value={d.value != null ? fmt(d.value) : '—'} />
              <Stat label="Дохід провайдерів (F_prov)" value={d.provider_value != null ? fmt(d.provider_value) : '—'} />
              <Stat label="Сумарна вигода (F_IT + F_prov)" value={d.combined_benefit != null ? fmt(d.combined_benefit) : '—'} />
              <Stat label="Викор. ресурс" value={totalsMemo ? fmt(totalsMemo.total_resource_used) : '—'} />
              <Stat label="Провайдерів" value={String(totalsMemo?.provider_count ?? 0)} />
              <Stat label="Сервісів" value={String(totalsMemo?.service_count ?? 0)} />
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Stat label="Дохід IT-компанії (F)" value={d.value != null ? fmt(d.value) : '—'} />
              <Stat label="Викор. ресурс" value={totalsMemo ? fmt(totalsMemo.total_resource_used) : '—'} />
              <Stat label="Провайдерів" value={String(totalsMemo?.provider_count ?? 0)} />
              <Stat label="Сервісів" value={String(totalsMemo?.service_count ?? 0)} />
            </div>
          )}
          <div className="text-sm text-muted-foreground">Загальний ресурс T = {fmt(d.b_total)}</div>
        </CardContent>
      </Card>

      <Collapsible open={paramsOpen} onOpenChange={setParamsOpen}>
        <Card>
          <CardHeader>
            <CollapsibleTrigger className="flex items-center gap-2 text-sm font-medium">
              Параметри алгоритму
              <span className="text-muted-foreground">· T = {fmt(d.b_total)}</span>
              <span className="ml-auto text-muted-foreground">{paramsOpen ? '▾' : '▸'}</span>
            </CollapsibleTrigger>
          </CardHeader>
          <CollapsibleContent>
            <CardContent>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm max-w-md">
                <dt className="text-muted-foreground">T (загальний ресурс)</dt>
                <dd>{fmt(d.b_total)}</dd>
                {orderedParams(d.algorithm, d.params).map((row) => (
                  <FragmentRow key={row.key} label={row.label} value={formatParamValue(row.value)} />
                ))}
              </dl>
            </CardContent>
          </CollapsibleContent>
        </Card>
      </Collapsible>

      {iterations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Збіжність</CardTitle>
          </CardHeader>
          <CardContent>
            <IterationChart
              series={[{
                name: ALGO_LABEL[d.algorithm],
                color: ALGO_COLOR[d.algorithm],
                data: iterations.map((it) => ({ iteration: it.iteration, value: it.best_value })),
              }]}
            />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Призначення</CardTitle>
        </CardHeader>
        <CardContent>
          {d.assignments.length === 0 ? (
            <p className="text-muted-foreground">Немає призначень.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Сервіс</TableHead>
                  <TableHead>Провайдер</TableHead>
                  <TableHead>Ціна</TableHead>
                  <TableHead>Знижка</TableHead>
                  <TableHead>Дохід</TableHead>
                  <TableHead>Ресурс</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {d.assignments.map((a, i) => {
                  // For combined runs the negotiated discount is final_discount;
                  // mark when it differs from the planning r_max.
                  const negotiated = a.final_discount;
                  const shown = negotiated ?? a.discount;
                  const differs =
                    negotiated != null && Math.abs(negotiated - a.discount) > 1e-9;
                  return (
                    <TableRow key={i}>
                      <TableCell className="font-medium">
                        {a.service_name}
                        {a.group_name && (
                          <Badge variant="secondary" className="ml-2">{a.group_name}</Badge>
                        )}
                      </TableCell>
                      <TableCell>{a.provider_name}</TableCell>
                      <TableCell>{fmt(a.price)}</TableCell>
                      <TableCell>
                        {shown}
                        {differs && (
                          <span
                            className="ml-1 text-xs text-muted-foreground"
                            title={`узгоджено: ${a.final_discount} (межа ${a.discount})`}
                          >
                            {negotiated! < a.discount ? '↓' : '↑'}
                          </span>
                        )}
                      </TableCell>
                      <TableCell>{fmt(a.effective_revenue)}</TableCell>
                      <TableCell>{fmt(a.resource_used)}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-lg font-semibold">{value}</span>
    </div>
  );
}

function FragmentRow({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd>{value}</dd>
    </>
  );
}
