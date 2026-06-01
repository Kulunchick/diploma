import { api } from '@shared/api/client';
import type { Provider, ProviderInput } from '@entities/provider/model/types';

export const listProviders = () => api.get<Provider[]>('/providers');
export const createProvider = (body: ProviderInput) => api.post<Provider>('/providers', body);
export const updateProvider = (id: string, body: ProviderInput) =>
  api.put<Provider>(`/providers/${id}`, body);
export const deleteProvider = (id: string) => api.del<void>(`/providers/${id}`);
