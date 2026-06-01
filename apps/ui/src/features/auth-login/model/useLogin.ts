import { ApiError } from '@shared/api/error';
import { API_BASE_URL } from '@shared/config/env';
import { ROUTES } from '@shared/config/routes';
import { useAuthStore } from '@shared/zustand/useAuthStore';
import * as userApi from '@entities/user/api';
import type { User } from '@shared/types/user';

/**
 * Imperative login helper — call in a form's onSubmit.
 * Fetches user with the fresh token before writing to the store so
 * loginSuccess() can set token + user + redirect atomically.
 * Returns the destination URL navigated to (the `from` location or /services).
 */
export async function loginUser(
  email: string,
  password: string,
  fromPathname?: string,
): Promise<void> {
  const { access_token } = await userApi.login(email, password);
  const res = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${access_token}` },
  });
  if (!res.ok) throw new ApiError(res.status, 'Не вдалося отримати дані профілю');
  const user: User = await res.json();
  useAuthStore.getState().loginSuccess(access_token, user, fromPathname ?? ROUTES.services);
}
