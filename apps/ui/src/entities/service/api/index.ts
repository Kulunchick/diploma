import { api } from '@shared/api/client';
import type { Service, ServiceInput } from '@entities/service/model/types';

export const listServices = () => api.get<Service[]>('/services');
export const createService = (body: ServiceInput) => api.post<Service>('/services', body);
export const updateService = (id: string, body: ServiceInput) =>
  api.put<Service>(`/services/${id}`, body);
export const deleteService = (id: string) => api.del<void>(`/services/${id}`);
