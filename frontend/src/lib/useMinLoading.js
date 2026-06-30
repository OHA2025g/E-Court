import { useEffect, useRef, useState } from "react";

/**
 * Returns a "loading" boolean that stays true for at least `minMs` after
 * the underlying isLoading first turned true — avoids skeleton flicker
 * on warm-cache navigations.
 */
export function useMinLoading(isLoading, minMs = 250) {
  const [show, setShow] = useState(isLoading);
  const startedAt = useRef(null);

  useEffect(() => {
    if (isLoading) {
      if (!startedAt.current) startedAt.current = Date.now();
      setShow(true);
      return;
    }
    if (!startedAt.current) {
      setShow(false);
      return;
    }
    const elapsed = Date.now() - startedAt.current;
    const remaining = Math.max(0, minMs - elapsed);
    const t = setTimeout(() => {
      setShow(false);
      startedAt.current = null;
    }, remaining);
    return () => clearTimeout(t);
  }, [isLoading, minMs]);

  return show;
}
