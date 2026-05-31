import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';

import {
  exportCsv,
  exportJson,
  getFormation,
  listFormations,
} from '@/api/formations';
import type { FormationAssignment } from '@/api/types';
import { Button } from '@/components/ui/button.tsx';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card.tsx';
import { Checkbox } from '@/components/ui/checkbox.tsx';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.tsx';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table.tsx';
import StatusBadge from '@/components/StatusBadge.tsx';

const ALGO_LABEL: Record<string, string> = {
  probabilistic: 'Ймовірнісно-жадібний',
  ant_colony: 'Мурашиних колоній',
};

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}

export default function FormationDetail() {
  const { id = '' } = useParams();
  const navigate = useNavigate();

  const { data, isLoading } = useQuery({
    queryKey: ['formation', id],
    queryFn: () => getFormation(id),
    enabled: !!id,
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s === 'pending' || s === 'running' ? 1500 : false;
    },
  });

  const { data: allFormations = [] } = useQuery({ queryKey: ['formations'], queryFn: listFormations });

  const [compareOpen, setCompareOpen] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  // Group assignments by provider for display.
  const grouped = useMemo(() => {
    const map = new Map<string, FormationAssignment[]>();
    for (const a of data?.assignments ?? []) {
      const arr = map.get(a.provider_name) ?? [];
      arr.push(a);
      map.set(a.provider_name, arr);
    }
    return [...map.entries()];
  }, [data]);

  const download = (fn: (id: string) => Promise<void>) =>
    fn(id).catch((e) => toast.error(e instanceof Error ? e.message : 'Помилка експорту'));

  if (isLoading || !data) {
    return <p className="p-4 text-muted-foreground">Завантаження…</p>;
  }

  const fmt = (n: number) => Math.round(n).toLocaleString('uk');

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader className="flex flex-row items-start justify-between">
          <div className="flex flex-col gap-1">
            <CardTitle className="flex items-center gap-3">
              {data.name}
              <StatusBadge status={data.status} />
            </CardTitle>
            <span className="text-sm text-muted-foreground">
              Алгоритм: {ALGO_LABEL[data.algorithm] ?? data.algorithm} · T = {fmt(data.b_total)}
            </span>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => download(exportJson)}>
              Експорт JSON
            </Button>
            <Button variant="outline" onClick={() => download(exportCsv)}>
              Експорт CSV
            </Button>
            <Button
              onClick={() => {
                setSelected(new Set());
                setCompareOpen(true);
              }}
            >
              Порівняти зі сценарієм…
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {data.status === 'failed' && (
            <p className="text-destructive mb-4">Помилка: {data.error ?? 'невідома'}</p>
          )}
          {data.status === 'pending' || data.status === 'running' ? (
            <p className="text-muted-foreground">Триває обчислення…</p>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <Stat label="Дохід IT-компанії (F)" value={data.value != null ? fmt(data.value) : '—'} />
              <Stat label="Загальний дохід" value={fmt(data.totals.total_revenue)} />
              <Stat label="Використано ресурсу" value={fmt(data.totals.total_resource_used)} />
              <Stat label="Провайдерів" value={String(data.totals.provider_count)} />
              <Stat label="Сервісів" value={String(data.totals.service_count)} />
            </div>
          )}
        </CardContent>
      </Card>

      {data.assignments.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Призначення за провайдерами</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-6">
            {grouped.map(([provider, rows]) => (
              <div key={provider}>
                <h3 className="font-medium mb-2">{provider}</h3>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Сервіс</TableHead>
                      <TableHead>Ціна</TableHead>
                      <TableHead>Знижка</TableHead>
                      <TableHead>Дохід</TableHead>
                      <TableHead>Ресурс</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((a) => (
                      <TableRow key={a.service_id}>
                        <TableCell className="font-medium">{a.service_name}</TableCell>
                        <TableCell>{fmt(a.price)}</TableCell>
                        <TableCell>{a.discount}</TableCell>
                        <TableCell>{fmt(a.effective_revenue)}</TableCell>
                        <TableCell>{fmt(a.resource_used)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Dialog open={compareOpen} onOpenChange={setCompareOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Порівняти зі сценарієм</DialogTitle>
          </DialogHeader>
          <div className="max-h-72 overflow-auto flex flex-col gap-2">
            {allFormations.filter((f) => f.id !== id).length === 0 ? (
              <span className="text-sm text-muted-foreground">Немає інших сценаріїв.</span>
            ) : (
              allFormations
                .filter((f) => f.id !== id)
                .map((f) => (
                  <label key={f.id} className="flex items-center gap-2 cursor-pointer">
                    <Checkbox
                      checked={selected.has(f.id)}
                      onCheckedChange={() =>
                        setSelected((prev) => {
                          const next = new Set(prev);
                          if (next.has(f.id)) next.delete(f.id);
                          else next.add(f.id);
                          return next;
                        })
                      }
                    />
                    <span className="text-sm">{f.name}</span>
                  </label>
                ))
            )}
          </div>
          <DialogFooter>
            <Button
              disabled={selected.size === 0}
              onClick={() => {
                const ids = [id, ...selected].join(',');
                navigate(`/formations/compare?ids=${ids}`);
              }}
            >
              Порівняти
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
