import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';

import {
  createServiceGroup,
  deleteServiceGroup,
  listServiceGroups,
  updateServiceGroup,
} from '@/api/serviceGroups';
import { listServices } from '@/api/services';
import type { ServiceGroup } from '@/api/types';
import { Badge } from '@/components/ui/badge.tsx';
import { Button } from '@/components/ui/button.tsx';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card.tsx';
import { Checkbox } from '@/components/ui/checkbox.tsx';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.tsx';
import { Input } from '@/components/ui/input.tsx';
import { Label } from '@/components/ui/label.tsx';

export default function ServiceGroups() {
  const qc = useQueryClient();
  const { data: groups = [], isLoading } = useQuery({
    queryKey: ['service-groups'],
    queryFn: listServiceGroups,
  });
  const { data: services = [] } = useQuery({ queryKey: ['services'], queryFn: listServices });

  const serviceName = useMemo(() => new Map(services.map((s) => [s.id, s.name])), [services]);

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ServiceGroup | null>(null);
  const [name, setName] = useState('');
  const [memberIds, setMemberIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (open) {
      setName(editing?.name ?? '');
      setMemberIds(new Set(editing?.members ?? []));
    }
  }, [open, editing]);

  const invalidate = () => qc.invalidateQueries({ queryKey: ['service-groups'] });

  const saveMutation = useMutation({
    mutationFn: () => {
      const body = { name, member_ids: [...memberIds] };
      return editing ? updateServiceGroup(editing.id, body) : createServiceGroup(body);
    },
    onSuccess: () => {
      toast.success(editing ? 'Групу оновлено' : 'Групу створено');
      setOpen(false);
      setEditing(null);
      invalidate();
      qc.invalidateQueries({ queryKey: ['services'] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Помилка збереження'),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteServiceGroup,
    onSuccess: () => {
      toast.success('Групу видалено');
      invalidate();
      qc.invalidateQueries({ queryKey: ['services'] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Помилка видалення'),
  });

  const toggle = (id: string) =>
    setMemberIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>Групи взаємозалежних сервісів</CardTitle>
          <p className="text-sm text-muted-foreground mt-1">
            Якщо хоча б один сервіс групи включено для провайдера, всі сервіси групи мають
            бути включені. (Зберігається, але поки не враховується розв'язувачем.)
          </p>
        </div>
        <Button
          onClick={() => {
            setEditing(null);
            setOpen(true);
          }}
        >
          Додати групу
        </Button>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {isLoading ? (
          <p className="text-muted-foreground">Завантаження…</p>
        ) : groups.length === 0 ? (
          <p className="text-muted-foreground">Груп ще немає.</p>
        ) : (
          groups.map((g) => (
            <div key={g.id} className="flex items-start justify-between rounded-md border p-3">
              <div>
                <div className="font-medium">{g.name}</div>
                <div className="flex flex-wrap gap-1 mt-1">
                  {g.members.length === 0 ? (
                    <span className="text-sm text-muted-foreground">Без сервісів</span>
                  ) : (
                    g.members.map((mid) => (
                      <Badge key={mid} variant="secondary">
                        {serviceName.get(mid) ?? '—'}
                      </Badge>
                    ))
                  )}
                </div>
              </div>
              <div className="space-x-2 shrink-0">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setEditing(g);
                    setOpen(true);
                  }}
                >
                  Редагувати
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => {
                    if (confirm(`Видалити групу «${g.name}»?`)) deleteMutation.mutate(g.id);
                  }}
                >
                  Видалити
                </Button>
              </div>
            </div>
          ))
        )}
      </CardContent>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? 'Редагувати групу' : 'Нова група'}</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="group-name">Назва</Label>
              <Input id="group-name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="flex flex-col gap-2">
              <Label>Сервіси групи</Label>
              <div className="max-h-60 overflow-auto rounded-md border p-2 flex flex-col gap-2">
                {services.length === 0 ? (
                  <span className="text-sm text-muted-foreground">Спершу додайте сервіси.</span>
                ) : (
                  services.map((s) => (
                    <label key={s.id} className="flex items-center gap-2 cursor-pointer">
                      <Checkbox checked={memberIds.has(s.id)} onCheckedChange={() => toggle(s.id)} />
                      <span className="text-sm">{s.name}</span>
                    </label>
                  ))
                )}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              onClick={() => saveMutation.mutate()}
              disabled={!name.trim() || saveMutation.isPending}
            >
              Зберегти
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
