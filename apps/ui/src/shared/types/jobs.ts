/**
 * Legacy WS/job/experiment types — left from the removed /solve WebSocket endpoint.
 * Kept to avoid a dead-code cleanup inside a structural migration. Not wired to any
 * current screen. Source: apps/api/src/coursework_operations/routers/jobs.py (removed).
 */

export interface JobStartResponse {
  workflow_id: string;
}

/** Values match temporalio WorkflowExecutionStatus enum on the backend. */
export type WorkflowStatus =
  | 'RUNNING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELED'
  | 'TERMINATED'
  | 'CONTINUED_AS_NEW'
  | 'TIMED_OUT';

export interface JobStatusResponse {
  workflow_id: string;
  status: WorkflowStatus;
  result: unknown;
  error: string | null;
}

export interface CancelJobResponse {
  workflow_id: string;
  cancelled: boolean;
}

export interface VariantStats {
  ant: { avg_value: number; avg_time: number };
  prob: { avg_value: number; avg_time: number };
  relative_difference: number;
}

export type ExperimentData = Record<string, VariantStats>;

export type SolveAlgorithm = 'ant_colony' | 'probabilistic';

export interface SolveStartMessage { type: 'start'; algorithm: SolveAlgorithm }
export interface SolveIterationMessage { type: 'iteration'; algorithm: SolveAlgorithm; iteration: number; current_best_value: number }
export interface SolveResultMessage { type: 'result'; algorithm: SolveAlgorithm; solution: number[][]; value: number }
export interface SolveCompleteMessage { type: 'complete' }
export interface ExperimentStartedMessage { type: 'started' }
export interface ExperimentProgressMessage { type: 'progress'; completed: number; total: number }
export interface ExperimentCompleteMessage { type: 'complete'; data: ExperimentData }
export interface ErrorMessage { type: 'error'; message: string }

export type SolveWsMessage = SolveStartMessage | SolveIterationMessage | SolveResultMessage | SolveCompleteMessage | ErrorMessage;
export type ExperimentWsMessage = ExperimentStartedMessage | ExperimentProgressMessage | ExperimentCompleteMessage | ErrorMessage;
export type JobMessage = SolveWsMessage | ExperimentWsMessage;

export interface Range { min: number; max: number }

export interface SolvePayload {
  m: number; n: number; c: number[][]; B_ij: number[][];
  B_total: number; omega: number[][];
  algorithm_parameters: {
    ant_colony: { Kmax: number; num_ants: number; alpha: number; beta: number; p: number; tau: number };
    probabilistic: { Kmax: number };
  };
}

export interface Experiment1Payload { count: number; n: number; m: number; kmaxVariants: Array<{ kmax: number }>; l: number; p: number; tau: number; alpha: number; beta: number; cRange: Range; bRange: Range; omegaRange: Range }
export interface Experiment2Payload { count: number; betaVariants: Array<{ beta: number }>; p: number; tau: number; alpha: number; antKmax: number; m: number; n: number; l: number; cRange: Range; bRange: Range; omegaRange: Range }
export interface Experiment3Payload { count: number; mnVariants: Array<{ m: number; n: number }>; p: number; tau: number; antKmax: number; probKmax: number; l: number; cRange: Range; bRange: Range; omegaRange: Range }
export interface Experiment4Payload { count: number; omegaRangeVariants: Range[]; p: number; tau: number; alpha: number; beta: number; m: number; n: number; antKmax: number; probKmax: number; l: number; cRange: Range; bRange: Range }

export interface SolveAlgorithmResult { solution: number[][]; value: number }
export interface SolveResult { ant_colony: SolveAlgorithmResult | null; probabilistic: SolveAlgorithmResult | null }
