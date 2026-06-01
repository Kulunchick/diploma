import type { FormationTotals } from '@entities/formation';

const fmt = (n: number) => Math.round(n).toLocaleString('uk');
const fmtOrDash = (n: number | null) => (n != null ? fmt(n) : '—');
const sumOrNull = (a: number | null, b: number | null) =>
  a != null && b != null ? a + b : null;

interface Props {
  value: number | null;
  provider_value: number | null;
  provider_profit: number | null;
  totals: FormationTotals | undefined;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-lg font-semibold">{value}</span>
    </div>
  );
}

export default function FormationTotalsCards({ value, provider_value, provider_profit, totals }: Props) {
  // Single grid for all metric cards: vertical columns stay aligned and gaps
  // are uniform by construction as cards wrap. Fewer columns on narrow viewports.
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
      <Stat label="Дохід IT-компанії (F_IT)" value={fmtOrDash(value)} />
      <Stat label="Дохід провайдерів (F_prov)" value={fmtOrDash(provider_value)} />
      <Stat label="Сумарна вигода (F_IT + F_prov)" value={fmtOrDash(sumOrNull(value, provider_value))} />
      <Stat label="Прибуток провайдерів" value={fmtOrDash(provider_profit)} />
      <Stat label="Створена цінність (F_IT + прибуток пров.)" value={fmtOrDash(sumOrNull(value, provider_profit))} />
      <Stat label="Викор. ресурс" value={totals ? fmt(totals.total_resource_used) : '—'} />
      <Stat label="Провайдерів" value={String(totals?.provider_count ?? 0)} />
      <Stat label="Сервісів" value={String(totals?.service_count ?? 0)} />
    </div>
  );
}
