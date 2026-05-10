import Link from 'next/link';
import { api } from '@/lib/api';
import type { Source } from '@/lib/types';
import { timeAgo } from '@/lib/utils';
import { AddSourceForm } from './AddSourceForm';

export const dynamic = 'force-dynamic';

export default async function SourcesPage() {
  let sources: Source[];
  try {
    sources = await api.getSources();
  } catch {
    return <BackendOffline />;
  }

  const enabled = sources.filter((s) => s.enabled);
  const disabled = sources.filter((s) => !s.enabled);
  const paywalled = sources.filter((s) => s.tier === 'paywall').length;

  return (
    <>
      <section className="shell pt-7 pb-5 border-b border-line">
        <div className="flex items-baseline gap-2 text-[13px] mb-3">
          <span className="text-mark font-bold">$</span>
          <span className="text-fg">observer sources <span className="text-mark">--all</span></span>
        </div>
        <h1 className="font-mono text-[24px] font-semibold text-fg leading-tight m-0">
          {sources.length} {sources.length === 1 ? 'source' : 'sources'}{' '}
          <span className="text-mark">·</span> {paywalled} paywalled
        </h1>
        <p className="text-fg-soft text-[13px] leading-[1.6] max-w-[76ch] mt-2">
          Manage the feeds you pull from. Cookies for paywalled sites are stored
          encrypted per-source and rotated when they expire.
        </p>
      </section>

      <section className="shell py-6">
        <div className="mb-6">
          <AddSourceForm />
        </div>
        <Section title="active" count={enabled.length} sources={enabled} />
        {disabled.length > 0 && (
          <Section title="disabled" count={disabled.length} sources={disabled} dim />
        )}
      </section>
    </>
  );
}

function Section({
  title,
  count,
  sources,
  dim = false,
}: {
  title: string;
  count: number;
  sources: Source[];
  dim?: boolean;
}) {
  return (
    <div className={dim ? 'mt-10 opacity-60' : 'mt-2'}>
      <div className="flex items-baseline gap-2 mb-3 text-[11px] tracking-[0.12em] uppercase text-fg-soft">
        <span className="text-mark">▸</span>
        <span>{title}</span>
        <span className="sep">·</span>
        <span className="num-tabular text-fg-faint">{count}</span>
      </div>
      <div className="border border-line">
        {/* Header row */}
        <div className="hidden md:grid grid-cols-[40px_1.4fr_60px_60px_60px_1fr_140px_60px] gap-3 px-3 py-2 border-b border-line bg-bg-elev text-[10px] tracking-[0.14em] uppercase text-fg-faint num-tabular">
          <span>kind</span>
          <span>name</span>
          <span>lang</span>
          <span>region</span>
          <span>tier</span>
          <span>cookies</span>
          <span>last fetch</span>
          <span className="text-right">24h</span>
        </div>
        {sources.map((s, i) => (
          <SourceRow key={s.slug} source={s} index={i + 1} />
        ))}
      </div>
    </div>
  );
}

function SourceRow({ source, index }: { source: Source; index: number }) {
  const cookieStatus = source.needsCookies ? source.cookieStatus ?? 'missing' : null;

  return (
    <div className="grid md:grid-cols-[40px_1.4fr_60px_60px_60px_1fr_140px_60px] gap-3 px-3 py-2.5 border-b last:border-b-0 border-line text-[12px] hover:bg-[color-mix(in_oklch,var(--mark)_4%,transparent)] transition-colors">
      <span className="text-fg-faint num-tabular hidden md:inline">
        {String(index).padStart(2, '0')}
      </span>
      <div className="min-w-0">
        <Link
          href={`/sources/${source.slug}`}
          className="text-fg font-semibold truncate block hover:text-mark transition-colors"
        >
          {source.name}
        </Link>
        {source.nameLocal && source.nameLocal !== source.name && (
          <Link
            href={`/sources/${source.slug}`}
            className="text-fg-faint text-[11px] truncate block hover:text-mark transition-colors"
          >
            {source.nameLocal}
          </Link>
        )}
        <div className="md:hidden mt-1 flex items-center gap-2 text-[11px] text-fg-soft num-tabular">
          <span className="text-mark">{source.lang.toUpperCase()}</span>
          <span className="sep">·</span>
          <span>{source.region}</span>
          <span className="sep">·</span>
          <span className={source.tier === 'paywall' ? 'text-warn' : ''}>
            {source.tier}
          </span>
          <span className="sep">·</span>
          <time>{source.lastFetchedAt ? timeAgo(source.lastFetchedAt) : '—'}</time>
        </div>
      </div>
      <span className="hidden md:inline text-mark">{source.lang.toUpperCase()}</span>
      <span className="hidden md:inline text-fg-soft num-tabular">{source.region}</span>
      <span className={[
        'hidden md:inline',
        source.tier === 'paywall' ? 'text-warn' : 'text-fg-soft',
      ].join(' ')}>
        {source.tier}
      </span>
      <span className="hidden md:inline">
        {cookieStatus ? <CookieStatus status={cookieStatus} slug={source.slug} /> : <span className="text-fg-faint">—</span>}
      </span>
      <time className="hidden md:inline text-fg-soft num-tabular">
        {source.lastFetchedAt ? timeAgo(source.lastFetchedAt) : '—'}
      </time>
      <span className="text-right text-fg num-tabular font-semibold">
        {source.articleCount24h}
      </span>
    </div>
  );
}

function CookieStatus({
  status,
  slug,
}: {
  status: 'missing' | 'ok' | 'expiring' | 'expired';
  slug: string;
}) {
  const labels = {
    ok: { text: 'valid', class: 'text-fg' },
    expiring: { text: 'renew soon', class: 'text-warn' },
    expired: { text: 'expired', class: 'text-hot' },
    missing: { text: 'missing', class: 'text-fg-faint' },
  };
  const meta = labels[status];

  return (
    <Link
      href={`/sources/${slug}/cookies`}
      className={['inline-flex items-center gap-1.5 hover:text-mark transition-colors', meta.class].join(' ')}
    >
      <span className="inline-block w-1.5 h-1.5" style={{
        background:
          status === 'ok' ? 'var(--mark)' :
          status === 'expiring' ? 'var(--warn)' :
          status === 'expired' ? 'var(--hot)' :
          'var(--fg-faint)',
      }} />
      <span>{meta.text}</span>
    </Link>
  );
}

function BackendOffline() {
  return (
    <div className="shell pt-12">
      <div className="flex items-baseline gap-2 text-[13px] mb-4">
        <span className="text-hot font-bold">!</span>
        <span className="text-hot">backend unreachable</span>
      </div>
      <h1 className="font-mono text-[24px] font-semibold mb-3">
        Couldn&rsquo;t reach <code className="text-mark">/api/sources</code>.
      </h1>
      <p className="text-fg-soft text-[13px]">
        Start the backend (uvicorn / docker compose) and refresh.
      </p>
    </div>
  );
}
