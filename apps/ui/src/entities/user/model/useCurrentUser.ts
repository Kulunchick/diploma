import { useQuery } from '@tanstack/react-query';
import { keys } from '@shared/lib/react-query/keys';
import { useAuthStore } from '@shared/zustand/useAuthStore';
import * as userApi from '@entities/user/api';

export function useCurrentUser() {
  const token = useAuthStore((s) => s.token);
  return useQuery({
    queryKey: keys.user.me(),
    queryFn: userApi.getMe,
    enabled: !!token,
  });
}
