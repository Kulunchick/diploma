import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import type { User } from '@shared/types/user';
import { ApiError } from '@shared/api/error';
import { API_BASE_URL } from '@shared/config/env';

const TOKEN_KEY = 'token';

interface AuthState {
  token: string | null;
  user: User | null;
  loading: boolean;
  setToken: (token: string) => void;
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

      setToken: (token) => set({ token }),

      clearToken: () => set({ token: null, user: null }),

      setUser: (user) => set({ user }),

      hydrate: async () => {
        const { token } = get();
        if (!token) return;

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
      // Only persist the token; user is re-fetched on hydrate.
      partialize: (state) => ({ token: state.token }),
    },
  ),
);
