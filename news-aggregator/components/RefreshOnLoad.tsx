'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, ApiError } from '@/lib/api';

type Phase = 'idle' | 'fetching' | 'done' | 'error';

/**
 * Fires `POST /api/sources/refresh` once per page mount, then triggers
 * `router.refresh()` so the server component re-renders with new articles.
 *
 * Backend enforces a 5-minute per-source cooldown, so spamming refresh
 * is safe — eligible sources are simply skipped.
 *
 * Sessionish guard: a flag in sessionStorage prevents duplicate triggers
 * within the same tab session (Next.js dev hot-reload, fast double mount).
 */
export function RefreshOnLoad() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>('idle');
  const [message, setMessage] = useState<string>('');
  const fired = useRef(false);

  useEffect(() => {
    if (fired.current) return;
    fired.current = true;

    // Skip if we already refreshed within the last 30s in this tab — this
    // covers React strict-mode double-invokes and quick navigations away+back.
    try {
      const last = Number(sessionStorage.getItem('observer-last-refresh') ?? 0);
      if (Date.now() - last < 30_000) {
        return;
      }
    } catch {}

    let cancelled = false;
    setPhase('fetching');
    setMessage('fetching latest…');

    (async () => {
      try {
        const r = await api.refreshSources();
        if (cancelled) return;
        try { sessionStorage.setItem('observer-last-refresh', String(Date.now())); } catch {}

        if (r.totalNew > 0) {
          setPhase('done');
          setMessage(`+${r.totalNew} new`);
          router.refresh();
        } else if (r.skippedRecent.length > 0 && r.triggered.length === 0) {
          setPhase('done');
          setMessage('already fresh');
        } else {
          setPhase('done');
          setMessage('no new stories');
        }
      } catch (err) {
        if (cancelled) return;
        setPhase('error');
        if (err instanceof ApiError) setMessage(`${err.code}: ${err.message}`);
        else if (err instanceof Error) setMessage(err.message);
        else setMessage('refresh failed');
      }
    })();

    return () => { cancelled = true; };
  }, [router]);

  // Auto-hide after 4s once we're in a terminal state
  useEffect(() => {
    if (phase !== 'done' && phase !== 'error') return;
    const id = window.setTimeout(() => setPhase('idle'), 4_000);
    return () => window.clearTimeout(id);
  }, [phase]);

  if (phase === 'idle') return null;

  const colors =
    phase === 'fetching' ? 'border-mark-soft text-mark'
    : phase === 'done'   ? 'border-mark text-mark'
    :                      'border-hot text-hot';

  return (
    <div
      role="status"
      className={[
        'fixed bottom-10 left-4 z-40 px-3 py-1.5 text-[11px] tracking-[0.06em] uppercase',
        'bg-bg-elev border flex items-center gap-2 num-tabular',
        'shadow-[0_0_0_1px_rgba(0,0,0,0.04)]',
        colors,
      ].join(' ')}
    >
      {phase === 'fetching' && (
        <span className="inline-block w-1.5 h-1.5 bg-current obs-pulse" />
      )}
      {phase === 'done' && <span className="font-bold">▸</span>}
      {phase === 'error' && <span className="font-bold">!</span>}
      <span>{message}</span>
    </div>
  );
}
