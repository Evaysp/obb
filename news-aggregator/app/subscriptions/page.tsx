/**
 * Subscriptions — source-grouped grid view.
 *
 * Each card = one enabled source. Header shows the source name + favicon;
 * the body lists that source's recent article titles, numbered 1, 2, 3…
 * Cards are uniform-sized; titles flow until the body height runs out
 * and trailing items are softly clipped.
 *
 * (Entity tracking — the previous /subscriptions content — has moved to
 * /settings → tracking section.)
 */

import { ApiError, api } from '@/lib/api';
import type { Article, Source } from '@/lib/types';
import { SourceGrid } from './SourceGrid';

export const dynamic = 'force-dynamic';

interface Group {
  source: Source;
  articles: Article[];
}

export default async function SubscriptionsPage() {
  let feed, sources;
  try {
    [feed, sources] = await Promise.all([
      api.getFeed({ limit: 100 }),
      api.getSources(),
    ]);
  } catch (err) {
    return <BackendOffline err={err} />;
  }

  // Group articles by source. Only include enabled sources that have
  // at least one article — empty sources are noise.
  const enabled = sources.filter((s) => s.enabled);
  const bySlug = new Map<string, Article[]>();
  for (const a of feed.items) {
    const arr = bySlug.get(a.sourceSlug) ?? [];
    arr.push(a);
    bySlug.set(a.sourceSlug, arr);
  }

  const groups: Group[] = enabled
    .map((s) => ({ source: s, articles: bySlug.get(s.slug) ?? [] }))
    .filter((g) => g.articles.length > 0)
    // Sort by most-recent activity first
    .sort((a, b) => {
      const ta = new Date(a.articles[0].publishedAt).getTime();
      const tb = new Date(b.articles[0].publishedAt).getTime();
      return tb - ta;
    });

  const totalArticles = groups.reduce((n, g) => n + g.articles.length, 0);
  const utc = new Date().toISOString().slice(0, 10);
  const utcTime = new Date().toISOString().slice(11, 16) + ' UTC';

  return (
    <>
      <section className="shell pt-7 pb-5 border-b border-line">
        <div className="flex items-baseline gap-2 text-[13px] mb-3 flex-wrap">
          <span className="text-mark font-bold">$</span>
          <span className="text-fg">
            observer subscriptions <span className="text-mark">--layout=grid</span>
          </span>
        </div>
        <h1 className="font-mono text-[24px] font-semibold text-fg leading-tight m-0">
          {groups.length} {groups.length === 1 ? 'source' : 'sources'}{' '}
          <span className="text-mark">·</span> {totalArticles} stories{' '}
          <span className="text-mark">·</span> {utcTime}{' '}
          <span className="text-mark">·</span> {utc}
        </h1>
        <p className="text-fg-soft text-[13px] leading-[1.6] max-w-[76ch] mt-2">
          One card per source. Click any title to read; click the source header
          to filter the feed by that source. Entity / person tracking lives
          under <a href="/settings" className="text-mark underline">/settings</a>.
        </p>
      </section>

      <section className="shell py-6">
        {groups.length === 0 ? (
          <Empty />
        ) : (
          <SourceGrid groups={groups} />
        )}
      </section>
    </>
  );
}

function Empty() {
  return (
    <div className="border border-dashed border-line py-16 text-center">
      <p className="text-fg-soft text-[13px]">
        no enabled sources have articles yet.
      </p>
      <p className="text-fg-faint text-[11px] uppercase tracking-[0.12em] mt-2">
        try refreshing the home feed or adding a source
      </p>
    </div>
  );
}

function BackendOffline({ err }: { err: unknown }) {
  const isApi = err instanceof ApiError;
  return (
    <div className="shell pt-12">
      <div className="flex items-baseline gap-2 text-[13px] mb-4">
        <span className="text-hot font-bold">!</span>
        <span className="text-hot">backend unreachable</span>
      </div>
      <h1 className="font-mono text-[24px] font-semibold mb-3">
        Couldn&rsquo;t reach <code className="text-mark">/api/feed</code>.
      </h1>
      {isApi && (
        <p className="text-fg-faint text-[12px] num-tabular">
          {err.status} {err.code} — {err.message}
        </p>
      )}
    </div>
  );
}
