/**
 * Maps errors to user-facing Ukrainian messages.
 *
 * The API surfaces the backend's English `detail` string via ApiError. This
 * helper translates the known ones, falls back to an HTTP-status message for
 * the rest, recognises network failures, and lets through messages that are
 * already Ukrainian (e.g. ones we throw ourselves).
 */
import { ApiError } from '@shared/api/error';

const NETWORK = 'Немає з’єднання із сервером';

/** Exact backend `detail` strings → Ukrainian. */
const DETAIL_MAP: Record<string, string> = {
  // auth
  'Could not validate credentials': 'Не вдалося підтвердити облікові дані. Увійдіть знову.',
  'A user with this email already exists': 'Користувач із такою електронною поштою вже існує',
  'Incorrect email or password': 'Невірна електронна пошта або пароль',
  // planning
  'One or more services do not exist': 'Один або кілька сервісів не існують',
  'One or more providers do not exist': 'Один або кілька провайдерів не існують',
  // providers
  'Provider not found': 'Провайдера не знайдено',
  'A provider with this name already exists': 'Провайдер із такою назвою вже існує',
  // formations
  'Scenario not found': 'Сценарій не знайдено',
  'At least one service and one provider are required':
    'Потрібні щонайменше один сервіс і один провайдер',
  // services
  'Service not found': 'Сервіс не знайдено',
  'A service with this name already exists': 'Сервіс із такою назвою вже існує',
  // service groups
  'One or more member services do not exist': 'Один або кілька сервісів-учасників не існують',
  'Service group not found': 'Групу сервісів не знайдено',
  'A service group with this name already exists': 'Група сервісів із такою назвою вже існує',
};

/** Fallback by HTTP status when the detail is unknown/English. */
const STATUS_MAP: Record<number, string> = {
  400: 'Невірний запит',
  401: 'Потрібно увійти в систему',
  403: 'Доступ заборонено',
  404: 'Не знайдено',
  409: 'Конфлікт даних',
  422: 'Перевірте правильність введених даних',
  429: 'Забагато запитів. Спробуйте пізніше.',
  500: 'Помилка сервера. Спробуйте пізніше.',
  502: 'Помилка сервера. Спробуйте пізніше.',
  503: 'Сервіс тимчасово недоступний. Спробуйте пізніше.',
  504: 'Сервіс тимчасово недоступний. Спробуйте пізніше.',
};

const hasCyrillic = (s: string) => /[а-щьюяґєіїА-ЩЬЮЯҐЄІЇ]/.test(s);
const looksNetwork = (s: string) => /failed to fetch|networkerror|load failed/i.test(s);

/** Translate a backend `detail`, including the few dynamic (f-string) ones. */
function translateDetail(detail: string): string | undefined {
  if (DETAIL_MAP[detail]) return DETAIL_MAP[detail];
  if (detail.startsWith('Unknown algorithm')) return 'Невідомий алгоритм';
  if (detail.startsWith("Service '") && detail.includes('already belongs to group')) {
    return 'Сервіс уже належить до іншої групи (сервіс може належати лише до однієї групи)';
  }
  return undefined;
}

/**
 * Resolve a Ukrainian message for any thrown value.
 * @param fallback page-specific Ukrainian text used when nothing better fits.
 */
export function getErrorMessage(err: unknown, fallback = 'Сталася помилка'): string {
  // fetch() rejects with a TypeError when the network is unreachable.
  if (err instanceof TypeError) return NETWORK;

  if (err instanceof ApiError) {
    const mapped = translateDetail(err.message);
    if (mapped) return mapped;
    if (hasCyrillic(err.message)) return err.message; // already Ukrainian
    return STATUS_MAP[err.status] ?? fallback;
  }

  if (err instanceof Error) {
    if (looksNetwork(err.message)) return NETWORK;
    if (hasCyrillic(err.message)) return err.message;
    return fallback;
  }

  return fallback;
}
