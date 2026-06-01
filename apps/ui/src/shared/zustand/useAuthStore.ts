import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import type { User } from '@shared/types/user';
import { ApiError } from '@shared/api/error';
import { API_BASE_URL } from '@shared/config/env';

const TOKEN_KEY = 'token';

interface AuthState {
  token: string | null;
  user: User | null;
  /**
   * True while /auth/me is in-flight (hydrate) OR immediately after persist
   * rehydration when a stored token exists but user hasn't been fetched yet.
   * RequireAuth shows a spinner (not a redirect) while this is true.
   */
  loading: boolean;
  /**
   * Where to navigate after a successful login/register. Set atomically with
   * the auth state so RedirectIfAuthenticated uses it as the <Navigate>
   * destination — one update, one redirect, no race with explicit navigate().
   */
  pendingNavigation: string | null;
  /** Atomically set token + user + where to redirect next. */
  loginSuccess: (token: string, user: User, redirectTo?: string) => void;
  clearToken: () => void;
  setUser: (user: User | null) => void;
  /** Called once on app mount: resolves stored token against /auth/me. */
  hydrate: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      loading: false,
      pendingNavigation: null,

      loginSuccess: (token, user, redirectTo) =>
        set({ token, user, pendingNavigation: redirectTo ?? null }),

      clearToken: () => set({ token: null, user: null, pendingNavigation: null }),

      setUser: (user) => set({ user }),

      hydrate: async () => {
        const { token } = get();
        if (!token) {
          set({ loading: false });
          return;
        }

        set({ loading: true });
        try {
          const res = await fetch(`${API_BASE_URL}/auth/me`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (!res.ok) {
            if (res.status === 401) {
              set({ token: null, user: null });
            }
            return;
          }
          const user: User = await res.json();
          set({ user });
        } catch (err) {
          if (err instanceof ApiError && err.status === 401) {
            set({ token: null, user: null });
          }
        } finally {
          set({ loading: false });
        }
      },
    }),
    {
      name: TOKEN_KEY,
      // Only persist the token; user is re-fetched on every hydrate().
      partialize: (state) => ({ token: state.token }),
      // When a stored token is found on page load, pre-set loading=true so
      // RequireAuth shows a spinner (not a redirect) until hydrate() resolves.
      onRehydrateStorage: () => (state) => {
        if (state?.token) {
          state.loading = true;
        }
      },
    },
  ),
);
