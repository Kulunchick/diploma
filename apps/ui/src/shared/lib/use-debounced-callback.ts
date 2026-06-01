import { useCallback, useEffect, useRef } from 'react';

/** Returns a debounced version of `fn`. The debounced function is stable
 *  across renders (same reference). Pending calls are flushed/cancelled on unmount. */
export function useDebouncedCallback<T extends unknown[]>(
  fn: (...args: T) => void,
  delayMs: number,
): (...args: T) => void {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) clearTimeout(timerRef.current);
    };
  }, []);

  return useCallback(
    (...args: T) => {
      if (timerRef.current !== null) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        fnRef.current(...args);
      }, delayMs);
    },
    [delayMs],
  );
}
