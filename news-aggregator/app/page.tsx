/**
 * Feed home — server component.
 * Reads filter searchParams, fetches /api/feed, renders the operations-console layout.
 */

import { ApiError, api } from '@/lib/api';
import { ArticleRow } from '@/components/ArticleRow';
import { FilterBarClient } from '@/components/FilterBarClient';
import { RefreshOnLoad } from '@/components/RefreshOnLoad';
import { AISummary } from '@/components/AISummary';
import type { Lang, Source } from '@/lib/types';

interface SearchParams { lang?: string; region?: string; tier?: string; }

type TierFilter = 'all' | 'free' | 'paywall';

function parseLang(v: string | undefined): Lang | undefined {
  return v === 'zh' || v === 'ja' || v === 'en' ? v : undefined;
}
function parseTier(v: string | undefined): TierFilter {
  return v === 'free' || v === 'paywall' ? v : 'all';
}

export const dynamic = 'force-dynamic';

export default async function FeedPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const lang = parseLang(searchParams.lang);
  const region = searchParams.region && searchParams.region !== 'all' ? searchParams.region : undefined;
  const tier = parseTier(searchParams.tier);

  let feed, sources;
  try {
    [feed, sources] = await Promise.all([
      api.getFeed({ lang, region, tier: tier === 'all' ? undefined : tier, limit: 50 }),
      api.getSources(),
    ]);
  } catch (err) {
    return <BackendOffline err={err} />;
  }

  const sourceBySlug = new Map<string, Source>(sources.map((s) => [s.slug, s]));
  const items = feed.items.filter((a) => sourceBySlug.has(a.sourceSlug));
  const enabledSources = sources.filter((s) => s.enabled).length;
  const langs = new Set(items.map((i) => i.lang)).size;
  const lastFetchTs = sources
    .map((s) => (s.lastFetchedAt ? new Date(s.lastFetchedAt).getTime() : 0))
    .reduce((a, b) => Math.max(a, b), 0);
  const lastFetchAgo = lastFetchTs ? minutesSince(lastFetchTs) : 'never';

  const utc = new Date().toISOString().slice(0, 10);
  const utcTime = new Date().toISOString().slice(11, 16) + ' UTC';

  // First item gets the hero treatment; new = published within 30 minutes
  const newCutoff = Date.now() - 30 * 60_000;
  const isNew = (a: { publishedAt: string }) =>
    new Date(a.publishedAt).getTime() >= newCutoff;

  const [heroItem, ...rest] = items;
  const filterFlags = [
    `--lang=${searchParams.lang ?? 'all'}`,
    `--region=${searchParams.region ?? 'all'}`,
    `--tier=${searchParams.tier ?? 'all'}`,
    `--limit=${items.length}`,
  ];

  return (
    <>
      <RefreshOnLoad />

      {/* ── Command header + AI summary ─────────────── */}
      <section className="shell pt-7 pb-5 border-b border-line">
        <div className="grid lg:grid-cols-[minmax(0,1fr)_minmax(360px,440px)] gap-6 lg:gap-10 items-start">
          <div className="min-w-0">
            <div className="flex items-baseline gap-2 text-[13px] mb-3 flex-wrap">
              <span className="text-mark font-bold">$</span>
              <span className="text-fg">
                observer brief{' '}
                {filterFlags.map((f, i) => (
                  <span key={f}>
                    <span className="text-mark">{f}</span>
                    {i < filterFlags.length - 1 ? ' ' : ''}
                  </span>
                ))}
              </span>
              <span className="inline-block w-2 h-3.5 bg-mark obs-blink align-[-2px] ml-1" />
            </div>

            <h1 className="font-mono text-[28px] font-semibold leading-tight tracking-[-0.01em] text-fg m-0">
              {feed.total} {feed.total === 1 ? 'story' : 'stories'}{' '}
              <span className="text-mark">·</span> {utcTime}{' '}
              <span className="text-mark">·</span> {utc}
            </h1>

            <p className="text-fg-soft text-[13px] leading-[1.6] max-w-[76ch] mt-2 mb-4">
              Aggregated read across English, Japanese and Chinese press.
              Deduplicated by URL hash, ranked by editorial weight. Filters
              apply server-side; ordering follows{' '}
              <code className="text-mark">/api/feed</code>.
            </p>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-8 gap-y-2 border border-line bg-bg-elev px-4 py-2.5 text-[12px] num-tabular w-fit max-w-full">
              <Stat label="stories" value={String(feed.total)} hot />
              <Stat label="sources" value={String(enabledSources)} />
              <Stat label="langs"   value={String(langs)} />
              <Stat label="last_fetch" value={lastFetchAgo} />
            </div>
          </div>

          <AISummary />
        </div>
      </section>

      {/* ── Filter bar (with view switch) ────────────── */}
      <div className="shell">
        <FilterBarClient
          initial={{
            lang: lang ?? 'all',
            region: searchParams.region ?? 'all',
            tier,
          }}
          totalCount={feed.total}
          filteredCount={items.length}
        />
      </div>

      {/* ── Feed ─────────────────────────────────────── */}
      <section className="shell feed">
        {items.length === 0 ? (
          <Empty />
        ) : (
          <>
            {heroItem && (
              <ArticleRow
                article={heroItem}
                source={sourceBySlug.get(heroItem.sourceSlug)!}
                index={1}
                hero
                isNew={isNew(heroItem)}
              />
            )}
            {rest.length > 0 && (
              <div className="feed-divider">
                <span className="label">▸ also leading</span>
                <span className="line" />
                <span className="num-tabular">
                  {Math.min(rest.length, 4)} of {items.length}
                </span>
              </div>
            )}
            {rest.slice(0, 4).map((a, i) => (
              <ArticleRow
                key={a.id}
                article={a}
                source={sourceBySlug.get(a.sourceSlug)!}
                index={i + 2}
                isNew={isNew(a)}
              />
            ))}
            {rest.length > 4 && (
              <div className="feed-divider">
                <span className="label">▸ remaining {rest.length - 4} stories</span>
                <span className="line" />
                <span className="num-tabular">
                  showing 006..{String(items.length).padStart(3, '0')}
                </span>
              </div>
            )}
            {rest.slice(4).map((a, i) => (
              <ArticleRow
                key={a.id}
                article={a}
                source={sourceBySlug.get(a.sourceSlug)!}
                index={i + 6}
                isNew={isNew(a)}
              />
            ))}
          </>
        )}
      </section>
    </>
  );
}

