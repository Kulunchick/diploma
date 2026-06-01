import { Badge } from '@shared/ui/badge';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@shared/ui/table';
import type { FormationAssignment } from '@entities/formation';

const fmt = (n: number) => Math.round(n).toLocaleString('uk');
const fmtOrDash = (n: number | null) => (n != null ? fmt(n) : '—');

export default function AssignmentsTable({ assignments }: { assignments: FormationAssignment[] }) {
  if (assignments.length === 0) {
    return <p className="text-muted-foreground">Немає призначень.</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Сервіс</TableHead>
          <TableHead>Провайдер</TableHead>
          <TableHead>Ціна</TableHead>
          <TableHead>Знижка</TableHead>
          <TableHead>Дохід</TableHead>
          <TableHead>Дохід пров.</TableHead>
          <TableHead>Прибуток пров.</TableHead>
          <TableHead>Ресурс</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {assignments.map((a, i) => {
          const negotiated = a.final_discount;
          const shown = negotiated ?? a.discount;
          const differs = negotiated != null && Math.abs(negotiated - a.discount) > 1e-9;
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
              <TableCell>{fmtOrDash(a.provider_revenue_pair)}</TableCell>
              <TableCell>{fmtOrDash(a.provider_profit_pair)}</TableCell>
              <TableCell>{fmt(a.resource_used)}</TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
