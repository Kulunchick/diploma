import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';

import { useAuth } from '@/auth/AuthContext';
import { ROUTES } from '@/config/routes';

/**
 * Mirror of RequireAuth for the auth pages: an already-authenticated user
 * visiting /login or /register is bounced to the app home. While a stored token
 * is still being validated (getMe in flight) we render a spinner instead of
 * flashing the login form. If the token turns out invalid, the store clears it
 * (token → null) and the form renders normally — no redirect loop.
 */
export default function RedirectIfAuthenticated({ children }: { children: ReactNode }) {
  const { token, user, loading } = useAuth();

  if (token && loading) {
    return <div className="p-8 text-center text-muted-foreground">Завантаження…</div>;
  }
  if (token && user) {
    return <Navigate to={ROUTES.formations} replace />;
  }
  return <>{children}</>;
}
