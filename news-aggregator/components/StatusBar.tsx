import { api, ApiError } from '@/lib/api';
import { ThemeToggle } from './ThemeToggle';
import { TranslateToggle } from './TranslateToggle';

/**
 * Top status bar — vim-modeline style.
 * Server component fetches sources/queue health; falls back gracefully
 * when the API is unreachable so the shell still renders.
 */
export async function StatusBar() {
  let sourcesLabel = '—';
  let lastFetchedLabel = '—';
  let queueLabel = 'idle';

  try {
    const sources = await api.getSources();
    const enabled = sources.filter((s) => s.enabled).length;
    sourcesLabel = `${enabled}/${sources.length} ok`;

    const lastTs = sources
      .map((s) => (s.lastFetchedAt ? new Date(s.lastFetchedAt).getTime() : 0))
      .reduce((a, b) => Math.max(a, b), 0);
    lastFetchedLabel = lastTs > 0 ? minutesAgo(lastTs) : 'never';
  } catch (err) {
    if (err instanceof ApiError) {
      sourcesLabel = 'api error';
    } else {
      sourcesLabel = 'offline';
    }
    queueLabel = '—';
  }

  return (
    <header className="bg-bg-elev border-b border-line text-fg-soft text-[12px]">
      <div className="shell flex items-center gap-3 md:gap-4 h-9 flex-wrap">
        <span className="flex items-center gap-2">
          <span className="inline-block w-2 h-2 bg-mark obs-pulse" />
          <span className="text-fg font-bold tracking-[0.04em]">OBSERVER</span>
        </span>
        <span className="sep hidden sm:inline">│</span>
        <span className="hidden sm:flex gap-2">
          <span className="text-fg-faint">sources</span>
          <span className="text-fg num-tabular">{sourcesLabel}</span>
        </span>
        <span className="sep hidden md:inline">│</span>
        <span className="hidden md:flex gap-2">
          <span className="text-fg-faint">queue</span>
          <span className="text-fg">{queueLabel}</span>
        </span>
        <span className="ml-auto flex items-center gap-3 md:gap-4">
          <span className="hidden sm:flex gap-2">
            <span className="text-fg-faint">fetched</span>
            <span className="text-fg num-tabular">{lastFetchedLabel}</span>
          </span>
          <span className="sep hidden sm:inline">│</span>
          <TranslateToggle />
          <span className="sep hidden sm:inline">│</span>
          <ThemeToggle />
        </span>
      </div>
    </header>
  );
}

function minutesAgo(ts: number): string {
  const m = Math.max(0, Math.floor((Date.now() - ts) / 60_000));
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}
