'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import type { Article, Source } from '@/lib/types';
import { timeAgo } from '@/lib/utils';
import { useTranslation } from './TranslationProvider';

interface Props {
  article: Article;
  source: Source;
  index: number;     // 1-based position in the list
  hero?: boolean;    // hero rows get figure + larger title + accent border
  isNew?: boolean;   // < ~30 min old → "▸ NEW" tag
}

export function ArticleRow({ article, source, index, hero = false, isNew = false }: Props) {
  const idxLabel = `[${String(index).padStart(3, '0')}]`;
  const { enabled, translations, request } = useTranslation();

  // Only register translation requests for rows that have entered (or are
  // about to enter) the viewport. Saves the LLM from translating 50+
  // off-screen articles when the user toggles ON.
  const ref = useRef<HTMLElement>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    if (seen) return;
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === 'undefined') {
      setSeen(true);
      return;
    }
    const ob = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setSeen(true);
          ob.disconnect();
        }
      },
      { rootMargin: '300px 0px' }, // pre-warm articles 300px before viewport
    );
    ob.observe(el);
    return () => ob.disconnect();
  }, [seen]);

  // When toggle is on AND row is visible, ask the provider for a translation.
  useEffect(() => {
    if (enabled && seen) request([article.id]);
  }, [enabled, seen, article.id, request]);

  const tr = enabled ? translations[article.id] : undefined;
  const displayTitle = tr?.title || article.title;
  const displaySummary = tr?.summary ?? article.summary;
  const isTranslated = !!tr && (tr.title !== article.title || tr.summary !== article.summary);

  return (
    <article ref={ref}>
      <Link
        href={`/a/${article.id}`}
        className={[
          'row group',
          hero ? 'row-hero' : '',
        ].join(' ')}
      >
        <div className="row-num">{idxLabel}</div>
        <div className="row-body">
          <div className="row-meta">
            {isNew && <span className="row-meta-new">▸ NEW</span>}
            {isNew && <span className="sep">·</span>}
            <span className="row-meta-src">{source.name}</span>
            <span className="sep">·</span>
            {source.tier === 'paywall' && (
              <>
                <span className="row-meta-paywall">PAYWALL</span>
                <span className="sep">·</span>
              </>
            )}
            <span className="row-meta-lang">{source.lang.toUpperCase()}</span>
            <span className="sep">·</span>
            <time dateTime={article.publishedAt}>{timeAgo(article.publishedAt)}</time>
            {article.readingTimeMin ? (
              <>
                <span className="sep">·</span>
                <span>{article.readingTimeMin} min</span>
              </>
            ) : null}
            {isTranslated && (
              <>
                <span className="sep">·</span>
                <span className="text-mark text-[10px]" title="auto-translated to Chinese">译</span>
              </>
            )}
          </div>

          <h2 className="row-title">{displayTitle}</h2>

          {displaySummary && (
            <p className="row-summary">{displaySummary}</p>
          )}

          {hero && (
            <div className="hero-fig" aria-hidden>
              [ figure · lead image · {source.region} · click to read ]
            </div>
          )}

          {article.entities && article.entities.length > 0 && (
            <div className="row-tags">
              {article.entities.slice(0, 4).map((slug) => (
                <span key={slug} className="row-tag">{slug}</span>
              ))}
              {article.id && (
                <span className="row-tag-id">· id {article.id}</span>
              )}
            </div>
          )}
        </div>
      </Link>
    </article>
  );
}
