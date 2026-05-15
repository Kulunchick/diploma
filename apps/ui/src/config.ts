/**
 * VITE_USE_TEMPORAL_API=true  → new Temporal-backed flow (POST + WS /jobs/{id}/events)
 * VITE_USE_TEMPORAL_API=false → legacy direct WS (/ws/solve, /ws/experiment1..4)
 *
 * Rollback = flip the flag, no component changes needed.
 */
export const USE_TEMPORAL_API = import.meta.env.VITE_USE_TEMPORAL_API === 'true';

/**
 * Both WS and HTTP share the same host:port.
 * HTTP base is derived from the WS base so one env var covers both.
 * ws://host → http://host,  wss://host → https://host
 */
export const WS_BASE_URL: string =
  (import.meta.env.VITE_WS_BASE_URL as string | undefined) ?? 'ws://localhost:8000';

export const API_BASE_URL: string = WS_BASE_URL.replace(/^ws/, 'http');
