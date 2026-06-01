/**
 * Typed fetch wrapper for the authenticated /api/* endpoints.
 *
 * Attaches `Authorization: Bearer <token>` from the Zustand auth store and
 * throws an ApiError (with parsed `detail`) on non-2xx responses.
 * Called outside React, so reads via getState() not a hook.
 */
import { API_BASE_URL } from '@shared/config/env';
import { ApiError } from '@shared/api/error';
import { useAuthStore } from '@shared/zustand/useAuthStore';

interface RequestOptions {
  method?: string;
  json?: unknown;
  form?: Record<string, string>;
  signal?: AbortSignal;
}

function authHeaders(): Headers {
  const headers = new Headers();
  const token = useAuthStore.getState().token;
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return headers;
}

async function parseError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === 'string') return detail;
    if (detail != null) return JSON.stringify(detail);
    return JSON.stringify(body);
  } catch {
    return res.statusText || `HTTP ${res.status}`;
  }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = authHeaders();
  let body: BodyInit | undefined;

  if (options.json !== undefined) {
    headers.set('Content-Type', 'application/json');
    body = JSON.stringify(options.json);
  } else if (options.form) {
    body = new URLSearchParams(options.form);
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body,
    signal: options.signal,
  });

  if (!res.ok) {
    throw new ApiError(res.status, await parseError(res));
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get('content-type') ?? '';
  if (ct.includes('application/json')) return res.json() as Promise<T>;
  return (await res.text()) as unknown as T;
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { method: 'GET', signal }),
  post: <T>(path: string, json?: unknown) => request<T>(path, { method: 'POST', json }),
  postForm: <T>(path: string, form: Record<string, string>) =>
    request<T>(path, { method: 'POST', form }),
  put: <T>(path: string, json: unknown) => request<T>(path, { method: 'PUT', json }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};

/** Download an attachment with the auth header attached, then trigger a browser save. */
export async function downloadFile(path: string, fallbackName: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}${path}`, { headers: authHeaders() });
  if (!res.ok) throw new ApiError(res.status, await parseError(res));

  const disposition = res.headers.get('content-disposition') ?? '';
  const match = /filename="?([^"]+)"?/.exec(disposition);
  const filename = match?.[1] ?? fallbackName;

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export { ApiError } from '@shared/api/error';
