import { useQuery } from '@tanstack/react-query';
import { keys } from '@shared/lib/react-query/keys';
import { listServices } from '@entities/service/api';

export function useServices() {
  return useQuery({ queryKey: keys.services.all(), queryFn: listServices });
}
