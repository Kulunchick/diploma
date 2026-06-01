import { useEffect } from 'react';
import type { ReactNode } from 'react';

import { useAuthStore } from '@shared/zustand/useAuthStore';

/** Calls hydrate() once on mount: checks the persisted token against /auth/me
 *  and populates the user field (or clears a stale token on 401). Pure side-effect
 *  component — renders children immediately, no loading gate here. Guards handle
 *  the loading state inline. */
export function AuthProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    void useAuthStore.getState().hydrate();
  }, []);

  return <>{children}</>;
}
