import { useState } from 'react';

import { Card, CardContent, CardHeader } from '@shared/ui/card';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@shared/ui/collapsible';
import { orderedParams, formatParamValue } from '@shared/lib/algorithmParams';
import type { FormationAlgorithm } from '@shared/types/formation';

const fmt = (n: number) => Math.round(n).toLocaleString('uk');

interface Props {
  algorithm: FormationAlgorithm;
  params: Record<string, number | boolean>;
  b_total: number;
}

function FragmentRow({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd>{value}</dd>
    </>
  );
}

export default function AlgorithmParamsView({ algorithm, params, b_total }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card>
        <CardHeader>
          <CollapsibleTrigger className="flex items-center gap-2 text-sm font-medium">
            Параметри алгоритму
            <span className="text-muted-foreground">· T = {fmt(b_total)}</span>
            <span className="ml-auto text-muted-foreground">{open ? '▾' : '▸'}</span>
          </CollapsibleTrigger>
        </CardHeader>
        <CollapsibleContent>
          <CardContent>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm max-w-md">
              <dt className="text-muted-foreground">T (загальний ресурс)</dt>
              <dd>{fmt(b_total)}</dd>
              {orderedParams(algorithm, params).map((row) => (
                <FragmentRow key={row.key} label={row.label} value={formatParamValue(row.value)} />
              ))}
            </dl>
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}
