'use client';

import Link from 'next/link';
import { forwardRef, memo, useEffect, useRef, useState } from 'react';
import { api, ApiError } from '@/lib/api';
import type { ArticleDetail, Source } from '@/lib/types';
import { useTranslation } from '@/components/TranslationProvider';
import { formatDate, timeAgo } from '@/lib/utils';

interface Props {
  article: ArticleDetail;
  source: Source;
}

type DisplayMode = 'bilingual' | 'translated' | 'original';

const MODE_KEY = 'observer-translate-mode';
const FLUSH_DELAY_MS = 30;
const BATCH_SIZE = 4;     // smaller batch = faster turnaround per LLM call
const MAX_PARALLEL = 6;   // more concurrent batches = closer to immersive-translate feel

/**
 * Block-level (immersive-translate-style) article reader.
 *
 * - DOM walk top-level children of `.prose-article` plus the title/summary.
 * - IntersectionObserver queues blocks as they enter the viewport.
 * - Up to MAX_PARALLEL flushes run concurrently, each sending up to BATCH_SIZE blocks.
 * - Send sanitized HTML (no Tailwind classes) so the LLM doesn't echo them
 *   back into the translation; the inserted translation's styling is
 *   controlled entirely by `.prose-translated` CSS.
 */
export function ArticleReader({ article, source }: Props) {
  const { enabled } = useTranslation();
  const proseRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const summaryRef = useRef<HTMLParagraphElement>(null);

  const [mode, setMode] = useState<DisplayMode>('bilingual');
  const [translatedCount, setTranslatedCount] = useState(0);
  const [totalBlocks, setTotalBlocks] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  // Hydrate display mode preference
  useEffect(() => {
    try {
      const v = localStorage.getItem(MODE_KEY);
      if (v === 'bilingual' || v === 'translated' || v === 'original') {
        setMode(v);
      }
    } catch {}
  }, []);

  function persistMode(v: DisplayMode) {
    setMode(v);
    try { localStorage.setItem(MODE_KEY, v); } catch {}
  }

  // ── Translation engine ─────────────────────────
  const queued = useRef<WeakSet<HTMLElement>>(new WeakSet());
  const queue = useRef<HTMLElement[]>([]);
  const flushTimer = useRef<number | null>(null);
  const inFlight = useRef(0);

  useEffect(() => {
    if (!enabled) return;

    // Detail pages have finite, known content — queue every block right away
    // (no IntersectionObserver). MAX_PARALLEL throttles backend pressure.
    const collected: HTMLElement[] = [];
    if (titleRef.current) collected.push(titleRef.current);
    if (summaryRef.current) collected.push(summaryRef.current);
    if (proseRef.current) {
      for (const child of Array.from(proseRef.current.children) as HTMLElement[]) {
        if (child.dataset.translatedBlock === '1') continue;
        const txt = (child.textContent || '').trim();
        if (!txt) continue;
        collected.push(child);
      }
    }
    setTotalBlocks(collected.length);
    setTranslatedCount(0);
    setError(null);

    for (const el of collected) {
      if (queued.current.has(el)) continue;
      queued.current.add(el);
      el.dataset.translating = '1';
      queue.current.push(el);
    }
    scheduleFlush();

    return () => {
      if (flushTimer.current !== null) {
        window.clearTimeout(flushTimer.current);
        flushTimer.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, article.id]);

  function scheduleFlush() {
    if (flushTimer.current !== null) return;
    flushTimer.current = window.setTimeout(() => {
      flushTimer.current = null;
      // Fire as many parallel batches as we can
      while (queue.current.length > 0 && inFlight.current < MAX_PARALLEL) {
        const batch = queue.current.splice(0, BATCH_SIZE);
        void runBatch(batch);
      }
    }, FLUSH_DELAY_MS);
  }

  async function runBatch(batch: HTMLElement[]) {
    inFlight.current += 1;
    setRunning(true);
    try {
      const texts = batch.map((el) => sanitizeForTranslation(el));
      const r = await api.translateBlocks(texts, 'zh');
      let added = 0;
      for (let i = 0; i < batch.length; i++) {
        const el = batch[i];
        // remove "translating" indicator regardless of outcome
        delete el.dataset.translating;

        const translated = r.translations[i];
        if (!translated) continue;
        // Skip if a translation node was already injected
        const next = el.nextElementSibling as HTMLElement | null;
        if (next?.dataset?.translatedBlock === '1') continue;
        const node = htmlToNode(translated, el.tagName);
        if (!node) continue;
        node.dataset.translatedBlock = '1';
        node.classList.add('prose-translated');
        // Mark the original now (after we know we have a translation for it)
        el.classList.add('prose-original');
        el.parentElement?.insertBefore(node, el.nextSibling);
        added += 1;
      }
      if (added > 0) setTranslatedCount((c) => c + added);
    } catch (e) {
      // clear translating indicator on error too
      for (const el of batch) delete el.dataset.translating;
      if (e instanceof ApiError) setError(`${e.code}: ${e.message}`);
      else if (e instanceof Error) setError(e.message);
      else setError('translation failed');
    } finally {
      inFlight.current = Math.max(0, inFlight.current - 1);
      if (inFlight.current === 0 && queue.current.length === 0) setRunning(false);
      // Drain remaining queue with newly-freed slots
      while (queue.current.length > 0 && inFlight.current < MAX_PARALLEL) {
        const next = queue.current.splice(0, BATCH_SIZE);
        void runBatch(next);
      }
    }
  }

  const themeClass =
    mode === 'bilingual' ? 'translate-bilingual'
      : mode === 'translated' ? 'translate-only'
      : 'translate-original';

  return (
    <div
      className={[
        'shell pt-6 pb-16',
        enabled ? `translate-on ${themeClass}` : '',
      ].join(' ')}
    >
      <Link
        href="/"
        className="inline-flex items-center gap-2 text-[12px] text-fg-soft hover:text-mark transition-colors mb-8"
      >
        <span className="text-mark">◂</span>
        <span>back to brief</span>
      </Link>

      <article className="max-w-[700px] mx-auto">
        {/* Dateline + translation status */}
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[11px] mb-5">
          <span className="text-fg font-bold tracking-[0.04em] uppercase">
            {source.nameLocal || source.name}
          </span>
          <span className="sep">·</span>
          <span className="text-mark">{source.lang.toUpperCase()}</span>
          <span className="sep">·</span>
          <span className="text-fg-faint">{source.region}</span>
          {source.tier === 'paywall' && (
            <>
              <span className="sep">·</span>
              <span className="text-warn">PAYWALL</span>
            </>
          )}
          <span className="sep">·</span>
          <time className="text-fg-faint num-tabular">{timeAgo(article.publishedAt)}</time>
          {enabled && (
            <>
              <span className="sep">·</span>
              <span className="text-mark num-tabular">
                {running && (
                  <span className="inline-block animate-spin mr-1">⟳</span>
                )}
                译 {translatedCount}/{totalBlocks}
              </span>
              <ModeSelector mode={mode} onChange={persistMode} />
            </>
          )}
          {error && (
            <>
              <span className="sep">·</span>
              <span className="text-hot truncate max-w-[40ch]" title={error}>
                ! {error}
              </span>
            </>
          )}
        </div>

        {/* Title */}
        <h1
          ref={titleRef}
          className="font-serif font-semibold text-[34px] md:text-[42px] leading-[1.1] tracking-[-0.018em] mb-5 text-fg article-title"
          style={{ fontVariationSettings: '"opsz" 48' }}
        >
          {article.title}
        </h1>

        {article.summary && (
          <p
            ref={summaryRef}
            className="font-serif text-[19px] leading-[1.55] text-fg-soft mb-8 max-w-[60ch] border-l-2 border-mark pl-5 article-summary"
            style={{ fontVariationSettings: '"opsz" 20' }}
          >
            {article.summary}
          </p>
        )}

        <div className="flex flex-wrap items-baseline gap-x-8 gap-y-2 pb-5 mb-10 border-b border-line text-[12px]">
          {article.author && (
            <div className="flex flex-col gap-0.5">
              <span className="text-fg-faint text-[10px] tracking-[0.14em] uppercase">By</span>
              <span className="font-serif italic text-fg text-[14px]">{article.author}</span>
            </div>
          )}
          <div className="flex flex-col gap-0.5">
            <span className="text-fg-faint text-[10px] tracking-[0.14em] uppercase">Published</span>
            <span className="text-fg num-tabular">{formatDate(article.publishedAt)}</span>
          </div>
          {article.readingTimeMin && (
            <div className="flex flex-col gap-0.5">
              <span className="text-fg-faint text-[10px] tracking-[0.14em] uppercase">Read</span>
              <span className="text-fg num-tabular">{article.readingTimeMin} min</span>
            </div>
          )}
          <div className="flex flex-col gap-0.5">
            <span className="text-fg-faint text-[10px] tracking-[0.14em] uppercase">ID</span>
            <span className="text-fg-faint num-tabular">{article.id}</span>
          </div>
        </div>

        <ProseBody
          ref={proseRef}
          contentHtml={article.contentHtml}
          fallbackSummary={article.summary}
        />

        {article.entities && article.entities.length > 0 && (
          <section className="mt-14 pt-6 border-t border-line">
            <div className="text-[10px] tracking-[0.16em] uppercase text-fg-faint mb-4">
              entities mentioned
            </div>
            <div className="flex flex-wrap gap-2 text-[12px]">
              {article.entities.map((slug) => (
                <Link
                  key={slug}
                  href={`/subscriptions?focus=${slug}`}
                  className="px-2 py-1 border border-line hover:border-mark hover:text-mark transition-colors text-fg-soft"
                >
                  #{slug}
                </Link>
              ))}
            </div>
          </section>
        )}

        <section className="mt-10 pt-6 border-t border-line flex items-center justify-between text-[12px]">
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 text-fg-soft hover:text-mark transition-colors"
          >
            <span className="text-mark">↗</span>
            <span>view original on {source.name}</span>
          </a>
          <span className="text-fg-faint num-tabular">
            fetched · id {article.id}
          </span>
        </section>
      </article>
    </div>
  );
}

// Render the article body once and never let parent re-renders touch it.
// dangerouslySetInnerHTML re-applies on every render with a fresh prop object,
// wiping out the translated sibling nodes we inject. Memoizing keeps this
// subtree out of React's reconciliation while parent state churns.
interface ProseBodyProps {
  contentHtml: string | null | undefined;
  fallbackSummary: string | null | undefined;
}

const ProseBody = memo(
  forwardRef<HTMLDivElement, ProseBodyProps>(function ProseBody(
    { contentHtml, fallbackSummary },
    ref,
  ) {
    if (contentHtml) {
      return (
        <div
          ref={ref}
          className="prose-article"
          dangerouslySetInnerHTML={{ __html: contentHtml }}
        />
      );
    }
    return (
      <div ref={ref} className="prose-article">
        <p className="italic text-fg-soft">
          No extracted body yet for this article. The RSS fetcher may have
          failed to reach the article page, or extraction returned empty —
          check the worker logs.
        </p>
        <p>{fallbackSummary}</p>
      </div>
    );
  }),
);

// ─── helpers ────────────────────────────────────

/**
 * Strip presentational attributes (class, style, data-*) from the element
 * and its descendants. Keep semantic attributes: href, src, alt, title.
 * Returns a clean outerHTML string ready to send to the LLM. Translation
 * styling will be re-applied via .prose-translated CSS, so the LLM never
 * sees React's Tailwind soup and can't pollute the cache key with it.
 */
function sanitizeForTranslation(el: HTMLElement): string {
  const clone = el.cloneNode(true) as HTMLElement;
  const walk = (node: Element) => {
    const drop: string[] = [];
    for (const attr of Array.from(node.attributes)) {
      if (
        attr.name === 'class' ||
        attr.name === 'style' ||
        attr.name.startsWith('data-')
      ) {
        drop.push(attr.name);
      }
    }
    drop.forEach((n) => node.removeAttribute(n));
    for (const child of Array.from(node.children)) walk(child);
  };
  walk(clone);
  return clone.outerHTML;
}

/**
 * Parse an HTML string into a single root element. If the string is plain
 * text or doesn't parse to an element, wrap it in a tag matching the
 * original (e.g. preserve <h1>/<p> nature).
 */
function htmlToNode(html: string, fallbackTag: string): HTMLElement | null {
  const tmp = document.createElement('div');
  tmp.innerHTML = html.trim();
  if (tmp.firstElementChild) return tmp.firstElementChild as HTMLElement;
  // Fallback: build a tag manually
  const tag = (fallbackTag || 'p').toLowerCase();
  const node = document.createElement(tag);
  node.innerHTML = html;
  return node;
}

function ModeSelector({
  mode,
  onChange,
}: {
  mode: DisplayMode;
  onChange: (m: DisplayMode) => void;
}) {
  const opts: { v: DisplayMode; label: string; title: string }[] = [
    { v: 'bilingual',  label: '双语',  title: '原文 + 译文 对照' },
    { v: 'translated', label: '仅译',  title: '只显示译文' },
    { v: 'original',   label: '仅原',  title: '只显示原文（关闭翻译显示）' },
  ];
  return (
    <span className="inline-flex border border-line ml-1">
      {opts.map((o, i) => {
        const on = mode === o.v;
        return (
          <button
            key={o.v}
            type="button"
            onClick={() => onChange(o.v)}
            title={o.title}
            className={[
              'px-1.5 py-px text-[10px]',
              i < opts.length - 1 ? 'border-r border-line' : '',
              on ? 'bg-mark text-bg font-semibold' : 'text-fg-soft hover:text-fg',
            ].join(' ')}
          >
            {o.label}
          </button>
        );
      })}
    </span>
  );
}
