'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, ApiError } from '@/lib/api';
import type { Lang } from '@/lib/types';

const LANGS: { v: Lang; label: string }[] = [
  { v: 'en', label: 'en · English' },
  { v: 'ja', label: 'ja · 日本語' },
  { v: 'zh', label: 'zh · 中文' },
];

const REGIONS = ['UK', 'US', 'JP', 'CN', 'HK', 'EU', 'INTL'];

export function AddSourceForm() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<'idle' | 'ok' | 'error'>('idle');
  const [message, setMessage] = useState('');

  const [name, setName] = useState('');
  const [feedUrl, setFeedUrl] = useState('');
  const [lang, setLang] = useState<Lang>('en');
  const [region, setRegion] = useState('US');
  const [nameLocal, setNameLocal] = useState('');

  function clearFields() {
    setName('');
    setFeedUrl('');
    setLang('en');
    setRegion('US');
    setNameLocal('');
  }

  function reset() {
    clearFields();
    setStatus('idle');
    setMessage('');
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setStatus('idle');
    setMessage('');
    try {
      const src = await api.createSource({
        name: name.trim(),
        feedUrl: feedUrl.trim(),
        lang,
        region: region.trim().toUpperCase(),
        nameLocal: nameLocal.trim() || undefined,
      });
      clearFields();
      setStatus('ok');
      setMessage(`▸ added ${src.name} (${src.slug}) · feed validated`);
      router.refresh();
    } catch (err) {
      setStatus('error');
      if (err instanceof ApiError) setMessage(`${err.status} ${err.code}: ${err.message}`);
      else if (err instanceof Error) setMessage(err.message);
      else setMessage('failed to create source');
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-[12px] text-fg-soft hover:text-mark border border-line hover:border-mark px-3 py-1 transition-colors uppercase tracking-[0.08em]"
      >
        + add free rss source
      </button>
    );
  }

  return (
    <div className="border border-mark-soft bg-bg-elev mt-4">
      <div className="flex items-center justify-between px-3 py-2 border-b border-line text-[11px] tracking-[0.16em] uppercase">
        <span className="text-mark">▸ add rss source</span>
        <button
          type="button"
          onClick={() => { reset(); setOpen(false); }}
          className="text-fg-faint hover:text-fg"
          aria-label="Close"
        >
          × close
        </button>
      </div>

      <form onSubmit={handleSubmit} className="p-4 grid gap-3 text-[12px]">
        <Field label="--name" required hint="display name (e.g. The Verge)">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="The Verge"
            required
            className="input"
          />
        </Field>

        <Field
          label="--feed-url"
          required
          hint="https URL to the RSS / Atom feed; we'll fetch + parse it once to validate"
        >
          <input
            type="url"
            value={feedUrl}
            onChange={(e) => setFeedUrl(e.target.value)}
            placeholder="https://www.theverge.com/rss/index.xml"
            required
            className="input font-mono"
          />
        </Field>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Field label="--lang" required>
            <select
              value={lang}
              onChange={(e) => setLang(e.target.value as Lang)}
              className="input"
            >
              {LANGS.map((l) => (
                <option key={l.v} value={l.v}>{l.label}</option>
              ))}
            </select>
          </Field>

          <Field label="--region" required>
            <select
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              className="input"
            >
              {REGIONS.map((r) => <option key={r}>{r}</option>)}
            </select>
          </Field>

          <Field label="--name-local" hint="optional local-language name">
            <input
              type="text"
              value={nameLocal}
              onChange={(e) => setNameLocal(e.target.value)}
              placeholder="e.g. ザ・ヴァージ"
              className="input"
            />
          </Field>
        </div>

        {status !== 'idle' && (
          <div
            className={[
              'border px-3 py-2 text-[12px] flex items-start gap-2',
              status === 'ok' ? 'border-mark text-mark' : 'border-hot text-hot',
            ].join(' ')}
          >
            <span className="font-bold">{status === 'ok' ? '✓' : '!'}</span>
            <span className="leading-relaxed">{message}</span>
          </div>
        )}

        <div className="flex gap-3 mt-1">
          <button
            type="submit"
            disabled={busy || !name.trim() || !feedUrl.trim()}
            className="px-4 py-1.5 bg-mark text-bg text-[12px] font-semibold uppercase tracking-[0.08em] hover:bg-mark-soft transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {busy ? 'validating…' : '▸ create source'}
          </button>
          <button
            type="button"
            onClick={reset}
            disabled={busy}
            className="px-4 py-1.5 border border-line text-[12px] uppercase tracking-[0.08em] text-fg-soft hover:text-fg hover:border-fg transition-colors disabled:opacity-40"
          >
            clear
          </button>
        </div>

        <style jsx>{`
          .input {
            background: var(--bg);
            border: 1px solid var(--line);
            color: var(--fg);
            padding: 6px 8px;
            font-family: var(--font-mono), monospace;
            font-size: 12px;
            outline: none;
            width: 100%;
          }
          .input:focus { border-color: var(--mark-soft); }
          .input::placeholder { color: var(--fg-faint); }
        `}</style>
      </form>
    </div>
  );
}

function Field({
  label,
  required,
  hint,
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="flex items-baseline gap-2 mb-1">
        <span className="text-fg-faint text-[11px]">{label}</span>
        {required && <span className="text-hot text-[10px]">*</span>}
        {hint && <span className="text-fg-faint text-[10px] font-normal">{hint}</span>}
      </span>
      {children}
    </label>
  );
}
