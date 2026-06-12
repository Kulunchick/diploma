// Low-level WebSocket helper for the live formation convergence stream.
// Server protocol (JSON text frames, server → client):
//   { "type": "iteration", "iteration": number, "best_value": number }
//   { "type": "complete" }
import { WS_BASE_URL } from '@shared/config/env';

export interface IterationPoint {
  iteration: number;
  best_value: number;
}

export interface IterationStreamHandlers {
  onIteration?: (point: IterationPoint) => void;
  onComplete?: () => void;
  onError?: (event: Event) => void;
}

type ServerMessage =
  | { type: 'iteration'; iteration: number; best_value: number }
  | { type: 'complete' };

/**
 * Opens a WebSocket to the live convergence stream for a formation scenario.
 * The JWT is passed as a query parameter because browsers cannot set an
 * Authorization header on the WS handshake. Returns a disposer that closes
 * the socket.
 */
export function openIterationStream(
  scenarioId: string,
  token: string,
  handlers: IterationStreamHandlers,
): () => void {
  const url = `${WS_BASE_URL}/formations/${scenarioId}/ws?token=${encodeURIComponent(token)}`;
  const ws = new WebSocket(url);

  ws.onmessage = (event) => {
    let msg: ServerMessage;
    try {
      msg = JSON.parse(event.data as string);
    } catch {
      return;
    }
    if (msg.type === 'iteration') {
      handlers.onIteration?.({ iteration: msg.iteration, best_value: msg.best_value });
    } else if (msg.type === 'complete') {
      handlers.onComplete?.();
    }
  };

  if (handlers.onError) ws.onerror = handlers.onError;

  return () => {
    try {
      ws.close();
    } catch {
      /* already closing/closed */
    }
  };
}
