import { api, downloadFile } from '@/api/client';
import type {
  CompareResponse,
  FormationCreate,
  FormationDetail,
  FormationIteration,
  FormationListItem,
} from '@/api/types';

export const listFormations = () => api.get<FormationListItem[]>('/formations');
export const getFormation = (id: string) => api.get<FormationDetail>(`/formations/${id}`);
export const getIterations = (id: string) =>
  api.get<FormationIteration[]>(`/formations/${id}/iterations`);
export const createFormation = (body: FormationCreate) =>
  api.post<FormationListItem>('/formations', body);
export const deleteFormation = (id: string) => api.del<void>(`/formations/${id}`);
export const compareFormations = (scenario_ids: string[]) =>
  api.post<CompareResponse>('/formations/compare', { scenario_ids });

export const exportJson = (id: string) =>
  downloadFile(`/formations/${id}/export.json`, `formation-${id}.json`);
export const exportCsv = (id: string) =>
  downloadFile(`/formations/${id}/export.csv`, `formation-${id}.csv`);
