export function cellKey(serviceId: string, providerId: string): string {
  return `${serviceId}:${providerId}`;
}