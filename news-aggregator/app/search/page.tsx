'use client';

import { useState, useEffect, useMemo, Suspense } from 'react';
import type { FormEvent } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { api } from '@/lib/api';
import type { Article, Entity, Source } from '@/lib/types';
import { ArticleRow } from '@/components/ArticleRow';

function SearchContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const initial = searchParams.get('q') ?? '';
  const [query, setQuery] = useState(initial);

  const [articles, setArticles] = useState<Article[]>([]);
  const [entities, setEntities] = useState<Entity[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setQuery(searchParams.get('q') ?? '');
  }, [searchParams]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const [feed, ents, srcs] = await Promise.all([
          api.getFeed({ limit: 100 }),
          api.getEntities(),
          api.getSources(),
        ]);
        if (!cancelled) {
          setArticles(feed.items);
          setEntities(ents);
          setSources(srcs);
        }
      } catch {
        // backend offline — leave arrays empty
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (query.trim()) {
      router.push(`/search?q=${encodeURIComponent(query.trim())}`);
    }
  }

  const q = query.trim().toLowerCase();
  const sourceBySlug = new Map(sources.map((s) => [s.slug, s]));

  const articleResults = useMemo(() => {
    if (!q) return [];
    return articles
      .filter((a) =>
        a.title.toLowerCase().includes(q) || a.summary.toLowerCase().includes(q),
      )
      .slice(0, 24);
  }, [q, articles]);

  const entityResults = useMemo(() => {
    if (!q) return [];
    return entities.filter((e) =>
      e.canonicalName.toLowerCase().includes(q) ||
      (e.nameLocal ?? '').toLowerCase().includes(q) ||
      e.aliases.some((a) => a.toLowerCase().includes(q)),
    );
  }, [q, entities]);

  const sourceResults = useMemo(() => {
    if (!q) return [];
    return sources.filter((s) =>
      s.name.toLowerCase().includes(q) ||
      (s.nameLocal ?? '').toLowerCase().includes(q),
    );
  }, [q, sources]);

  const total = articleResults.length + entityResults.length + sourceResults.length;

  return (
    <>
      <section className="shell pt-7 pb-5 border-b border-line">
        <div className="flex items-baseline gap-2 text-[13px] mb-3">
          <span className="text-mark font-bold">$</span>
          <span className="text-fg">observer search</span>
          {q && <span className="text-mark">--q=&quot;{query}&quot;</span>}
        </div>

        <form onSubmit={submit} className="flex items-baseline gap-3 pb-1">
          <span className="text-mark font-bold text-[18px]">/</span>
          <input
            type="text"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="query articles, entities, sources…"
            className="flex-1 font-mono text-[20px] md:text-[24px] tracking-[-0.005em] bg-transparent outline-none text-fg placeholder:text-fg-faint"
          />
          <button
            type="submit"
            className="text-[11px] uppercase tracking-[0.12em] text-fg-soft hover:text-mark border border-line hover:border-mark px-2 py-1"
          >
            ↵ run
          </button>
        </form>

        {q && !loading && (
          <div className="mt-3 text-[11px] text-fg-faint num-tabular">
            <span className="text-mark">{total}</span> result{total === 1 ? '' : 's'} for &ldquo;{query}&rdquo;
          </div>
        )}
        {loading && (
          <div className="mt-3 text-[11px] text-fg-faint">loading…</div>
        )}
      </section>

      {!q && !loading && (
        <section className="shell py-10">
          <p className="text-fg-soft text-[13px] max-w-[68ch] leading-[1.6]">
            Type anything. Search spans article titles and summaries,
            multi-language entity aliases (e.g. <span className="text-mark">马斯克</span> /{' '}
            <span className="text-mark">Elon Musk</span> /{' '}
            <span className="text-mark">イーロン・マスク</span>), and source names.
          </p>
          <div className="mt-6 flex flex-wrap gap-2">
            <span className="text-[11px] tracking-[0.12em] uppercase text-fg-faint mr-1">try</span>
            {['Nvidia', 'AI', '日銀', '央行', 'supply chain', 'Musk'].map((term) => (
              <button
                key={term}
                onClick={() => router.push(`/search?q=${encodeURIComponent(term)}`)}
                className="px-2 py-0.5 text-[11px] border border-line text-fg-soft hover:text-mark hover:border-mark transition-colors"
              >
                {term}
              </button>
            ))}
          </div>
          <p className="mt-8 text-fg-faint text-[11px] max-w-[68ch]">
            ▸ Full-text Meilisearch search lands in phase 3. Current search
            scans the most recent 100 articles loaded from the feed.
          </p>
        </section>
      )}

      {q && !loading && entityResults.length > 0 && (
        <section className="shell py-6 border-b border-line">
          <h2 className="text-[11px] tracking-[0.16em] uppercase text-fg-soft mb-3">
            <span className="text-mark mr-2">▸</span>entities · {entityResults.length}
          </h2>
          <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
            {entityResults.map((e) => (
              <Link
                key={e.slug}
                href={`/subscriptions?focus=${e.slug}`}
                className="px-3 py-2 border border-line hover:border-mark hover:text-mark transition-colors text-[12px]"
              >
                <div className="font-semibold text-fg">{e.canonicalName}</div>
                <div className="text-fg-faint text-[11px] tracking-[0.04em] uppercase mt-0.5">
                  {e.kind} · {e.articleCount7d} this week
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {q && !loading && sourceResults.length > 0 && (
        <section className="shell py-6 border-b border-line">
          <h2 className="text-[11px] tracking-[0.16em] uppercase text-fg-soft mb-3">
            <span className="text-mark mr-2">▸</span>sources · {sourceResults.length}
          </h2>
          <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
            {sourceResults.map((s) => (
              <Link
                key={s.slug}
                href="/sources"
                className="px-3 py-2 border border-line hover:border-mark hover:text-mark transition-colors text-[12px]"
              >
                <div className="font-semibold text-fg">{s.name}</div>
                <div className="text-fg-faint text-[11px] tracking-[0.04em] uppercase mt-0.5">
                  {s.region} · {s.lang} · {s.articleCount24h} stories today
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {q && !loading && articleResults.length > 0 && (
        <section className="shell feed">
          <h2 className="text-[11px] tracking-[0.16em] uppercase text-fg-soft py-3">
            <span className="text-mark mr-2">▸</span>articles · {articleResults.length}
          </h2>
          {articleResults.map((a, i) => {
            const src = sourceBySlug.get(a.sourceSlug);
            if (!src) return null;
            return <ArticleRow key={a.id} article={a} source={src} index={i + 1} />;
          })}
        </section>
      )}

      {q && !loading && total === 0 && (
        <div className="shell py-10">
          <div className="border border-dashed border-line py-12 text-center">
            <p className="text-fg-soft text-[13px]">
              no results for &ldquo;{query}&rdquo;.
            </p>
          </div>
        </div>
      )}
    </>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={
      <div className="shell pt-12 text-fg-soft text-[13px]">loading…</div>
    }>
      <SearchContent />
    </Suspense>
  );
}
