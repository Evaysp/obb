'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { api, ApiError } from '@/lib/api';

interface TranslatedText { title: string; summary: string; }

interface Ctx {
  enabled: boolean;
  setEnabled: (b: boolean) => void;
  loading: boolean;
  error: string | null;
  translations: Record<number, TranslatedText>;
  /** Articles call this on mount; provider debounces + batches requests. */
  request: (articleIds: number[]) => void;
}

const TranslationCtx = createContext<Ctx>({
  enabled: false,
  setEnabled: () => {},
  loading: false,
  error: null,
  translations: {},
  request: () => {},
});

export function useTranslation() {
  return useContext(TranslationCtx);
}

const STORAGE_KEY = 'observer-translate-enabled';
const FLUSH_DELAY_MS = 120;

export function TranslationProvider({ children }: { children: ReactNode }) {
  const [enabled, setEnabledState] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [translations, setTranslations] = useState<Record<number, TranslatedText>>({});

  // Refs so we don't churn the React tree on every queue update
  const pendingIds = useRef<Set<number>>(new Set());
  const inFlightIds = useRef<Set<number>>(new Set());
  const flushTimer = useRef<number | null>(null);
  const cacheRef = useRef<Record<number, TranslatedText>>({});

  // Hydrate enabled from localStorage on mount
  useEffect(() => {
    try {
      setEnabledState(localStorage.getItem(STORAGE_KEY) === '1');
    } catch { /* ignore */ }
  }, []);

  function setEnabled(b: boolean) {
    setEnabledState(b);
    try { localStorage.setItem(STORAGE_KEY, b ? '1' : '0'); } catch {}
    if (!b) setError(null);
  }

  const flush = useCallback(async () => {
    flushTimer.current = null;
    const ids = [...pendingIds.current].filter(
      (id) => !cacheRef.current[id] && !inFlightIds.current.has(id),
    );
    pendingIds.current.clear();
    if (ids.length === 0) return;

    ids.forEach((id) => inFlightIds.current.add(id));
    setLoading(true);
    setError(null);
    try {
      const resp = await api.translateArticles({ articleIds: ids, targetLang: 'zh' });
      const updates: Record<number, TranslatedText> = {};
      let hadError: string | null = null;
      for (const [k, v] of Object.entries(resp.translations)) {
        const id = Number(k);
        updates[id] = { title: v.title, summary: v.summary };
        if (v.error && !hadError) hadError = v.error;
      }
      cacheRef.current = { ...cacheRef.current, ...updates };
      setTranslations((prev) => ({ ...prev, ...updates }));
      if (hadError) setError(hadError);
    } catch (e) {
      if (e instanceof ApiError) setError(`${e.code}: ${e.message}`);
      else if (e instanceof Error) setError(e.message);
      else setError('translation failed');
    } finally {
      ids.forEach((id) => inFlightIds.current.delete(id));
      // If more ids arrived while we were in flight, flush again
      setLoading(inFlightIds.current.size > 0 || pendingIds.current.size > 0);
      if (pendingIds.current.size > 0 && flushTimer.current === null) {
        flushTimer.current = window.setTimeout(flush, FLUSH_DELAY_MS);
      }
    }
  }, []);

  const request = useCallback(
    (articleIds: number[]) => {
      if (!enabled) return;
      let added = false;
      for (const id of articleIds) {
        if (cacheRef.current[id]) continue;
        if (inFlightIds.current.has(id)) continue;
        if (pendingIds.current.has(id)) continue;
        pendingIds.current.add(id);
        added = true;
      }
      if (added && flushTimer.current === null) {
        flushTimer.current = window.setTimeout(flush, FLUSH_DELAY_MS);
      }
    },
    [enabled, flush],
  );

  return (
    <TranslationCtx.Provider
      value={{ enabled, setEnabled, loading, error, translations, request }}
    >
      {children}
    </TranslationCtx.Provider>
  );
}
