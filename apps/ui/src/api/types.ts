/**
 * TypeScript types for the Temporal-backed job API.
 * Verified against backend Pydantic models in apps/api/src/.
 *
 * Backend source of truth:
 *   POST bodies   → apps/api/src/coursework_operations/routers/{solve,experiments}.py
 *   WS messages   → apps/api/src/coursework_operations/routers/jobs.py
 *   GET /jobs/:id → apps/api/src/coursework_operations/routers/jobs.py
 *   Experiment result shape → apps/api/src/experiments/base.py (ExperimentStatsResult)
 */

// ---------------------------------------------------------------------------
// API responses
// ---------------------------------------------------------------------------

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
  /** Raw model_dump() of the workflow result. Shape varies by workflow type. */
  result: unknown;
  error: string | null;
}

export interface CancelJobResponse {
  workflow_id: string;
  cancelled: boolean;
}

// ---------------------------------------------------------------------------
// Shared experiment result shape
// Matches ExperimentStatsResult.model_dump() from apps/api/src/experiments/base.py
// ---------------------------------------------------------------------------

export interface VariantStats {
  ant: { avg_value: number; avg_time: number };
  prob: { avg_value: number; avg_time: number };
  relative_difference: number;
}

/** Keyed by variant string: "100", "2.0", "3x4", "0.1-0.5" */
export type ExperimentData = Record<string, VariantStats>;

// ---------------------------------------------------------------------------
// WS messages — /solve (legacy format preserved by backend adapter)
// Source: apps/api/src/coursework_operations/routers/jobs.py _solve_adapter()
// ---------------------------------------------------------------------------

export type SolveAlgorithm = 'ant_colony' | 'probabilistic';

export interface SolveStartMessage {
  type: 'start';
  algorithm: SolveAlgorithm;
}

export interface SolveIterationMessage {
  type: 'iteration';
  algorithm: SolveAlgorithm;
  iteration: number;
  current_best_value: number;
}

export interface SolveResultMessage {
  type: 'result';
  algorithm: SolveAlgorithm;
  solution: number[][];
  value: number;
}

export interface SolveCompleteMessage {
  type: 'complete';
}

// ---------------------------------------------------------------------------
// WS messages — /experiment* (new unified format)
// Source: apps/api/src/coursework_operations/routers/jobs.py _experiment_adapter()
// ---------------------------------------------------------------------------

export interface ExperimentStartedMessage {
  type: 'started';
}

export interface ExperimentProgressMessage {
  type: 'progress';
  completed: number;
  total: number;
}

export interface ExperimentCompleteMessage {
  type: 'complete';
  data: ExperimentData;
}

// ---------------------------------------------------------------------------
// Shared / union types
// ---------------------------------------------------------------------------

export interface ErrorMessage {
  type: 'error';
  message: string;
}

export type SolveWsMessage =
  | SolveStartMessage
  | SolveIterationMessage
  | SolveResultMessage
  | SolveCompleteMessage
  | ErrorMessage;

export type ExperimentWsMessage =
  | ExperimentStartedMessage
  | ExperimentProgressMessage
  | ExperimentCompleteMessage
  | ErrorMessage;

/** Union of every possible message from /jobs/{id}/events. */
export type JobMessage = SolveWsMessage | ExperimentWsMessage;

// ---------------------------------------------------------------------------
// POST payload types — verified field-by-field against backend Pydantic models
// ---------------------------------------------------------------------------

export interface Range {
  min: number;
  max: number;
}

/** apps/api/src/coursework_operations/models/task_request.py + algorithm_parametrs.py */
export interface SolvePayload {
  m: number;
  n: number;
  c: number[][];
  B_ij: number[][];
  B_total: number;
  omega: number[][];
  algorithm_parameters: {
    ant_colony: {
      Kmax: number;
      num_ants: number;
      alpha: number;
      beta: number;
      p: number;
      tau: number;
    };
    probabilistic: { Kmax: number };
  };
}

/** apps/api/src/experiments/experiment1.py Experiment1Input */
export interface Experiment1Payload {
  count: number;
  n: number;
  m: number;
  kmaxVariants: Array<{ kmax: number }>;
  l: number;
  p: number;
  tau: number;
  alpha: number;
  beta: number;
  cRange: Range;
  bRange: Range;
  omegaRange: Range;
}

/** apps/api/src/experiments/experiment2.py Experiment2Input */
export interface Experiment2Payload {
  count: number;
  betaVariants: Array<{ beta: number }>;
  p: number;
  tau: number;
  alpha: number;
  antKmax: number;
  m: number;
  n: number;
  l: number;
  cRange: Range;
  bRange: Range;
  omegaRange: Range;
}

