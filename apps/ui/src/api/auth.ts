import { api } from '@/api/client';
import type { AuthToken, RegisterResponse, User } from '@/api/types';

export function register(email: string, password: string, full_name?: string) {
  return api.post<RegisterResponse>('/auth/register', { email, password, full_name });
}

export function login(email: string, password: string) {
  // OAuth2 password form: username = email.
  return api.postForm<AuthToken>('/auth/login', { username: email, password });
}

export function getMe() {
  return api.get<User>('/auth/me');
}
