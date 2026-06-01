import { useParams } from 'react-router-dom';
import { toast } from 'sonner';

import { ALGO_LABEL } from '@shared/lib/algorithmParams';
import { Badge } from '@shared/ui/badge';
import { Button } from '@shared/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@shared/ui/card';
import { AlgorithmParamsView } from '@widgets/algorithm-params-view';
import { AssignmentsTable } from '@widgets/assignments-table';
import { IterationChart, ALGO_COLOR } from '@widgets/convergence-chart';
import { FormationTotalsCards } from '@widgets/formation-totals-cards';
import { CompareScenarioDialog } from '@features/formation-compare-launch';
import { useFormation, useFormationIterations, StatusBadge } from '@entities/formation';
import { useExport } from '@features/formation-export';

const COMBINED_SOURCE_LABEL: Record<string, string> = {
  subtask_a_improved: 'Покращено з підзадачі ІТ-компанії',
  subtask_b_improved: 'Покращено з підзадачі провайдерів',
};

export default function FormationDetailPage() {
  const { id = '' } = useParams();
  const { data, isLoading } = useFormation(id);
  const { data: iterations = [] } = useFormationIterations(
    id,
    !!data && (data.status === 'completed' || data.status === 'failed'),
  );
  const { exportJson, exportCsv } = useExport(id);

  const handleExport = async (kind: 'json' | 'csv') => {
    try {
      if (kind === 'json') await exportJson();
      else await exportCsv();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Помилка експорту');
    }
  };

  if (isLoading || !data) return <p className="text-muted-foreground">Завантаження…</p>;

  const isCombined = data.algorithm === 'combined';

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>{data.name}</CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              {ALGO_LABEL[data.algorithm]} · <StatusBadge status={data.status} />
            </p>
            {isCombined && data.combined_source && (
              <Badge variant="secondary" className="mt-2">
                {COMBINED_SOURCE_LABEL[data.combined_source] ?? data.combined_source}
              </Badge>
            )}
          </div>
          <div className="flex flex-wrap gap-2 justify-end">
            <CompareScenarioDialog currentId={id} />
            <Button variant="outline" onClick={() => handleExport('json')}>Експорт JSON</Button>
            <Button variant="outline" onClick={() => handleExport('csv')}>Експорт CSV</Button>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {data.error && <p className="text-destructive text-sm">{data.error}</p>}
          <FormationTotalsCards
            value={data.value}
            provider_value={data.provider_value}
            provider_profit={data.provider_profit}
            totals={data.totals}
          />
        </CardContent>
      </Card>

      <AlgorithmParamsView algorithm={data.algorithm} params={data.params} b_total={data.b_total} />

      {iterations.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Збіжність</CardTitle></CardHeader>
          <CardContent>
            <IterationChart
              series={[{
                name: ALGO_LABEL[data.algorithm],
                color: ALGO_COLOR[data.algorithm],
                data: iterations.map((it) => ({ iteration: it.iteration, value: it.best_value })),
              }]}
            />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>Призначення</CardTitle></CardHeader>
        <CardContent>
          <AssignmentsTable assignments={data.assignments} />
        </CardContent>
      </Card>
    </div>
  );
}
