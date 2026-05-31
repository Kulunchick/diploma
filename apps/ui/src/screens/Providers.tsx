import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { z } from 'zod';

import {
  createProvider,
  deleteProvider,
  listProviders,
  updateProvider,
} from '@/api/providers';
import type { Provider } from '@/api/types';
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

export default function Providers() {
  const qc = useQueryClient();
  const { data: providers = [], isLoading } = useQuery({
    queryKey: ['providers'],
    queryFn: listProviders,
  });

  const [editing, setEditing] = useState<Provider | null>(null);
  const [open, setOpen] = useState(false);

  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } =
    useForm<FormValues>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (open) reset({ name: editing?.name ?? '', description: editing?.description ?? '' });
  }, [open, editing, reset]);

  const invalidate = () => qc.invalidateQueries({ queryKey: ['providers'] });

  const saveMutation = useMutation({
    mutationFn: (values: FormValues) => {
      const body = { name: values.name, description: values.description || null };
      return editing ? updateProvider(editing.id, body) : createProvider(body);
    },
    onSuccess: () => {
      toast.success(editing ? 'Провайдера оновлено' : 'Провайдера додано');
      setOpen(false);
      setEditing(null);
      invalidate();
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Помилка збереження'),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteProvider,
    onSuccess: () => {
      toast.success('Провайдера видалено');
      invalidate();
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Помилка видалення'),
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Провайдери інфокомунікацій</CardTitle>
        <Button
          onClick={() => {
            setEditing(null);
            setOpen(true);
          }}
        >
          Додати провайдера
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-muted-foreground">Завантаження…</p>
        ) : providers.length === 0 ? (
          <p className="text-muted-foreground">Провайдерів ще немає.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Назва</TableHead>
                <TableHead>Опис</TableHead>
                <TableHead className="text-right">Дії</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {providers.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="font-medium">{p.name}</TableCell>
                  <TableCell className="text-muted-foreground">{p.description}</TableCell>
                  <TableCell className="text-right space-x-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setEditing(p);
                        setOpen(true);
                      }}
                    >
                      Редагувати
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => {
                        if (confirm(`Видалити провайдера «${p.name}»?`)) deleteMutation.mutate(p.id);
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
            <DialogTitle>{editing ? 'Редагувати провайдера' : 'Новий провайдер'}</DialogTitle>
          </DialogHeader>
          <form
            id="provider-form"
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
            <Button type="submit" form="provider-form" disabled={isSubmitting || saveMutation.isPending}>
              Зберегти
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
