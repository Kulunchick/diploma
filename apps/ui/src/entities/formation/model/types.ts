export type { FormationAlgorithm, FormationStatus } from '@shared/types/formation';

export interface FormationListItem {
  id: string;
  name: string;
  algorithm: import('@shared/types/formation').FormationAlgorithm;
  status: import('@shared/types/formation').FormationStatus;
  value: number | null;
  created_at: string;
}

export interface FormationCreate {
  name: string;
  b_total: number;
  algorithm: import('@shared/types/formation').FormationAlgorithm;
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
  group_name: string | null;
  final_discount: number | null;
  provider_revenue_pair: number | null;
  provider_profit_pair: number | null;
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
  algorithm: import('@shared/types/formation').FormationAlgorithm;
  status: import('@shared/types/formation').FormationStatus;
  value: number | null;
  provider_value: number | null;
  provider_profit: number | null;
  created_value: number | null;
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
  algorithm: import('@shared/types/formation').FormationAlgorithm;
  status: import('@shared/types/formation').FormationStatus;
  value: number | null;
  provider_value: number | null;
  provider_profit: number | null;
  created_value: number | null;
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
