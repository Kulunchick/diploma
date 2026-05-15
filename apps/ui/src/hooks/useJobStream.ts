/**
 * useJobStream — unified job streaming hook for all 5 endpoints.
 *
 * Flow:
 *   start(endpoint, payload)  →  POST → ?job=id  → WS /jobs/{id}/events
 *   attach(workflowId)        →  GET  → resume WS or show terminal state
 *   cancel()                  →  DELETE + clear ?job= + reset state
 *
 * Resilience: WS onclose(code ≠ 1000, still running) → polling GET every 2 s.
 *
 * URL persistence: workflow_id is written to ?job= on start, cleared on cancel/error.
 * On mount, ?job= is read and attach() is called automatically (Variant A: no DELETE
 * on unmount — orphaned workflows are cleaned up by Temporal execution_timeout).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { cancelJob, getJobStatus, openJobStream, startJob } from '@/api/jobs';
import type {
  ExperimentCompleteMessage,
  JobMessage,
  SolveResult,
  WorkflowStatus,
} from '@/api/types';

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export type JobStatus = 'idle' | 'starting' | 'running' | 'complete' | 'error';

export interface UseJobStreamOptions {
  /**
   * true  → every WS message is appended to messages[]. Use for /solve
   *          (kmax * 2 iteration messages at most — bounded).
   * false → only progress and result are tracked. Use for /experiment*
   *          (run_completed messages can be hundreds — do not accumulate).
   */
  streamMessages?: boolean;
}

