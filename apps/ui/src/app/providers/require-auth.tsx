import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { useAuthStore } from '@shared/zustand/useAuthStore';

export default function RequireAuth({ children }: { children: ReactNode }) {
  const token = useAuthStore((s) => s.token);
  const user = useAuthStore((s) => s.user);
  const loading = useAuthStore((s) => s.loading);
  const location = useLocation();

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  if (loading) {
    return <div className="p-8 text-center text-muted-foreground">Завантаження…</div>;
  }
  if (!user) {
    // Token present but invalid/expired — bounce to login.
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}
