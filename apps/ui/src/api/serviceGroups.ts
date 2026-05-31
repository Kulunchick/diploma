import { api } from '@/api/client';
import type { ServiceGroup, ServiceGroupInput } from '@/api/types';

export const listServiceGroups = () => api.get<ServiceGroup[]>('/service-groups');
export const createServiceGroup = (body: ServiceGroupInput) =>
  api.post<ServiceGroup>('/service-groups', body);
export const updateServiceGroup = (id: string, body: ServiceGroupInput) =>
  api.put<ServiceGroup>(`/service-groups/${id}`, body);
export const deleteServiceGroup = (id: string) => api.del<void>(`/service-groups/${id}`);
