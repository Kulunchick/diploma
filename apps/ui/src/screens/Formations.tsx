import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import { createFormation, listFormations } from '@/api/formations';
import type { FormationAlgorithm } from '@/api/types';
import { Button } from '@/components/ui/button.tsx';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card.tsx';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.tsx';
import { Input } from '@/components/ui/input.tsx';
import { Label } from '@/components/ui/label.tsx';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group.tsx';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table.tsx';
import StatusBadge from '@/components/StatusBadge.tsx';

const ALGO_LABEL: Record<FormationAlgorithm, string> = {
  probabilistic: 'Ймовірнісно-жадібний',
  ant_colony: 'Мурашиних колоній',
};

function NumberField({
  label,
  value,
  onChange,
  step = 1,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  step?: number;
}) {
  return (
    <div className="flex flex-col gap-1">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Input type="number" step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </div>
  );
}

export default function Formations() {
  const qc = useQueryClient();
  const navigate = useNavigate();

  const { data: formations = [], isLoading } = useQuery({
    queryKey: ['formations'],
    queryFn: listFormations,
    // Keep polling while anything is still in flight.
    refetchInterval: (query) =>
      (query.state.data ?? []).some((f) => f.status === 'pending' || f.status === 'running')
        ? 2000
        : false,
  });

  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [bTotal, setBTotal] = useState(16000);
  const [algorithm, setAlgorithm] = useState<FormationAlgorithm>('probabilistic');
  const [ant, setAnt] = useState({ Kmax: 100, num_ants: 20, alpha: 1, beta: 2, p: 0.1, tau: 1 });
  const [prob, setProb] = useState({ Kmax: 100 });

  const createMutation = useMutation({
    mutationFn: () =>
      createFormation({
        name,
        b_total: bTotal,
        algorithm,
        params: algorithm === 'ant_colony' ? ant : { Kmax: prob.Kmax },
      }),
    onSuccess: (scenario) => {
      toast.success('Формування запущено');
      setOpen(false);
      qc.invalidateQueries({ queryKey: ['formations'] });
      navigate(`/formations/${scenario.id}`);
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Не вдалося запустити формування'),
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Сценарії формування пакетів</CardTitle>
        <Button
          onClick={() => {
            setName('');
            setOpen(true);
          }}
        >
          Нове формування
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-muted-foreground">Завантаження…</p>
        ) : formations.length === 0 ? (
          <p className="text-muted-foreground">Сценаріїв ще немає.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Назва</TableHead>
                <TableHead>Алгоритм</TableHead>
                <TableHead>Статус</TableHead>
                <TableHead>Дохід (F)</TableHead>
                <TableHead className="text-right">Дії</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {formations.map((f) => (
                <TableRow key={f.id}>
                  <TableCell className="font-medium">{f.name}</TableCell>
                  <TableCell>{ALGO_LABEL[f.algorithm]}</TableCell>
                  <TableCell>
                    <StatusBadge status={f.status} />
                  </TableCell>
                  <TableCell>{f.value != null ? Math.round(f.value).toLocaleString('uk') : '—'}</TableCell>
                  <TableCell className="text-right">
                    <Button variant="outline" size="sm" onClick={() => navigate(`/formations/${f.id}`)}>
                      Відкрити
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Нове формування</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="f-name">Назва</Label>
              <Input id="f-name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="f-btotal">Загальний ресурс T</Label>
              <Input
                id="f-btotal"
                type="number"
                step={100}
                value={bTotal}
                onChange={(e) => setBTotal(Number(e.target.value))}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label>Алгоритм</Label>
              <RadioGroup
                value={algorithm}
                onValueChange={(v) => setAlgorithm(v as FormationAlgorithm)}
              >
                <label className="flex items-center gap-2 cursor-pointer">
                  <RadioGroupItem value="probabilistic" />
                  <span className="text-sm">Ймовірнісно-жадібний</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <RadioGroupItem value="ant_colony" />
                  <span className="text-sm">Мурашиних колоній</span>
                </label>
              </RadioGroup>
              <p className="text-xs text-muted-foreground">
                Сервіси, об'єднані у групу, формують пакет за принципом «усе або нічого»:
                для провайдера вони включаються або разом, або не включаються взагалі.
              </p>
            </div>

            {algorithm === 'probabilistic' ? (
              <div className="grid grid-cols-2 gap-2">
                <NumberField label="Kmax" value={prob.Kmax} onChange={(v) => setProb({ Kmax: v })} />
              </div>
            ) : (
              <div className="grid grid-cols-3 gap-2">
                <NumberField label="Kmax" value={ant.Kmax} onChange={(v) => setAnt({ ...ant, Kmax: v })} />
                <NumberField label="L (мурахи)" value={ant.num_ants} onChange={(v) => setAnt({ ...ant, num_ants: v })} />
                <NumberField label="α" step={0.1} value={ant.alpha} onChange={(v) => setAnt({ ...ant, alpha: v })} />
                <NumberField label="β" step={0.1} value={ant.beta} onChange={(v) => setAnt({ ...ant, beta: v })} />
                <NumberField label="ρ" step={0.1} value={ant.p} onChange={(v) => setAnt({ ...ant, p: v })} />
                <NumberField label="τ₀" step={0.1} value={ant.tau} onChange={(v) => setAnt({ ...ant, tau: v })} />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button onClick={() => createMutation.mutate()} disabled={!name.trim() || createMutation.isPending}>
              Запустити
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
