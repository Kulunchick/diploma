import { useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '@shared/zustand/useAuthStore';

export function useLogout() {
  const qc = useQueryClient();
  const clearToken = useAuthStore((s) => s.clearToken);
  return () => {
    clearToken();
    qc.clear();
  };
}
