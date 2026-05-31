import { Check, Loader2, X } from 'lucide-react';

import type { PlanningField, Provider, Service } from '@/api/types';
import { Input } from '@/components/ui/input.tsx';

export type CellSaveState = 'idle' | 'saving' | 'saved' | 'error';

export function cellKey(serviceId: string, providerId: string): string {
  return `${serviceId}:${providerId}`;
}

const FIELD_STEP: Record<PlanningField, { step: number; min: number; max?: number }> = {
  price: { step: 1, min: 0 },
  resource: { step: 1, min: 0 },
  provider_revenue: { step: 1, min: 0 },
  discount: { step: 0.05, min: 0, max: 0.99 },
};

interface Props {
  field: PlanningField;
  services: Service[];
  providers: Provider[];
  getValue: (serviceId: string, providerId: string) => number;
  onChange: (serviceId: string, providerId: string, value: number) => void;
  getState: (serviceId: string, providerId: string) => CellSaveState;
}

function Indicator({ state }: { state: CellSaveState }) {
  if (state === 'saving') return <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />;
  if (state === 'saved') return <Check className="h-3 w-3 text-green-600" />;
  if (state === 'error') return <X className="h-3 w-3 text-destructive" />;
  return <span className="inline-block h-3 w-3" />;
}

export default function PlanningMatrix({
  field,
  services,
  providers,
  getValue,
  onChange,
  getState,
}: Props) {
  const cfg = FIELD_STEP[field];

  if (services.length === 0 || providers.length === 0) {
    return (
      <p className="text-muted-foreground">
        Потрібні хоча б один сервіс і один провайдер.
      </p>
    );
  }

  return (
    <div className="relative w-full overflow-auto">
      <table className="w-full caption-bottom text-sm border-collapse">
        <thead>
          <tr className="border-b">
            <th className="h-10 px-2 text-left font-medium text-muted-foreground sticky left-0 bg-background">
              Сервіс \ Провайдер
            </th>
            {providers.map((p) => (
              <th key={p.id} className="h-10 px-2 text-left font-medium text-muted-foreground">
                {p.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {services.map((s) => (
            <tr key={s.id} className="border-b">
              <td className="p-2 font-medium sticky left-0 bg-background">{s.name}</td>
              {providers.map((p) => (
                <td key={p.id} className="p-2">
                  <div className="flex items-center gap-1">
                    <Input
                      type="number"
                      className="w-28"
                      min={cfg.min}
                      max={cfg.max}
                      step={cfg.step}
                      value={getValue(s.id, p.id)}
                      onChange={(e) => onChange(s.id, p.id, Number(e.target.value))}
                    />
                    <Indicator state={getState(s.id, p.id)} />
                  </div>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
