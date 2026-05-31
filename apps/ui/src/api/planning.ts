import { api } from '@/api/client';
import type { PlanningCell, PlanningCellUpsert } from '@/api/types';

export const listPlanning = () => api.get<PlanningCell[]>('/planning');
export const upsertCell = (cell: PlanningCellUpsert) =>
  api.put<PlanningCell>('/planning/cell', cell);
export const bulkUpsert = (cells: PlanningCellUpsert[]) =>
  api.post<PlanningCell[]>('/planning/bulk', { cells });
