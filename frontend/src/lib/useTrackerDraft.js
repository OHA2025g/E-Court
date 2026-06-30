import { useCallback, useEffect, useRef, useState } from "react";

const DEBOUNCE_MS = 300;

export function useTrackerDraft({ userId, tracker, period, hc, fields, setFields }) {
  const key = userId && period && hc
    ? `pmis-draft:${userId}:${tracker}:${period}:${hc}`
    : null;
  const [restored, setRestored] = useState(false);
  const [showBanner, setShowBanner] = useState(false);
  const timer = useRef(null);

  useEffect(() => {
    if (!key || restored) return;
    try {
      const raw = localStorage.getItem(key);
      if (raw) {
        const parsed = JSON.parse(raw);
        setFields(parsed);
        setShowBanner(true);
      }
    } catch {
      /* ignore */
    }
    setRestored(true);
  }, [key, restored, setFields]);

  useEffect(() => {
    if (!key || !restored || showBanner) return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      try {
        localStorage.setItem(key, JSON.stringify(fields));
      } catch {
        /* ignore */
      }
    }, DEBOUNCE_MS);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [fields, key, restored, showBanner]);

  const clearDraft = useCallback(() => {
    if (key) localStorage.removeItem(key);
    setShowBanner(false);
  }, [key]);

  const dismissBanner = useCallback(() => setShowBanner(false), []);

  return { showBanner, clearDraft, dismissBanner };
}
