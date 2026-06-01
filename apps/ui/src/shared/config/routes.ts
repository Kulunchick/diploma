/** Single source of truth for app route paths. No hardcoded path strings in
 *  components — import from here. */
export const ROUTES = {
  login: '/login',
  register: '/register',
  services: '/services',
  serviceGroups: '/service-groups',
  providers: '/providers',
  planning: '/planning',
  formations: '/formations',
  formationsCompare: '/formations/compare',
  formationDetail: (id: string) => `/formations/${id}`,
} as const;

/** Authenticated app-shell navigation sections (left→right order in the nav). */
export const NAV_SECTIONS: { to: string; label: string }[] = [
  { to: ROUTES.services, label: 'Сервіси' },
  { to: ROUTES.serviceGroups, label: 'Групи сервісів' },
  { to: ROUTES.providers, label: 'Провайдери' },
  { to: ROUTES.planning, label: 'Планові дані' },
  { to: ROUTES.formations, label: 'Формування пакетів' },
];