export interface UseJobStreamReturn<TResult> {
  start: (endpoint: string, payload: unknown) => Promise<void>;
  attach: (workflowId: string) => Promise<void>;
  cancel: () => Promise<void>;
  status: JobStatus;
  progress: { completed: number; total: number } | null;
  /** Full message stream. Populated only when streamMessages=true. */
  messages: JobMessage[];
  result: TResult | null;
  error: string | null;
  workflowId: string | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const POLL_INTERVAL_MS = 2_000;

function isTerminal(s: WorkflowStatus): boolean {
  return (
    s === 'COMPLETED' ||
    s === 'FAILED' ||
    s === 'CANCELED' ||
    s === 'TERMINATED' ||
    s === 'TIMED_OUT'
  );
}

function isSuccess(s: WorkflowStatus): boolean {
  return s === 'COMPLETED';
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useJobStream<TResult>({
  streamMessages = false,
}: UseJobStreamOptions = {}): UseJobStreamReturn<TResult> {
  const [, setSearchParams] = useSearchParams();

  const [status, setStatus] = useState<JobStatus>('idle');
  const [progress, setProgress] = useState<{ completed: number; total: number } | null>(null);
  const [messages, setMessages] = useState<JobMessage[]>([]);
  const [result, setResult] = useState<TResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [workflowId, setWorkflowId] = useState<string | null>(null);

  // Shadow refs — read in WS event handlers where state would be stale.
  const statusRef = useRef<JobStatus>('idle');
  const workflowIdRef = useRef<string | null>(null);
  useEffect(() => { statusRef.current = status; }, [status]);
  useEffect(() => { workflowIdRef.current = workflowId; }, [workflowId]);

  // Infrastructure refs
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Accumulated solve results (one per algorithm, assembled on 'complete').
  const partialSolveRef = useRef<SolveResult>({ ant_colony: null, probabilistic: null });
  // Stable ref to the latest attach() so the mount effect never needs it as a dep.
  const attachRef = useRef<(id: string) => Promise<void>>(async () => { /* init */ });
  // Guards against StrictMode's double-invocation of the mount effect.
  const mountedRef = useRef(false);

  // ---------------------------------------------------------------------------
  // Internal helpers
  // ---------------------------------------------------------------------------

  const removeJobParam = useCallback(() => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete('job');
        return next;
      },
      { replace: true },
    );
  }, [setSearchParams]);

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const closeWs = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
      wsRef.current.close(1000, 'cleanup');
      wsRef.current = null;
    }
  }, []);

  /**
   * Extracts TResult from GET /jobs/:id response.result:
   *   solve      (streamMessages=true)  → result shape is SolveResult directly
   *   experiment (streamMessages=false) → result shape is { data: ExperimentData }
   */
  const extractResultFromGet = useCallback(
    (raw: unknown): TResult | null => {
      if (raw == null) return null;
      if (streamMessages) return raw as TResult;
      return (raw as { data: TResult }).data ?? null;
    },
    [streamMessages],
  );

  // ---------------------------------------------------------------------------
  // Polling fallback (WS disconnect while still running)
  // ---------------------------------------------------------------------------

  const startPolling = useCallback(
    (id: string) => {
      stopPolling();
      pollRef.current = setInterval(() => {
        void (async () => {
          try {
            const res = await getJobStatus(id);
            if (isSuccess(res.status)) {
              stopPolling();
              setResult(extractResultFromGet(res.result));
              setStatus('complete');
              statusRef.current = 'complete';
            } else if (isTerminal(res.status)) {
              stopPolling();
              setError(res.error ?? `Job ended with status: ${res.status}`);
              setStatus('error');
              statusRef.current = 'error';
              removeJobParam();
            }
            // RUNNING → keep polling until terminal
          } catch {
            // Network hiccup → retry next interval
          }
        })();
      }, POLL_INTERVAL_MS);
    },
    [stopPolling, extractResultFromGet, removeJobParam],
  );

  // ---------------------------------------------------------------------------
  // WS message handler
  // ---------------------------------------------------------------------------

  const handleMessageFn = useCallback(
    (event: MessageEvent) => {
      const msg = JSON.parse(event.data as string) as JobMessage;

      if (streamMessages) {
        setMessages((prev) => [...prev, msg]);
      }

      switch (msg.type) {
        case 'progress':
          setProgress({ completed: msg.completed, total: msg.total });
          break;

        case 'result':
          // Solve: accumulate per-algorithm results; assembled on 'complete'.
          partialSolveRef.current = {
            ...partialSolveRef.current,
            [msg.algorithm]: { solution: msg.solution, value: msg.value },
          };
          break;

        case 'complete':
          stopPolling();
          if (streamMessages) {
            // Solve complete: use accumulated partial results.
            setResult(partialSolveRef.current as unknown as TResult);
          } else {
            // Experiment complete: result lives in message.data.
            setResult((msg as ExperimentCompleteMessage).data as unknown as TResult);
          }
          setStatus('complete');
          statusRef.current = 'complete';
          break;

        case 'error':
          stopPolling();
          setError(msg.message);
          setStatus('error');
          statusRef.current = 'error';
          removeJobParam();
          break;

        // 'start', 'iteration', 'started' — already pushed to messages[] above.
        default:
          break;
      }
    },
    [streamMessages, stopPolling, removeJobParam],
  );

  // Keep a ref so openWs always installs the latest handler without recreating the WS.
  const handleMessageRef = useRef(handleMessageFn);
  handleMessageRef.current = handleMessageFn;

  // ---------------------------------------------------------------------------
  // Open WebSocket
  // ---------------------------------------------------------------------------

  const openWs = useCallback(
    (id: string) => {
      closeWs();
      const ws = openJobStream(id);

      ws.onmessage = (event) => handleMessageRef.current(event);
      ws.onerror = () => { /* onclose fires next */ };
      ws.onclose = (event) => {
        if (event.code !== 1000 && statusRef.current === 'running') {
          // Unexpected disconnect — fall back to polling until terminal.
          startPolling(id);
        }
      };

      wsRef.current = ws;
    },
    [closeWs, startPolling],
  );

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------

  const attach = useCallback(
    async (id: string) => {
      try {
        const res = await getJobStatus(id);
        setWorkflowId(id);
        workflowIdRef.current = id;

        if (isSuccess(res.status)) {
          setResult(extractResultFromGet(res.result));
          setStatus('complete');
          statusRef.current = 'complete';
        } else if (isTerminal(res.status)) {
          setError(res.error ?? `Job ended with status: ${res.status}`);
          setStatus('error');
          statusRef.current = 'error';
          removeJobParam();
        } else {
          // RUNNING (or CONTINUED_AS_NEW) → reconnect WS
          setStatus('running');
          statusRef.current = 'running';
          openWs(id);
        }
      } catch {
        // 404 or network error — stale job id, clear URL and stay idle.
        removeJobParam();
      }
    },
    [extractResultFromGet, removeJobParam, openWs],
  );

  // Always keep the ref current for the mount effect.
  attachRef.current = attach;

  const start = useCallback(
    async (endpoint: string, payload: unknown) => {
      setStatus('starting');
      statusRef.current = 'starting';
      setMessages([]);
      setProgress(null);
      setResult(null);
      setError(null);
      partialSolveRef.current = { ant_colony: null, probabilistic: null };
      closeWs();
      stopPolling();

      try {
        const { workflow_id } = await startJob(endpoint, payload);
        setWorkflowId(workflow_id);
        workflowIdRef.current = workflow_id;
        setSearchParams({ job: workflow_id }, { replace: true });
        setStatus('running');
        statusRef.current = 'running';
        openWs(workflow_id);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
        setStatus('error');
        statusRef.current = 'error';
      }
    },
    [closeWs, stopPolling, setSearchParams, openWs],
  );

  const cancel = useCallback(async () => {
    const id = workflowIdRef.current;
    closeWs();
    stopPolling();

    if (id) {
      try {
        await cancelJob(id);
      } catch {
        // Job may already be terminal — ignore.
      }
    }

    removeJobParam();
    setWorkflowId(null);
    workflowIdRef.current = null;
    setStatus('idle');
    statusRef.current = 'idle';
    setMessages([]);
    setProgress(null);
    setResult(null);
    setError(null);
  }, [closeWs, stopPolling, removeJobParam]);

  // ---------------------------------------------------------------------------
  // Mount: URL resume (?job=<id>)
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (mountedRef.current) return;
    mountedRef.current = true;

    const jobId = new URLSearchParams(window.location.search).get('job');
    if (jobId) {
      void attachRef.current(jobId);
    }
    // Intentionally empty deps: run once on mount.
    // attachRef.current is always the latest version of attach.
  }, []);

  // ---------------------------------------------------------------------------
  // Cleanup on unmount — close WS + stop polling, do NOT cancel the job.
  // ---------------------------------------------------------------------------

  useEffect(() => {
    return () => {
      closeWs();
      stopPolling();
      // Do NOT call cancelJob here. The user may have navigated away temporarily
      // and intends to resume. Orphaned workflows are cleaned up by Temporal's
      // execution_timeout setting on the backend.
    };
  }, [closeWs, stopPolling]);

  // ---------------------------------------------------------------------------

  return { start, attach, cancel, status, progress, messages, result, error, workflowId };
}
