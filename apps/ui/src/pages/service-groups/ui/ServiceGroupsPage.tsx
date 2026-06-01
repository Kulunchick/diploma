import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';

import { keys } from '@shared/lib/react-query/keys';
import { cn } from '@shared/lib/utils';
import { Badge } from '@shared/ui/badge';
import { Button } from '@shared/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@shared/ui/card';
import { Checkbox } from '@shared/ui/checkbox';
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '@shared/ui/dialog';
import { Input } from '@shared/ui/input';
import { Label } from '@shared/ui/label';
import { useServiceGroups, type ServiceGroup, serviceGroupApi } from '@entities/service-group';
import { useServices } from '@entities/service';

export default function ServiceGroupsPage() {
  const qc = useQueryClient();
  const { data: groups = [], isLoading } = useServiceGroups();
  const { data: services = [] } = useServices();
  const serviceName = useMemo(() => new Map(services.map((s) => [s.id, s.name])), [services]);

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ServiceGroup | null>(null);
  const [name, setName] = useState('');
  const [memberIds, setMemberIds] = useState<Set<string>>(new Set());

  const ownedByOther = useMemo(() => {
    const map = new Map<string, string>();
    for (const g of groups) {
      if (editing && g.id === editing.id) continue;
      for (const mid of g.members) map.set(mid, g.name);
    }
    return map;
  }, [groups, editing]);

  useEffect(() => {
    if (open) { setName(editing?.name ?? ''); setMemberIds(new Set(editing?.members ?? [])); }
  }, [open, editing]);

  const invalidate = () => qc.invalidateQueries({ queryKey: keys.serviceGroups.all() });

  const saveMutation = useMutation({
    mutationFn: () => {
      const body = { name, member_ids: [...memberIds] };
      return editing ? serviceGroupApi.updateServiceGroup(editing.id, body) : serviceGroupApi.createServiceGroup(body);
    },
    onSuccess: () => {
      toast.success(editing ? 'Групу оновлено' : 'Групу створено');
      setOpen(false); setEditing(null); invalidate();
      qc.invalidateQueries({ queryKey: keys.services.all() });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Помилка збереження'),
  });

  const deleteMutation = useMutation({
    mutationFn: serviceGroupApi.deleteServiceGroup,
    onSuccess: () => {
      toast.success('Групу видалено'); invalidate();
      qc.invalidateQueries({ queryKey: keys.services.all() });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Помилка видалення'),
  });

  const toggle = (id: string) => setMemberIds((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>Групи взаємозалежних сервісів</CardTitle>
          <p className="text-sm text-muted-foreground mt-1">
            Якщо хоча б один сервіс групи включено для провайдера, всі сервіси групи мають
            бути включені.
          </p>
        </div>
        <Button onClick={() => { setEditing(null); setOpen(true); }}>Додати групу</Button>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {isLoading ? <p className="text-muted-foreground">Завантаження…</p>
          : groups.length === 0 ? <p className="text-muted-foreground">Груп ще немає.</p>
          : groups.map((g) => (
            <div key={g.id} className="flex items-start justify-between rounded-md border p-3">
              <div>
                <div className="font-medium">{g.name}</div>
                <div className="flex flex-wrap gap-1 mt-1">
                  {g.members.length === 0
                    ? <span className="text-sm text-muted-foreground">Без сервісів</span>
                    : g.members.map((mid) => (
                        <Badge key={mid} variant="secondary">{serviceName.get(mid) ?? '—'}</Badge>
                      ))}
                </div>
              </div>
              <div className="space-x-2 shrink-0">
                <Button variant="outline" size="sm" onClick={() => { setEditing(g); setOpen(true); }}>Редагувати</Button>
                <Button variant="destructive" size="sm" onClick={() => { if (confirm(`Видалити групу «${g.name}»?`)) deleteMutation.mutate(g.id); }}>Видалити</Button>
              </div>
            </div>
          ))}
      </CardContent>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>{editing ? 'Редагувати групу' : 'Нова група'}</DialogTitle></DialogHeader>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="group-name">Назва</Label>
              <Input id="group-name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="flex flex-col gap-2">
              <Label>Сервіси групи</Label>
              <p className="text-xs text-muted-foreground">Сервіс може входити лише в одну групу.</p>
              <div className="max-h-60 overflow-auto rounded-md border p-2 flex flex-col gap-2">
                {services.length === 0
                  ? <span className="text-sm text-muted-foreground">Спершу додайте сервіси.</span>
                  : services.map((s) => {
                      const owner = ownedByOther.get(s.id);
                      const disabled = !!owner;
                      return (
                        <label key={s.id} title={disabled ? `Уже в групі «${owner}»` : undefined}
                          className={cn('flex items-center gap-2', disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer')}>
                          <Checkbox checked={memberIds.has(s.id)} disabled={disabled} onCheckedChange={() => toggle(s.id)} />
                          <span className="text-sm">
                            {s.name}{disabled && <span className="text-muted-foreground"> — у групі «{owner}»</span>}
                          </span>
                        </label>
                      );
                    })}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button onClick={() => saveMutation.mutate()} disabled={!name.trim() || saveMutation.isPending}>Зберегти</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
