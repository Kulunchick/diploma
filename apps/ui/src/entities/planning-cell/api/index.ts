import { api } from '@shared/api/client';
import type { PlanningCell, PlanningCellUpsert } from '@entities/planning-cell/model/types';

export const listPlanning = () => api.get<PlanningCell[]>('/planning');
export const upsertCell = (cell: PlanningCellUpsert) =>
  api.put<PlanningCell>('/planning/cell', cell);
export const bulkUpsert = (cells: PlanningCellUpsert[]) =>
  api.post<PlanningCell[]>('/planning/bulk', { cells });
