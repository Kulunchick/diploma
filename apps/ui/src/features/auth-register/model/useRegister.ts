import { ROUTES } from '@shared/config/routes';
import { useAuthStore } from '@shared/zustand/useAuthStore';
import * as userApi from '@entities/user/api';

/** Imperative register helper — call in a form's onSubmit. */
export async function registerUser(
  email: string,
  password: string,
  fullName?: string,
): Promise<void> {
  const res = await userApi.register(email, password, fullName);
  useAuthStore.getState().loginSuccess(res.access_token, res.user, ROUTES.services);
}
