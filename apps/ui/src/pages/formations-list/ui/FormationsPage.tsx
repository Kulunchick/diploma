import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import { ROUTES } from '@shared/config/routes';
import { ALGO_LABEL } from '@shared/lib/algorithmParams';
import { Button } from '@shared/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@shared/ui/card';
import { Checkbox } from '@shared/ui/checkbox';
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '@shared/ui/dialog';
import { Input } from '@shared/ui/input';
import { Label } from '@shared/ui/label';
import { RadioGroup, RadioGroupItem } from '@shared/ui/radio-group';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@shared/ui/table';
import { useFormations, StatusBadge, type FormationAlgorithm } from '@entities/formation';
import { useCreateFormation } from '@features/formation-create';

// Bounds mirror Pydantic validators in apps/api/src/operations/models/:
//   FormationCreate.b_total        gt=0
//   AntColonyParameters            no Field constraints (logical: Kmax≥1, L≥1, τ₀>0)
//   ProbabilisticParameters        no Field constraints (logical: Kmax≥1)
//   CombinedParameters.kmax_subproblem   ge=1
//   CombinedParameters.discount_step     gt=0, le=0.5
//   CombinedParameters.local_search_restarts  ge=0
const BOUNDS = {
  bTotal:             { min: 1 },
  prob_Kmax:          { min: 1 },
  ant_Kmax:           { min: 1 },
  ant_num_ants:       { min: 1 },
  ant_alpha:          { min: 0 },
  ant_beta:           { min: 0 },
  ant_p:              { min: 0 },
  ant_tau:            { min: 0.1 },       // τ₀ > 0; step is 0.1
  comb_kmax:          { min: 1 },
  comb_discount_step: { min: 0.01, max: 0.5 },
  comb_restarts:      { min: 0 },
} as const;

function inBounds(v: number, min?: number, max?: number) {
  if (min !== undefined && v < min) return false;
  if (max !== undefined && v > max) return false;
  return true;
}

function NumberField({
  label, value, onChange, step = 1, min, max,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  step?: number;
  min?: number;
  max?: number;
}) {
  const invalid = !inBounds(value, min, max);
  const errorMsg = invalid
    ? (min !== undefined && value < min
        ? `Мін. значення: ${min}`
        : `Макс. значення: ${max}`)
    : null;

  return (
    <div className="flex flex-col gap-1">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Input
        type="number"
        step={step}
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className={invalid ? 'border-destructive focus-visible:ring-destructive' : ''}
      />
      {errorMsg && <span className="text-xs text-destructive">{errorMsg}</span>}
    </div>
  );
}

