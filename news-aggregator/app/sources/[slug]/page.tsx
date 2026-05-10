/**
 * Source detail — all articles for one source, with the source's metadata.
 *
 * Reachable from /subscriptions by clicking a card's header.
 * Sibling /sources/[slug]/cookies handles the cookie import flow;
 * this page is the "read everything from this source" view.
 */

import Link from 'next/link';
import { notFound } from 'next/navigation';
import { ApiError, api } from '@/lib/api';
import type { Source } from '@/lib/types';
import { ArticleRow } from '@/components/ArticleRow';
import { ViewSwitch } from '@/components/ViewSwitch';
import { timeAgo } from '@/lib/utils';

export const dynamic = 'force-dynamic';

interface Props { params: { slug: string }; }

export default async function SourceDetailPage({ params }: Props) {
  let source: Source;
  let feed;
  try {
    source = await api.getSourceBySlug(params.slug);
    feed = await api.getFeed({ source: params.slug, limit: 100 });
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    return <BackendOffline err={err} />;
  }

  const items = feed.items;
  const newCutoff = Date.now() - 30 * 60_000;
  const isNew = (a: { publishedAt: string }) =>
    new Date(a.publishedAt).getTime() >= newCutoff;

  const domain = domainFromUrl(source.feedUrl ?? null);

  return (
    <>
      {/* ── Command header ───────────────────────────── */}
      <section className="shell pt-7 pb-5 border-b border-line">
        <Link
          href="/subscriptions"
          className="inline-flex items-center gap-2 text-[12px] text-fg-soft hover:text-mark transition-colors mb-4"
        >
          <span className="text-mark">◂</span>
          <span>back to subscriptions</span>
        </Link>

        <div className="flex items-baseline gap-2 text-[13px] mb-3 flex-wrap">
          <span className="text-mark font-bold">$</span>
          <span className="text-fg">
            observer source <span className="text-mark">--slug={source.slug}</span>{' '}
            <span className="text-mark">--limit={items.length}</span>
          </span>
        </div>

        <div className="flex items-center gap-4 mb-3">
          <SourceLogo domain={domain} fallback={(source.name || source.slug)[0]?.toUpperCase() ?? '?'} />
          <div className="min-w-0">
            <h1 className="font-mono text-[24px] font-semibold text-fg leading-tight m-0 truncate">
              {source.name}
              {source.nameLocal && source.nameLocal !== source.name && (
                <span className="text-fg-faint font-normal text-[16px] ml-3 font-serif italic"
                      style={{ fontVariationSettings: '"opsz" 18' }}>
                  {source.nameLocal}
                </span>
              )}
            </h1>
            <div className="text-fg-faint text-[11px] uppercase tracking-[0.12em] num-tabular mt-1">
              <span className="text-mark">{source.lang}</span>
              {' · '}
              <span>{source.region}</span>
              {' · '}
              <span className={source.tier === 'paywall' ? 'text-warn' : ''}>
                {source.tier}
              </span>
              {' · '}
              <span>{source.kind}</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-8 gap-y-2 border border-line bg-bg-elev px-4 py-2.5 text-[12px] num-tabular w-fit max-w-full">
          <Stat label="shown"      value={String(items.length)} hot />
          <Stat label="24h"        value={String(source.articleCount24h)} />
          <Stat label="last_fetch" value={source.lastFetchedAt ? timeAgo(source.lastFetchedAt) : '—'} />
          <Stat label="enabled"    value={source.enabled ? 'yes' : 'no'} />
        </div>

        {source.feedUrl && (
          <div className="mt-3 text-[11px] text-fg-faint flex items-center gap-2 flex-wrap">
            <span className="uppercase tracking-[0.14em]">feed</span>
            <a
              href={source.feedUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-mark hover:underline truncate max-w-[60ch] inline-block align-middle"
            >
              {source.feedUrl}
            </a>
          </div>
        )}
      </section>

      {/* ── View switch ─────────────────────────────── */}
      <div className="shell border-b border-line">
        <div className="flex flex-wrap items-center gap-3 py-3 text-[12px]">
          <span className="text-fg-faint uppercase tracking-[0.12em]">
            view
          </span>
          <ViewSwitch />
          <span className="ml-auto text-fg-faint num-tabular text-[11px]">
            <span className="text-fg font-medium">{items.length}</span> rows
          </span>
        </div>
      </div>

      {/* ── Article list ─────────────────────────────── */}
      <section className="shell feed">
        {items.length === 0 ? (
          <Empty />
        ) : (
          items.map((a, i) => (
            <ArticleRow
              key={a.id}
              article={a}
              source={source}
              index={i + 1}
              isNew={isNew(a)}
            />
          ))
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
    <div className="border border-dashed border-line py-16 text-center mt-4">
      <p className="text-fg-soft text-[13px]">
        no articles fetched yet for this source.
      </p>
      <p className="text-fg-faint text-[11px] uppercase tracking-[0.12em] mt-2">
        ▸ refresh from <Link href="/" className="text-mark underline normal-case tracking-normal">/brief</Link>
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
      {isApi && (
        <p className="text-fg-faint text-[12px] num-tabular">
          {err.status} {err.code} — {err.message}
        </p>
      )}
    </div>
  );
}

function SourceLogo({ domain, fallback }: { domain: string | null; fallback: string }) {
  if (!domain) {
    return (
      <div className="h-12 w-12 shrink-0 flex items-center justify-center bg-mark-soft text-bg font-bold text-[20px]">
        {fallback}
      </div>
    );
  }
  return (
    <img
      src={`https://www.google.com/s2/favicons?domain=${domain}&sz=64`}
      alt=""
      className="h-12 w-12 shrink-0 object-contain bg-bg p-1 border border-line"
      loading="lazy"
    />
  );
}

function domainFromUrl(input: string | null): string | null {
  if (!input) return null;
  try {
    const u = new URL(input);
    return u.hostname.replace(/^www\./, '');
  } catch {
    return null;
  }
}
