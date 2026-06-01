import { useQuery } from '@tanstack/react-query';
import { keys } from '@shared/lib/react-query/keys';
import { listServiceGroups } from '@entities/service-group/api';

export function useServiceGroups() {
  return useQuery({ queryKey: keys.serviceGroups.all(), queryFn: listServiceGroups });
}