export default function FormationsPage() {
  const navigate = useNavigate();
  const { data: formations = [], isLoading } = useFormations();

  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [bTotal, setBTotal] = useState(16000);
  const [algorithm, setAlgorithm] = useState<FormationAlgorithm>('probabilistic');
  const [ant, setAnt] = useState({ Kmax: 100, num_ants: 20, alpha: 1, beta: 2, p: 0.1, tau: 1 });
  const [prob, setProb] = useState({ Kmax: 100 });
  const [combined, setCombined] = useState({ kmax_subproblem: 300, discount_step: 0.05, ignore_discounts: false, local_search_restarts: 6, subtask_solver: 'probabilistic' });

  // All param values must be within bounds before the form can be submitted.
  const paramsValid = useMemo(() => {
    if (!inBounds(bTotal, BOUNDS.bTotal.min)) return false;
    if (algorithm === 'probabilistic')
      return inBounds(prob.Kmax, BOUNDS.prob_Kmax.min);
    if (algorithm === 'ant_colony')
      return (
        inBounds(ant.Kmax,     BOUNDS.ant_Kmax.min) &&
        inBounds(ant.num_ants, BOUNDS.ant_num_ants.min) &&
        inBounds(ant.alpha,    BOUNDS.ant_alpha.min) &&
        inBounds(ant.beta,     BOUNDS.ant_beta.min) &&
        inBounds(ant.p,        BOUNDS.ant_p.min) &&
        inBounds(ant.tau,      BOUNDS.ant_tau.min)
      );
    if (algorithm === 'combined')
      return (
        inBounds(combined.kmax_subproblem,   BOUNDS.comb_kmax.min) &&
        inBounds(combined.discount_step,     BOUNDS.comb_discount_step.min, BOUNDS.comb_discount_step.max) &&
        inBounds(combined.local_search_restarts, BOUNDS.comb_restarts.min)
      );
    return true;
  }, [algorithm, bTotal, prob, ant, combined]);

  const paramsFor = (algo: FormationAlgorithm): Record<string, number | boolean | string> => {
    if (algo === 'ant_colony') return { ...ant };
    if (algo === 'combined') return { ...combined };
    return { Kmax: prob.Kmax };
  };

  const createMutation = useCreateFormation((scenario) => {
    toast.success('Формування запущено');
    setOpen(false);
    navigate(ROUTES.formationDetail(scenario.id));
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Сценарії формування пакетів</CardTitle>
        <Button onClick={() => { setName(''); setOpen(true); }}>Нове формування</Button>
      </CardHeader>
      <CardContent>
        {isLoading ? <p className="text-muted-foreground">Завантаження…</p>
          : formations.length === 0 ? <p className="text-muted-foreground">Сценаріїв ще немає.</p>
          : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Назва</TableHead><TableHead>Алгоритм</TableHead>
                  <TableHead>Статус</TableHead><TableHead>Дохід (F)</TableHead>
                  <TableHead className="text-right">Дії</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {formations.map((f) => (
                  <TableRow key={f.id}>
                    <TableCell className="font-medium">{f.name}</TableCell>
                    <TableCell>{ALGO_LABEL[f.algorithm]}</TableCell>
                    <TableCell><StatusBadge status={f.status} /></TableCell>
                    <TableCell>{f.value != null ? Math.round(f.value).toLocaleString('uk') : '—'}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="outline" size="sm" onClick={() => navigate(ROUTES.formationDetail(f.id))}>Відкрити</Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
      </CardContent>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Нове формування</DialogTitle></DialogHeader>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="f-name">Назва</Label>
              <Input id="f-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Назва сценарію" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="f-btotal">Загальний ресурс T</Label>
              <Input
                id="f-btotal"
                type="number"
                step={100}
                min={BOUNDS.bTotal.min}
                value={bTotal}
                onChange={(e) => setBTotal(Number(e.target.value))}
                className={!inBounds(bTotal, BOUNDS.bTotal.min) ? 'border-destructive' : ''}
              />
              {!inBounds(bTotal, BOUNDS.bTotal.min) && (
                <span className="text-xs text-destructive">Мін. значення: {BOUNDS.bTotal.min}</span>
              )}
            </div>
            <div className="flex flex-col gap-2">
              <Label>Алгоритм</Label>
              <RadioGroup value={algorithm} onValueChange={(v) => setAlgorithm(v as FormationAlgorithm)}>
                <label className="flex items-center gap-2 cursor-pointer"><RadioGroupItem value="probabilistic" /><span className="text-sm">Ймовірнісно-жадібний</span></label>
                <label className="flex items-center gap-2 cursor-pointer"><RadioGroupItem value="ant_colony" /><span className="text-sm">Мурашиних колоній</span></label>
                <label className="flex items-center gap-2 cursor-pointer"><RadioGroupItem value="combined" /><span className="text-sm">Комбінований метод</span></label>
              </RadioGroup>
              <p className="text-xs text-muted-foreground">Сервіси, об'єднані у групу, формують пакет за принципом «усе або нічого»: для провайдера вони включаються або разом, або не включаються взагалі.</p>
            </div>

            {algorithm === 'probabilistic' && (
              <div className="grid grid-cols-2 gap-2">
                <NumberField label="Kmax" value={prob.Kmax} min={BOUNDS.prob_Kmax.min}
                  onChange={(v) => setProb({ Kmax: v })} />
              </div>
            )}

            {algorithm === 'ant_colony' && (
              <div className="grid grid-cols-3 gap-2">
                <NumberField label="Kmax"      value={ant.Kmax}     min={BOUNDS.ant_Kmax.min}     onChange={(v) => setAnt({ ...ant, Kmax: v })} />
                <NumberField label="L (мурахи)"value={ant.num_ants} min={BOUNDS.ant_num_ants.min} onChange={(v) => setAnt({ ...ant, num_ants: v })} />
                <NumberField label="α" step={0.1} value={ant.alpha} min={BOUNDS.ant_alpha.min}    onChange={(v) => setAnt({ ...ant, alpha: v })} />
                <NumberField label="β" step={0.1} value={ant.beta}  min={BOUNDS.ant_beta.min}     onChange={(v) => setAnt({ ...ant, beta: v })} />
                <NumberField label="ρ" step={0.1} value={ant.p}     min={BOUNDS.ant_p.min}        onChange={(v) => setAnt({ ...ant, p: v })} />
                <NumberField label="τ₀" step={0.1} value={ant.tau}  min={BOUNDS.ant_tau.min}      onChange={(v) => setAnt({ ...ant, tau: v })} />
              </div>
            )}

            {algorithm === 'combined' && (
              <div className="flex flex-col gap-3">
                <div className="flex flex-col gap-1">
                  <Label className="text-xs text-muted-foreground">Розв'язувач підзадач</Label>
                  <select
                    value={combined.subtask_solver}
                    onChange={(e) => setCombined({ ...combined, subtask_solver: e.target.value })}
                    className="h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  >
                    <option value="probabilistic">ймовірнісно-жадібний</option>
                    <option value="ant_colony">мурашині колонії</option>
                  </select>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <NumberField label="K_max підзадач"   value={combined.kmax_subproblem}
                    min={BOUNDS.comb_kmax.min}
                    onChange={(v) => setCombined({ ...combined, kmax_subproblem: v })} />
                  <NumberField label="Крок знижки" step={0.01} value={combined.discount_step}
                    min={BOUNDS.comb_discount_step.min} max={BOUNDS.comb_discount_step.max}
                    onChange={(v) => setCombined({ ...combined, discount_step: v })} />
                  <NumberField label="Додаткові рестарти" value={combined.local_search_restarts}
                    min={BOUNDS.comb_restarts.min}
                    onChange={(v) => setCombined({ ...combined, local_search_restarts: v })} />
                </div>
                <label className="flex items-center gap-2 cursor-pointer">
                  <Checkbox checked={combined.ignore_discounts} onCheckedChange={(c) => setCombined({ ...combined, ignore_discounts: c === true })} />
                  <span className="text-sm">Ігнорувати верхню межу знижок (рахувати від 0 до 1)</span>
                </label>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              onClick={() => createMutation.mutate({ name, b_total: bTotal, algorithm, params: paramsFor(algorithm) })}
              disabled={!name.trim() || !paramsValid || createMutation.isPending}
            >
              Запустити
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
