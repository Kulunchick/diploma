import { useQuery } from '@tanstack/react-query';
import { keys } from '@shared/lib/react-query/keys';
import { listFormations, getFormation, getIterations } from '@entities/formation/api';

export function useFormations() {
  return useQuery({
    queryKey: keys.formations.all(),
    queryFn: listFormations,
    refetchInterval: (query) =>
      (query.state.data ?? []).some((f) => f.status === 'pending' || f.status === 'running')
        ? 2000
        : false,
  });
}

export function useFormation(id: string) {
  return useQuery({
    queryKey: keys.formations.byId(id),
    queryFn: () => getFormation(id),
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s === 'pending' || s === 'running' ? 1500 : false;
    },
  });
}

export function useFormationIterations(id: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.formations.iterations(id),
    queryFn: () => getIterations(id),
    enabled,
  });
}
