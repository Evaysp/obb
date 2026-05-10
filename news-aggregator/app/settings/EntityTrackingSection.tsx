'use client';

import { useState, useMemo } from 'react';
import { api } from '@/lib/api';
import type { Entity } from '@/lib/types';

interface Props { initialEntities: Entity[]; }

/**
 * Embeddable entity-tracking table — used inside the Settings page.
 * (Previously lived as the body of /subscriptions; that route has moved
 * to a source-grid view, so the entity follow/unfollow controls now
 * live here as one of several settings sections.)
 */
export function EntityTrackingSection({ initialEntities }: Props) {
  const [entities, setEntities] = useState<Entity[]>(initialEntities);
  const [tab, setTab] = useState<'subscribed' | 'all'>('subscribed');
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState<string | null>(null);

  const list = useMemo(() => {
    const q = query.trim().toLowerCase();
    return entities.filter((e) => {
      if (tab === 'subscribed' && !e.subscribed) return false;
      if (q) {
        const hay = [e.canonicalName, e.nameLocal ?? '', ...e.aliases].join('|').toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [tab, query, entities]);

  const subscribedCount = entities.filter((e) => e.subscribed).length;

  async function toggleSubscription(slug: string, currentlySubscribed: boolean) {
    setBusy(slug);
    try {
      if (currentlySubscribed) await api.unsubscribe(slug);
      else await api.subscribe(slug);
      setEntities((prev) =>
        prev.map((e) => (e.slug === slug ? { ...e, subscribed: !currentlySubscribed } : e)),
      );
    } catch (err) {
      console.error('subscription toggle failed', err);
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-center gap-3 mb-4 text-[12px]">
        <div className="flex border border-line">
          <button
            onClick={() => setTab('subscribed')}
            className={[
              'px-3 py-1 transition-colors',
              tab === 'subscribed'
                ? 'bg-mark text-bg font-semibold'
                : 'text-fg-soft hover:text-fg',
            ].join(' ')}
          >
            subscribed · {subscribedCount}
          </button>
          <button
            onClick={() => setTab('all')}
            className={[
              'px-3 py-1 border-l border-line transition-colors',
              tab === 'all'
                ? 'bg-mark text-bg font-semibold'
                : 'text-fg-soft hover:text-fg',
            ].join(' ')}
          >
            all · {entities.length}
          </button>
        </div>

        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="filter by name or alias…"
          className="flex-1 min-w-[200px] max-w-[420px] px-2.5 py-1 bg-bg-elev border border-line text-[12px] text-fg outline-none focus:border-mark-soft placeholder:text-fg-faint"
        />

        <span className="ml-auto text-fg-faint num-tabular text-[11px]">
          {list.length} of {entities.length} shown
        </span>
      </div>

      {list.length === 0 ? (
        <div className="border border-dashed border-line py-12 text-center">
          <p className="text-fg-soft text-[13px]">
            {tab === 'subscribed' ? 'no subscriptions yet.' : 'no entities match.'}
          </p>
          {tab === 'subscribed' && (
            <button
              onClick={() => setTab('all')}
              className="mt-3 text-[11px] text-mark uppercase tracking-[0.12em] hover:underline"
            >
              ▸ browse all entities
            </button>
          )}
        </div>
      ) : (
        <div className="border border-line">
          <div className="hidden md:grid grid-cols-[40px_1.6fr_60px_80px_1fr_80px] gap-3 px-3 py-2 border-b border-line bg-bg-elev text-[10px] tracking-[0.14em] uppercase text-fg-faint">
            <span>idx</span>
            <span>name</span>
            <span>kind</span>
            <span className="text-right">7d</span>
            <span>aliases</span>
            <span className="text-right">action</span>
          </div>
          {list.map((e, i) => (
            <EntityRow
              key={e.slug}
              entity={e}
              index={i + 1}
              busy={busy === e.slug}
              onToggle={() => toggleSubscription(e.slug, e.subscribed)}
            />
          ))}
        </div>
      )}
    </>
  );
}

function EntityRow({
  entity, index, busy, onToggle,
}: {
  entity: Entity; index: number; busy: boolean; onToggle: () => void;
}) {
  return (
    <div className="grid md:grid-cols-[40px_1.6fr_60px_80px_1fr_80px] gap-3 px-3 py-3 border-b last:border-b-0 border-line text-[12px] hover:bg-[color-mix(in_oklch,var(--mark)_4%,transparent)] transition-colors">
      <span className="hidden md:inline text-fg-faint num-tabular">
        {String(index).padStart(2, '0')}
      </span>
      <div className="min-w-0">
        <div className="text-fg font-semibold truncate">{entity.canonicalName}</div>
        {entity.nameLocal && entity.nameLocal !== entity.canonicalName && (
          <div className="font-serif italic text-fg-soft text-[13px] truncate"
               style={{ fontVariationSettings: '"opsz" 14' }}>
            {entity.nameLocal}
          </div>
        )}
        {entity.description && (
          <div className="text-fg-faint text-[11px] truncate mt-0.5">
            {entity.description}
          </div>
        )}
      </div>
      <span className="hidden md:inline text-fg-soft">{entity.kind}</span>
      <span className="hidden md:inline text-right text-fg num-tabular font-semibold">
        {entity.articleCount7d}
      </span>
      <div className="hidden md:flex flex-wrap gap-1 items-start min-w-0">
        {entity.aliases.slice(0, 4).map((a) => (
          <span key={a} className="text-fg-faint text-[11px] truncate">
            {a}
          </span>
        ))}
      </div>
      <div className="md:text-right">
        <button
          onClick={onToggle}
          disabled={busy}
          className={[
            'px-2 py-0.5 text-[11px] uppercase tracking-[0.08em] border transition-colors disabled:opacity-50',
            entity.subscribed
              ? 'bg-mark text-bg border-mark font-semibold hover:bg-mark-soft'
              : 'border-line text-fg-soft hover:border-mark hover:text-mark',
          ].join(' ')}
          aria-label={entity.subscribed ? 'Unsubscribe' : 'Subscribe'}
        >
          {entity.subscribed ? '▸ on' : '+ track'}
        </button>
      </div>
    </div>
  );
}
