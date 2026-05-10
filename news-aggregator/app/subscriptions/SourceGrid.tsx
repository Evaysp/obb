'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import type { Article, Source } from '@/lib/types';
import { timeAgo } from '@/lib/utils';
import { useTranslation } from '@/components/TranslationProvider';

interface Group {
  source: Source;
  articles: Article[];
}

interface Props { groups: Group[]; }

const STORAGE_KEY = 'observer-source-order';

/**
 * 3-up grid of equal-size source cards. Drag any card onto another to
 * reorder; the order is persisted per-tab in localStorage. New sources
 * (added later) appear at the end of the saved order; removed/disabled
 * sources are skipped silently.
 */
export function SourceGrid({ groups }: Props) {
  const allSlugs = useMemo(() => groups.map((g) => g.source.slug), [groups]);
  const slugsKey = allSlugs.join('|');

  const [order, setOrder] = useState<string[]>(allSlugs);
  const [hydrated, setHydrated] = useState(false);
  const [draggingSlug, setDraggingSlug] = useState<string | null>(null);
  const [overSlug, setOverSlug] = useState<string | null>(null);

  // Hydrate from localStorage; merge with the current set of sources.
  useEffect(() => {
    let saved: string[] = [];
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) saved = JSON.parse(raw);
      if (!Array.isArray(saved)) saved = [];
    } catch { saved = []; }

    const known = new Set(allSlugs);
    const merged = [
      ...saved.filter((s) => known.has(s)),
      ...allSlugs.filter((s) => !saved.includes(s)),
    ];
    setOrder(merged);
    setHydrated(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slugsKey]);

  function persist(next: string[]) {
    setOrder(next);
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); } catch { /* ignore */ }
  }

  function handleDragStart(e: React.DragEvent, slug: string) {
    setDraggingSlug(slug);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', slug);
  }

  function handleDragOver(e: React.DragEvent, slug: string) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    if (slug !== overSlug) setOverSlug(slug);
  }

  function handleDragLeave(slug: string) {
    setOverSlug((prev) => (prev === slug ? null : prev));
  }

  function handleDrop(e: React.DragEvent, targetSlug: string) {
    e.preventDefault();
    const draggedSlug =
      e.dataTransfer.getData('text/plain') || draggingSlug;
    setDraggingSlug(null);
    setOverSlug(null);
    if (!draggedSlug || draggedSlug === targetSlug) return;

    const next = [...order];
    const fromIdx = next.indexOf(draggedSlug);
    const toIdx = next.indexOf(targetSlug);
    if (fromIdx < 0 || toIdx < 0) return;
    next.splice(fromIdx, 1);
    next.splice(toIdx, 0, draggedSlug);
    persist(next);
  }

  function handleDragEnd() {
    setDraggingSlug(null);
    setOverSlug(null);
  }

  function resetOrder() {
    persist(allSlugs);
  }

  const isCustomOrder =
    hydrated && order.some((s, i) => s !== allSlugs[i]);

  const groupBySlug = useMemo(
    () => new Map(groups.map((g) => [g.source.slug, g])),
    [groups],
  );

  const orderedGroups = order
    .map((s) => groupBySlug.get(s))
    .filter((g): g is Group => g !== undefined);

  return (
    <>
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3 text-[11px]">
        <span className="text-fg-faint uppercase tracking-[0.12em]">
          ⋮⋮ drag any card to reorder
        </span>
        <button
          type="button"
          onClick={resetOrder}
          disabled={!isCustomOrder}
          className="text-fg-faint hover:text-mark uppercase tracking-[0.1em] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          ↻ reset order
        </button>
      </div>
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
        {orderedGroups.map((g) => (
          <SourceCard
            key={g.source.slug}
            group={g}
            isDragging={draggingSlug === g.source.slug}
            isOver={overSlug === g.source.slug && draggingSlug !== g.source.slug}
            onDragStart={(e) => handleDragStart(e, g.source.slug)}
            onDragOver={(e) => handleDragOver(e, g.source.slug)}
            onDragLeave={() => handleDragLeave(g.source.slug)}
            onDrop={(e) => handleDrop(e, g.source.slug)}
            onDragEnd={handleDragEnd}
          />
        ))}
      </div>
    </>
  );
}

interface CardProps {
  group: Group;
  isDragging: boolean;
  isOver: boolean;
  onDragStart: (e: React.DragEvent) => void;
  onDragOver: (e: React.DragEvent) => void;
  onDragLeave: () => void;
  onDrop: (e: React.DragEvent) => void;
  onDragEnd: () => void;
}

