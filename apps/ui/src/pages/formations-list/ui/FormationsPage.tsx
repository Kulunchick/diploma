import { useState } from 'react';
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

function NumberField({ label, value, onChange, step = 1 }: { label: string; value: number; onChange: (v: number) => void; step?: number }) {
  return (
    <div className="flex flex-col gap-1">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Input type="number" step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
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
  const [combined, setCombined] = useState({ kmax_subproblem: 100, discount_step: 0.05, ignore_discounts: false, local_search_restarts: 0 });

  const paramsFor = (algo: FormationAlgorithm): Record<string, number | boolean> => {
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
              <Input id="f-name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="f-btotal">Загальний ресурс T</Label>
              <Input id="f-btotal" type="number" step={100} value={bTotal} onChange={(e) => setBTotal(Number(e.target.value))} />
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
                <NumberField label="Kmax" value={prob.Kmax} onChange={(v) => setProb({ Kmax: v })} />
              </div>
            )}
            {algorithm === 'ant_colony' && (
              <div className="grid grid-cols-3 gap-2">
                <NumberField label="Kmax" value={ant.Kmax} onChange={(v) => setAnt({ ...ant, Kmax: v })} />
                <NumberField label="L (мурахи)" value={ant.num_ants} onChange={(v) => setAnt({ ...ant, num_ants: v })} />
                <NumberField label="α" step={0.1} value={ant.alpha} onChange={(v) => setAnt({ ...ant, alpha: v })} />
                <NumberField label="β" step={0.1} value={ant.beta} onChange={(v) => setAnt({ ...ant, beta: v })} />
                <NumberField label="ρ" step={0.1} value={ant.p} onChange={(v) => setAnt({ ...ant, p: v })} />
                <NumberField label="τ₀" step={0.1} value={ant.tau} onChange={(v) => setAnt({ ...ant, tau: v })} />
              </div>
            )}
            {algorithm === 'combined' && (
              <div className="flex flex-col gap-3">
                <div className="grid grid-cols-3 gap-2">
                  <NumberField label="K_max підзадач" value={combined.kmax_subproblem} onChange={(v) => setCombined({ ...combined, kmax_subproblem: v })} />
                  <NumberField label="Крок знижки" step={0.01} value={combined.discount_step} onChange={(v) => setCombined({ ...combined, discount_step: v })} />
                  <NumberField label="Додаткові рестарти" value={combined.local_search_restarts} onChange={(v) => setCombined({ ...combined, local_search_restarts: v })} />
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
              disabled={!name.trim() || createMutation.isPending}
            >
              Запустити
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
