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
