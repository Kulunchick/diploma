import { api } from '@shared/api/client';
import type { AuthToken, RegisterResponse, User } from '@shared/types/user';

export function register(email: string, password: string, full_name?: string) {
  return api.post<RegisterResponse>('/auth/register', { email, password, full_name });
}

export function login(email: string, password: string) {
  return api.postForm<AuthToken>('/auth/login', { username: email, password });
}

export function getMe() {
  return api.get<User>('/auth/me');
}
