import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';

import { listPlanning, upsertCell } from '@/api/planning';
import { listProviders } from '@/api/providers';
import { listServices } from '@/api/services';
import type { PlanningCellUpsert, PlanningField } from '@/api/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card.tsx';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.tsx';
import PlanningMatrix, {
  cellKey,
  type CellSaveState,
} from '@/components/PlanningMatrix.tsx';

type CellValues = Omit<PlanningCellUpsert, 'service_id' | 'provider_id'>;

const EMPTY: CellValues = {
  price: 0,
  resource: 0,
  provider_revenue: 0,
  discount: 0,
  min_value: 0,
};

const TABS: { field: PlanningField; label: string }[] = [
  { field: 'price', label: 'Преференційні ціни' },
  { field: 'resource', label: 'Ресурси' },
  { field: 'provider_revenue', label: 'Дохід провайдера' },
  { field: 'discount', label: 'Знижки' },
  { field: 'min_value', label: 'Мін. відносна цінність (s_ij)' },
];

const DEBOUNCE_MS = 400;

export default function Planning() {
  const { data: services = [] } = useQuery({ queryKey: ['services'], queryFn: listServices });
  const { data: providers = [] } = useQuery({ queryKey: ['providers'], queryFn: listProviders });
  const { data: cells, isLoading } = useQuery({ queryKey: ['planning'], queryFn: listPlanning });

  // Local cell store keyed by "serviceId:providerId" — holds all fields
  // so a single-field edit can PUT the whole cell.
  const [values, setValues] = useState<Map<string, CellValues>>(new Map());
  const [states, setStates] = useState<Map<string, CellSaveState>>(new Map());
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  useEffect(() => {
    if (!cells) return;
    const next = new Map<string, CellValues>();
    for (const c of cells) {
      next.set(cellKey(c.service_id, c.provider_id), {
        price: c.price,
        resource: c.resource,
        provider_revenue: c.provider_revenue,
        discount: c.discount,
        min_value: c.min_value,
      });
    }
    setValues(next);
  }, [cells]);

  useEffect(() => {
    const map = timers.current;
    return () => map.forEach((t) => clearTimeout(t));
  }, []);

  const setState = (key: string, state: CellSaveState) =>
    setStates((prev) => new Map(prev).set(key, state));

  const handleChange = (
    serviceId: string,
    providerId: string,
    field: PlanningField,
    value: number,
  ) => {
    const key = cellKey(serviceId, providerId);
    const merged: CellValues = { ...(values.get(key) ?? EMPTY), [field]: value };

    // Optimistic local update.
    setValues((prev) => new Map(prev).set(key, merged));
    setState(key, 'saving');

    const existing = timers.current.get(key);
    if (existing) clearTimeout(existing);
    const timer = setTimeout(() => {
      void upsertCell({ service_id: serviceId, provider_id: providerId, ...merged })
        .then(() => setState(key, 'saved'))
        .catch((e) => {
          setState(key, 'error');
          toast.error(e instanceof Error ? e.message : 'Помилка збереження клітинки');
        });
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
          Рядки — сервіси, стовпці — провайдери (упорядковані за назвою). Зміни зберігаються
          автоматично.
        </p>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-muted-foreground">Завантаження…</p>
        ) : (
          <Tabs defaultValue="price">
            <TabsList>
              {TABS.map((t) => (
                <TabsTrigger key={t.field} value={t.field}>
                  {t.label}
                </TabsTrigger>
              ))}
            </TabsList>
            {TABS.map((t) => (
              <TabsContent key={t.field} value={t.field}>
                <PlanningMatrix
                  field={t.field}
                  services={services}
                  providers={providers}
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
