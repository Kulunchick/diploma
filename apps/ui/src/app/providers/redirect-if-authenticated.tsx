import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';

import { useAuthStore } from '@shared/zustand/useAuthStore';
import { ROUTES } from '@shared/config/routes';

/**
 * Bounces already-authenticated users away from auth pages (/login, /register).
 * Destination: the `pendingNavigation` set atomically by loginSuccess(), or the
 * default app home (/formations). Using <Navigate> (render-time), not useEffect,
 * so the navigation is the ONLY one that fires — screens must NOT call navigate()
 * after loginSuccess(); they set their destination in the store instead.
 */
export default function RedirectIfAuthenticated({ children }: { children: ReactNode }) {
  const token = useAuthStore((s) => s.token);
  const user = useAuthStore((s) => s.user);
  const loading = useAuthStore((s) => s.loading);
  const pendingNavigation = useAuthStore((s) => s.pendingNavigation);

  // While token is being validated (hydrate in flight): show spinner, not the form.
  if (token && loading) {
    return <div className="p-8 text-center text-muted-foreground">Завантаження…</div>;
  }
  if (token && user) {
    return <Navigate to={pendingNavigation ?? ROUTES.formations} replace />;
  }
  return <>{children}</>;
}