function Stat({ label, value, hot = false }: { label: string; value: string; hot?: boolean }) {
  return (
    <div className="flex gap-2 items-baseline">
      <span className="text-fg-faint text-[11px]">{label}</span>
      <span className={['font-semibold', hot ? 'text-mark' : 'text-fg'].join(' ')}>
        {value}
      </span>
    </div>
  );
}

function Empty() {
  return (
    <div className="border border-dashed border-line py-16 text-center text-fg-soft mt-4">
      <p className="font-mono text-[13px]">
        no rows match these filters.
      </p>
      <p className="text-[11px] uppercase tracking-[0.12em] text-fg-faint mt-2">
        try relaxing --lang or --region
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
      <p className="text-fg-soft text-[13px] max-w-[68ch] leading-relaxed mb-4">
        Make sure the backend is running and{' '}
        <code className="text-mark">NEXT_PUBLIC_API_URL</code> points to it.
      </p>
      {isApi && (
        <p className="text-fg-faint text-[12px] num-tabular">
          {err.status} {err.code} — {err.message}
        </p>
      )}
      <p className="text-fg-faint text-[12px] mt-4">
        try: <code className="text-mark">curl http://127.0.0.1:8000/livez</code>
      </p>
    </div>
  );
}

function minutesSince(ts: number): string {
  const m = Math.max(0, Math.floor((Date.now() - ts) / 60_000));
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}
