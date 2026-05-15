/**
 * Both WS and HTTP share the same host:port.
 * HTTP base is derived from the WS base so one env var covers both.
 * ws://host → http://host,  wss://host → https://host
 */
export const WS_BASE_URL: string =
  (import.meta.env.VITE_WS_BASE_URL as string | undefined) ?? 'ws://localhost:8000';

export const API_BASE_URL: string = WS_BASE_URL.replace(/^ws/, 'http');
