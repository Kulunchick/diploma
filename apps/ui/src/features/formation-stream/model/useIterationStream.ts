import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { keys } from '@shared/lib/react-query/keys';
import { openIterationStream } from '@shared/api/ws';
import { useAuthStore } from '@shared/zustand/useAuthStore';
import type { FormationIteration } from '@entities/formation';

/**
 * Live convergence points streamed over WebSocket while a scenario runs.
 *
 * Returns the accumulated iterations (sorted, last-write-wins per iteration);
 * empty when inactive. On the server's `complete` signal it invalidates the
 * formation and persisted-iterations queries so the page swaps to the durable
 * Postgres history.
 */
export function useIterationStream(id: string, active: boolean): FormationIteration[] {
  const [points, setPoints] = useState<FormationIteration[]>([]);
  const byIteration = useRef<Map<number, number>>(new Map());
  const qc = useQueryClient();

  useEffect(() => {
    if (!active || !id) return;
    const token = useAuthStore.getState().token;
    if (!token) return;

    byIteration.current = new Map();
    setPoints([]);

    return openIterationStream(id, token, {
      onIteration: ({ iteration, best_value }) => {
        byIteration.current.set(iteration, best_value);
        setPoints(
          [...byIteration.current.entries()]
            .sort((a, b) => a[0] - b[0])
            .map(([it, value]) => ({ iteration: it, best_value: value })),
        );
      },
      onComplete: () => {
        void qc.invalidateQueries({ queryKey: keys.formations.byId(id) });
        void qc.invalidateQueries({ queryKey: keys.formations.iterations(id) });
      },
    });
  }, [id, active, qc]);

  return points;
}
