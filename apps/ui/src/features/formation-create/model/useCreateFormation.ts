import { useMutation, useQueryClient } from '@tanstack/react-query';
import { keys } from '@shared/lib/react-query/keys';
import { createFormation } from '@entities/formation/api';
import type { FormationCreate, FormationListItem } from '@entities/formation';

export function useCreateFormation(onSuccess?: (item: FormationListItem) => void) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: FormationCreate) => createFormation(body),
    onSuccess: (item) => {
      void qc.invalidateQueries({ queryKey: keys.formations.all() });
      onSuccess?.(item);
    },
  });
}
