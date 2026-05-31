import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { z } from 'zod';

import {
  createService,
  deleteService,
  listServices,
  updateService,
} from '@/api/services';
import { listServiceGroups } from '@/api/serviceGroups';
import type { Service } from '@/api/types';
import { Badge } from '@/components/ui/badge.tsx';
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table.tsx';

const schema = z.object({
  name: z.string().min(1, "Назва обов'язкова"),
  description: z.string().optional(),
});
type FormValues = z.infer<typeof schema>;

export default function Services() {
  const qc = useQueryClient();
  const { data: services = [], isLoading } = useQuery({ queryKey: ['services'], queryFn: listServices });
  const { data: groups = [] } = useQuery({ queryKey: ['service-groups'], queryFn: listServiceGroups });

  const groupName = useMemo(() => new Map(groups.map((g) => [g.id, g.name])), [groups]);

  const [editing, setEditing] = useState<Service | null>(null);
  const [open, setOpen] = useState(false);

  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } =
    useForm<FormValues>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (open) reset({ name: editing?.name ?? '', description: editing?.description ?? '' });
  }, [open, editing, reset]);

  const invalidate = () => qc.invalidateQueries({ queryKey: ['services'] });

  const saveMutation = useMutation({
    mutationFn: (values: FormValues) => {
      const body = { name: values.name, description: values.description || null };
      return editing ? updateService(editing.id, body) : createService(body);
    },
    onSuccess: () => {
      toast.success(editing ? 'Сервіс оновлено' : 'Сервіс додано');
      setOpen(false);
      setEditing(null);
      invalidate();
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Помилка збереження'),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteService,
    onSuccess: () => {
      toast.success('Сервіс видалено');
      invalidate();
      qc.invalidateQueries({ queryKey: ['service-groups'] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Помилка видалення'),
  });

  const openCreate = () => {
    setEditing(null);
    setOpen(true);
  };
  const openEdit = (s: Service) => {
    setEditing(s);
    setOpen(true);
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Сервіси IT-компанії</CardTitle>
        <Button onClick={openCreate}>Додати сервіс</Button>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-muted-foreground">Завантаження…</p>
        ) : services.length === 0 ? (
          <p className="text-muted-foreground">Сервісів ще немає.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Назва</TableHead>
                <TableHead>Опис</TableHead>
                <TableHead>Групи</TableHead>
                <TableHead className="text-right">Дії</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {services.map((s) => (
                <TableRow key={s.id}>
                  <TableCell className="font-medium">{s.name}</TableCell>
                  <TableCell className="text-muted-foreground">{s.description}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {s.group_ids.map((gid) => (
                        <Badge key={gid} variant="secondary">
                          {groupName.get(gid) ?? '—'}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="text-right space-x-2">
                    <Button variant="outline" size="sm" onClick={() => openEdit(s)}>
                      Редагувати
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => {
                        if (confirm(`Видалити сервіс «${s.name}»?`)) deleteMutation.mutate(s.id);
                      }}
                    >
                      Видалити
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
            <DialogTitle>{editing ? 'Редагувати сервіс' : 'Новий сервіс'}</DialogTitle>
          </DialogHeader>
          <form
            id="service-form"
            onSubmit={handleSubmit((v) => saveMutation.mutate(v))}
            className="flex flex-col gap-4"
          >
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="name">Назва</Label>
              <Input id="name" {...register('name')} />
              {errors.name && <span className="text-sm text-destructive">{errors.name.message}</span>}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="description">Опис</Label>
              <Input id="description" {...register('description')} />
            </div>
          </form>
          <DialogFooter>
            <Button type="submit" form="service-form" disabled={isSubmitting || saveMutation.isPending}>
              Зберегти
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
