import { api } from '@/api/client';
import type { Provider, ProviderInput } from '@/api/types';

export const listProviders = () => api.get<Provider[]>('/providers');
export const createProvider = (body: ProviderInput) => api.post<Provider>('/providers', body);
export const updateProvider = (id: string, body: ProviderInput) =>
  api.put<Provider>(`/providers/${id}`, body);
export const deleteProvider = (id: string) => api.del<void>(`/providers/${id}`);
