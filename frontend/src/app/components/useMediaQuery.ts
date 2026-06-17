import { useEffect, useState } from 'react';

/** Reactive media-query hook. Returns whether the query currently matches. */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia(query).matches : false
  );

  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    onChange();
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, [query]);

  return matches;
}

/** True on phone-sized viewports (≤768px wide). */
export function useIsMobile(): boolean {
  return useMediaQuery('(max-width: 768px)');
}
