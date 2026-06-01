import { useQuery } from '@tanstack/react-query';
import { keys } from '@shared/lib/react-query/keys';
import { listProviders } from '@entities/provider/api';

export function useProviders() {
  return useQuery({ queryKey: keys.providers.all(), queryFn: listProviders });
}
