import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';

import { keys } from '@shared/lib/react-query/keys';
import { Card, CardContent, CardHeader, CardTitle } from '@shared/ui/card';
import { ComparisonMetricsTable, ComparisonParamsTable } from '@widgets/comparison-table';
import { compareFormations } from '@entities/formation/api';

export default function FormationsComparePage() {
  const [searchParams] = useSearchParams();
  const ids = [
    ...searchParams.getAll('id'),
    ...(searchParams.get('ids')?.split(',').filter(Boolean) ?? []),
  ];

  const { data, isLoading } = useQuery({
    queryKey: keys.compare.byIds(ids),
    queryFn: () => compareFormations(ids),
    enabled: ids.length > 0,
  });

  if (ids.length === 0) return <p className="text-muted-foreground">Не вибрано сценаріїв для порівняння.</p>;
  if (isLoading || !data) return <p className="text-muted-foreground">Завантаження…</p>;

  const { scenarios } = data;

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader><CardTitle>Порівняння сценаріїв</CardTitle></CardHeader>
        <CardContent><ComparisonMetricsTable scenarios={scenarios} /></CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Параметри алгоритму</CardTitle></CardHeader>
        <CardContent><ComparisonParamsTable scenarios={scenarios} /></CardContent>
      </Card>
    </div>
  );
}
