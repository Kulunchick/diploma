import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';

import { useAuthStore } from '@shared/zustand/useAuthStore';
import { ROUTES } from '@shared/config/routes';

/**
 * Mirror of RequireAuth for auth pages: an already-authenticated user
 * visiting /login or /register is bounced to the app home. While a stored
 * token is still being validated (hydrate in flight) we show a spinner
 * instead of flashing the login form. If the token turns out invalid, the
 * store clears it (token → null) and the form renders normally.
 */
export default function RedirectIfAuthenticated({ children }: { children: ReactNode }) {
  const token = useAuthStore((s) => s.token);
  const user = useAuthStore((s) => s.user);
  const loading = useAuthStore((s) => s.loading);

  if (token && loading) {
    return <div className="p-8 text-center text-muted-foreground">Завантаження…</div>;
  }
  if (token && user) {
    return <Navigate to={ROUTES.formations} replace />;
  }
  return <>{children}</>;
}