function SourceCard({
  group, isDragging, isOver,
  onDragStart, onDragOver, onDragLeave, onDrop, onDragEnd,
}: CardProps) {
  const { source, articles } = group;
  const domain = domainFromUrl(source.feedUrl ?? source.slug + '.com');
  const initial = (source.name || source.slug)[0]?.toUpperCase() ?? '?';
  const { enabled: translateEnabled, translations, request } = useTranslation();
  const visibleArticles = articles.slice(0, 20);

  // Ask the provider for translations of every visible title in this card
  const visibleIds = useMemo(
    () => visibleArticles.map((a) => a.id),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [visibleArticles.map((a) => a.id).join(',')],
  );
  useEffect(() => {
    if (translateEnabled) request(visibleIds);
  }, [translateEnabled, visibleIds, request]);

  return (
    <article
      draggable
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      onDragEnd={onDragEnd}
      className={[
        'bg-bg-elev flex flex-col h-[480px] transition-all border',
        isDragging ? 'opacity-30 scale-[0.98]' : '',
        isOver
          ? 'border-mark ring-2 ring-mark-soft ring-offset-1 ring-offset-bg'
          : 'border-line hover:border-mark-soft',
      ].join(' ')}
    >
      {/* header — link occupies the row, drag handle pinned to top-right */}
      <div className="flex items-stretch border-b border-line">
        <Link
          href={`/sources/${source.slug}`}
          draggable={false}
          className="flex items-center gap-3 px-3 py-2 flex-1 min-w-0 hover:bg-[color-mix(in_oklch,var(--mark)_4%,transparent)] transition-colors group"
        >
          <SourceLogo domain={domain} fallback={initial} />
          <div className="min-w-0 flex-1">
            <div className="text-fg font-semibold text-[13px] truncate group-hover:text-mark transition-colors">
              {source.name}
            </div>
            <div className="text-fg-faint text-[10px] uppercase tracking-[0.12em] num-tabular">
              {source.lang} · {source.region} · {articles.length} stories
            </div>
          </div>
        </Link>
        <span
          className="flex items-center px-1.5 text-[10px] leading-none text-fg-faint cursor-grab active:cursor-grabbing select-none border-l border-line hover:text-mark hover:bg-[color-mix(in_oklch,var(--mark)_8%,transparent)]"
          title="Drag to reorder"
          aria-hidden
        >
          ⋮⋮
        </span>
      </div>

      {/* body — numbered titles, scrollable on hover (up to 20 max) */}
      <ol className="flex-1 overflow-y-auto no-scrollbar overscroll-contain px-3 pt-2 pb-2">
        {visibleArticles.map((a, i) => {
          const tr = translateEnabled ? translations[a.id] : undefined;
          const displayTitle = tr?.title || a.title;
          return (
            <li key={a.id} className="flex gap-2 py-1.5">
              <span className="text-fg-faint text-[11px] num-tabular w-5 shrink-0 pt-0.5">
                {i + 1}.
              </span>
              <Link
                href={`/a/${a.id}`}
                draggable={false}
                className="flex-1 min-w-0 text-fg text-[12.5px] leading-[1.4] hover:text-mark transition-colors block"
                title={a.title}
              >
                <span className="block">{displayTitle}</span>
                <span className="text-fg-faint text-[10px] num-tabular">
                  {timeAgo(a.publishedAt)}
                  {source.tier === 'paywall' && (
                    <span className="text-warn ml-2">paywall</span>
                  )}
                  {tr && tr.title !== a.title && (
                    <span className="text-mark ml-2">译</span>
                  )}
                </span>
              </Link>
            </li>
          );
        })}
      </ol>
    </article>
  );
}

function SourceLogo({ domain, fallback }: { domain: string | null; fallback: string }) {
  const [errored, setErrored] = useState(false);
  const src = domain ? `https://www.google.com/s2/favicons?domain=${domain}&sz=64` : null;

  if (!src || errored) {
    return (
      <div className="h-8 w-8 shrink-0 flex items-center justify-center bg-mark-soft text-bg font-bold text-[14px] num-tabular">
        {fallback}
      </div>
    );
  }
  return (
    <img
      src={src}
      alt=""
      className="h-8 w-8 shrink-0 object-contain bg-bg p-0.5 border border-line"
      onError={() => setErrored(true)}
      loading="lazy"
      draggable={false}
    />
  );
}

function domainFromUrl(input: string | null | undefined): string | null {
  if (!input) return null;
  try {
    const u = new URL(input);
    return u.hostname.replace(/^www\./, '');
  } catch {
    if (input.includes('.')) return input.replace(/^www\./, '');
    return null;
  }
}
