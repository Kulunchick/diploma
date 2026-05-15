import { API_BASE_URL, WS_BASE_URL } from '@/config';
import type { CancelJobResponse, JobStartResponse, JobStatusResponse } from '@/api/types';

/**
 * POST /<endpoint> with JSON body.
 * Returns { workflow_id } on success; throws on HTTP error.
 */
export async function startJob(
  endpoint: string,
  payload: unknown,
): Promise<JobStartResponse> {
  const res = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`POST ${endpoint} failed (${res.status}): ${text}`);
  }
  return res.json() as Promise<JobStartResponse>;
}

/**
 * GET /jobs/:id — returns current status + result/error if terminal.
 * Used as WS fallback (polling) and for URL-resume on mount.
 */
export async function getJobStatus(id: string): Promise<JobStatusResponse> {
  const res = await fetch(`${API_BASE_URL}/jobs/${id}`);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`GET /jobs/${id} failed (${res.status}): ${text}`);
  }
  return res.json() as Promise<JobStatusResponse>;
}

/**
 * DELETE /jobs/:id — sends Temporal cancellation request.
 * Only called on explicit user action ("Cancel" button), never on unmount.
 *
 * Note: orphaned workflows (user navigated away without cancelling) are cleaned
 * up by Temporal's execution_timeout + backend TTL — no frontend action needed.
 */
export async function cancelJob(id: string): Promise<CancelJobResponse> {
  const res = await fetch(`${API_BASE_URL}/jobs/${id}`, { method: 'DELETE' });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`DELETE /jobs/${id} failed (${res.status}): ${text}`);
  }
  return res.json() as Promise<CancelJobResponse>;
}

/**
 * Opens a WebSocket to /jobs/:id/events.
 * The caller is responsible for attaching event listeners and closing.
 */
export function openJobStream(id: string): WebSocket {
  return new WebSocket(`${WS_BASE_URL}/jobs/${id}/events`);
}
