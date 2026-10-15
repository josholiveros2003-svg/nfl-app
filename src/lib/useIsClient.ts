import { useSyncExternalStore } from 'react';

const noop = () => () => {};

/** False while the page is being pre-built and during the browser's first render, true
 *  after that. Use it for anything that depends on the address (?id=...), which the
 *  pre-built page can't know, so the two first renders match. */
export function useIsClient() {
  return useSyncExternalStore(
    noop,
    () => true,
    () => false,
  );
}
