import type { FormationStatus } from '@entities/formation/model/types';
import { Badge } from '@shared/ui/badge';

const LABELS: Record<FormationStatus, string> = {
  pending: 'Очікує',
  running: 'Виконується',
  completed: 'Завершено',
  failed: 'Помилка',
};

const VARIANTS: Record<FormationStatus, 'secondary' | 'success' | 'destructive'> = {
  pending: 'secondary',
  running: 'secondary',
  completed: 'success',
  failed: 'destructive',
};

export default function StatusBadge({ status }: { status: FormationStatus }) {
  return <Badge variant={VARIANTS[status]}>{LABELS[status]}</Badge>;
}