/** apps/api/src/experiments/experiment3.py Experiment3Input (no alpha/beta — hardcoded 1.0) */
export interface Experiment3Payload {
  count: number;
  mnVariants: Array<{ m: number; n: number }>;
  p: number;
  tau: number;
  antKmax: number;
  probKmax: number;
  l: number;
  cRange: Range;
  bRange: Range;
  omegaRange: Range;
}

/** apps/api/src/experiments/experiment4.py Experiment4Input */
export interface Experiment4Payload {
  count: number;
  omegaRangeVariants: Range[];
  p: number;
  tau: number;
  alpha: number;
  beta: number;
  m: number;
  n: number;
  antKmax: number;
  probKmax: number;
  l: number;
  cRange: Range;
  bRange: Range;
}

// ---------------------------------------------------------------------------
// Solve result (assembled by useJobStream from individual WS result messages)
// ---------------------------------------------------------------------------

export interface SolveAlgorithmResult {
  solution: number[][];
  value: number;
}

export interface SolveResult {
  ant_colony: SolveAlgorithmResult | null;
  probabilistic: SolveAlgorithmResult | null;
}

// ---------------------------------------------------------------------------
// Information-system resources (mirror apps/api/src/operations/models/*)
// ---------------------------------------------------------------------------

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  created_at: string;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
}

export interface RegisterResponse {
  user: User;
  access_token: string;
  token_type: string;
}

export interface Service {
  id: string;
  name: string;
  description: string | null;
  group_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface ServiceInput {
  name: string;
  description?: string | null;
}

export interface ServiceGroup {
  id: string;
  name: string;
  members: string[];
  created_at: string;
  updated_at: string;
}

export interface ServiceGroupInput {
  name: string;
  member_ids: string[];
}

export interface Provider {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProviderInput {
  name: string;
  description?: string | null;
}

export interface PlanningCell {
  id: string;
  service_id: string;
  provider_id: string;
  price: number;
  resource: number;
  provider_revenue: number;
  discount: number;
  min_value: number;
}

export type PlanningField =
  | 'price'
  | 'resource'
  | 'provider_revenue'
  | 'discount'
  | 'min_value';

export interface PlanningCellUpsert {
  service_id: string;
  provider_id: string;
  price: number;
  resource: number;
  provider_revenue: number;
  discount: number;
  min_value: number;
}

export type FormationAlgorithm = 'probabilistic' | 'ant_colony' | 'combined';
export type FormationStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface FormationListItem {
  id: string;
  name: string;
  algorithm: FormationAlgorithm;
  status: FormationStatus;
  value: number | null;
  created_at: string;
}

export interface FormationCreate {
  name: string;
  b_total: number;
  algorithm: FormationAlgorithm;
  params: Record<string, number | boolean>;
}

export interface FormationAssignment {
  service_id: string;
  service_name: string;
  provider_id: string;
  provider_name: string;
  price: number;
  discount: number;
  effective_revenue: number;
  resource_used: number;
  /** Set when the service was assigned as part of a group (all-or-nothing). */
  group_name: string | null;
  /** The discount actually applied (negotiated for combined; = discount else). */
  final_discount: number | null;
}

export interface FormationTotals {
  total_revenue: number;
  total_resource_used: number;
  provider_count: number;
  service_count: number;
}

export interface FormationDetail {
  id: string;
  name: string;
  algorithm: FormationAlgorithm;
  status: FormationStatus;
  value: number | null;
  /** Combined-method only: F_prov, winning candidate, and value + provider_value. */
  provider_value: number | null;
  combined_source: string | null;
  combined_benefit: number | null;
  b_total: number;
  params: Record<string, number | boolean>;
  workflow_id: string | null;
  error: string | null;
  created_at: string;
  finished_at: string | null;
  assignments: FormationAssignment[];
  totals: FormationTotals;
}

export interface CompareProviderBreakdown {
  provider_id: string;
  provider_name: string;
  assignment_count: number;
  services: string[];
}

export interface CompareScenario {
  id: string;
  name: string;
  algorithm: FormationAlgorithm;
  status: FormationStatus;
  value: number | null;
  provider_value: number | null;
  combined_benefit: number | null;
  b_total: number;
  params: Record<string, number | boolean>;
  total_revenue: number;
  total_resource_used: number;
  per_provider: CompareProviderBreakdown[];
}

export interface CompareResponse {
  scenarios: CompareScenario[];
}

export interface FormationIteration {
  iteration: number;
  best_value: number;
}
