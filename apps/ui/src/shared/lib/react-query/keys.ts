/** Query-key factories. Every useQuery/useMutation invalidation uses these —
 *  no inline string arrays anywhere else in the codebase. */
export const keys = {
  user: {
    me: () => ['user', 'me'] as const,
  },
  services: {
    all: () => ['services'] as const,
  },
  serviceGroups: {
    all: () => ['service-groups'] as const,
  },
  providers: {
    all: () => ['providers'] as const,
  },
  planning: {
    all: () => ['planning'] as const,
  },
  formations: {
    all: () => ['formations'] as const,
    byId: (id: string) => ['formation', id] as const,
    iterations: (id: string) => ['formation', id, 'iterations'] as const,
  },
  compare: {
    byIds: (ids: string[]) => ['compare', ids] as const,
  },
};
