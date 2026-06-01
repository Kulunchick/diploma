import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';

import { listFormations } from '@/api/formations';
import { ROUTES } from '@/config/routes';
import { Button } from '@/components/ui/button.tsx';
import { Checkbox } from '@/components/ui/checkbox.tsx';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog.tsx';
import StatusBadge from '@/components/StatusBadge.tsx';
import { ALGO_LABEL } from '@/lib/algorithmParams';

const fmtDate = (iso: string) => new Date(iso).toLocaleString('uk');

const NO_OTHERS = 'Немає інших завершених сценаріїв для порівняння';

/**
 * Entry point to /formations/compare from a detail page. Lists the user's OTHER
 * completed formations (reusing the cached ['formations'] list), lets the user
 * tick one or more, and navigates to the compare page with the current scenario
 * always first in the id list. Disabled when there is nothing to compare against.
 */
export default function CompareScenarioDialog({ currentId }: { currentId: string }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<Set<string>>(new Set());

  const { data: formations = [], isLoading } = useQuery({
    queryKey: ['formations'],
    queryFn: listFormations,
  });

  const others = useMemo(
    () => formations.filter((f) => f.status === 'completed' && f.id !== currentId),
    [formations, currentId],
  );
  const hasOthers = others.length > 0;

  const toggle = (id: string) =>
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const onOpenChange = (next: boolean) => {
    setOpen(next);
    if (!next) setPicked(new Set()); // reset selection when closing
  };

  const confirm = () => {
    if (picked.size === 0) return;
    const ids = [currentId, ...picked]; // current scenario always first
    navigate(`${ROUTES.formationsCompare}?ids=${ids.join(',')}`);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          disabled={!isLoading && !hasOthers}
          title={!isLoading && !hasOthers ? NO_OTHERS : undefined}
        >
          Порівняти зі сценарієм…
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Порівняти зі сценарієм</DialogTitle>
          <DialogDescription>
            Виберіть один або більше завершених сценаріїв для порівняння з поточним.
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <p className="text-sm text-muted-foreground">Завантаження…</p>
        ) : !hasOthers ? (
          <p className="text-sm text-muted-foreground">{NO_OTHERS}</p>
        ) : (
          <ul className="flex flex-col gap-1 max-h-80 overflow-y-auto">
            {others.map((f) => (
              <li key={f.id}>
                <label className="flex items-center gap-3 rounded-md px-2 py-2 cursor-pointer hover:bg-accent">
                  <Checkbox
                    checked={picked.has(f.id)}
                    onCheckedChange={() => toggle(f.id)}
                  />
                  <span className="flex-1 min-w-0">
                    <span className="block font-medium truncate">{f.name}</span>
                    <span className="block text-xs text-muted-foreground">
                      {ALGO_LABEL[f.algorithm]} · {fmtDate(f.created_at)}
                    </span>
                  </span>
                  <StatusBadge status={f.status} />
                </label>
              </li>
            ))}
          </ul>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Скасувати
          </Button>
          <Button onClick={confirm} disabled={picked.size === 0}>
            Порівняти ({picked.size})
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
