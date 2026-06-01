import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';

import { keys } from '@shared/lib/react-query/keys';
import { Card, CardContent, CardHeader, CardTitle } from '@shared/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@shared/ui/tabs';
import { PlanningMatrix, cellKey, type CellSaveState } from '@widgets/planning-matrices';
import { useServices } from '@entities/service';
import { useProviders } from '@entities/provider';
import { planningApi, type PlanningCellUpsert, type PlanningField } from '@entities/planning-cell';

type CellValues = Omit<PlanningCellUpsert, 'service_id' | 'provider_id'>;
const EMPTY: CellValues = { price: 0, resource: 0, provider_revenue: 0, discount: 0, min_value: 0 };
const DEBOUNCE_MS = 400;

const TABS: { field: PlanningField; label: string }[] = [
  { field: 'price', label: 'Преференційні ціни' },
  { field: 'resource', label: 'Ресурси' },
  { field: 'provider_revenue', label: 'Дохід провайдера' },
  { field: 'discount', label: 'Знижки' },
  { field: 'min_value', label: 'Мін. відносна цінність (s_ij)' },
];

export default function PlanningPage() {
  const { data: services = [] } = useServices();
  const { data: providers = [] } = useProviders();
  const { data: cells, isLoading } = useQuery({
    queryKey: keys.planning.all(),
    queryFn: planningApi.listPlanning,
  });

  const [values, setValues] = useState<Map<string, CellValues>>(new Map());
  const [states, setStates] = useState<Map<string, CellSaveState>>(new Map());
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  useEffect(() => {
    if (!cells) return;
    const next = new Map<string, CellValues>();
    for (const c of cells) {
      next.set(cellKey(c.service_id, c.provider_id), {
        price: c.price, resource: c.resource, provider_revenue: c.provider_revenue,
        discount: c.discount, min_value: c.min_value,
      });
    }
    setValues(next);
  }, [cells]);

  useEffect(() => { const map = timers.current; return () => map.forEach((t) => clearTimeout(t)); }, []);

  const setState = (key: string, state: CellSaveState) =>
    setStates((prev) => new Map(prev).set(key, state));

  const handleChange = (serviceId: string, providerId: string, field: PlanningField, value: number) => {
    const key = cellKey(serviceId, providerId);
    const merged: CellValues = { ...(values.get(key) ?? EMPTY), [field]: value };
    setValues((prev) => new Map(prev).set(key, merged));
    setState(key, 'saving');
    const existing = timers.current.get(key);
    if (existing) clearTimeout(existing);
    const timer = setTimeout(() => {
      void planningApi.upsertCell({ service_id: serviceId, provider_id: providerId, ...merged })
        .then(() => setState(key, 'saved'))
        .catch((e) => { setState(key, 'error'); toast.error(e instanceof Error ? e.message : 'Помилка збереження клітинки'); });
    }, DEBOUNCE_MS);
    timers.current.set(key, timer);
  };

  const getValue = (serviceId: string, providerId: string, field: PlanningField) =>
    values.get(cellKey(serviceId, providerId))?.[field] ?? 0;
  const getState = (serviceId: string, providerId: string): CellSaveState =>
    states.get(cellKey(serviceId, providerId)) ?? 'idle';

  return (
    <Card>
      <CardHeader>
        <CardTitle>Планові дані</CardTitle>
        <p className="text-sm text-muted-foreground">
          Рядки — сервіси, стовпці — провайдери (упорядковані за назвою). Зміни зберігаються автоматично.
        </p>
      </CardHeader>
      <CardContent>
        {isLoading ? <p className="text-muted-foreground">Завантаження…</p> : (
          <Tabs defaultValue="price">
            <TabsList>
              {TABS.map((t) => <TabsTrigger key={t.field} value={t.field}>{t.label}</TabsTrigger>)}
            </TabsList>
            {TABS.map((t) => (
              <TabsContent key={t.field} value={t.field}>
                <PlanningMatrix
                  field={t.field} services={services} providers={providers}
                  getValue={(s, p) => getValue(s, p, t.field)}
                  onChange={(s, p, v) => handleChange(s, p, t.field, v)}
                  getState={getState}
                />
              </TabsContent>
            ))}
          </Tabs>
        )}
      </CardContent>
    </Card>
  );
}
