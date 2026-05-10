'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { api, ApiError, type AIProvider, type AppSettings } from '@/lib/api';

const PROVIDER_LABELS: Record<AIProvider, string> = {
  anthropic: 'claude',
  openai: 'openai',
  deepseek: 'deepseek',
  minimax: 'minimax',
};

type Phase = 'idle' | 'running' | 'done' | 'error';

export function AISummary() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [provider, setProvider] = useState<AIProvider | ''>('');
  const [phase, setPhase] = useState<Phase>('idle');
  const [summary, setSummary] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [meta, setMeta] = useState<{ model: string; n: number; custom: boolean } | null>(null);
  const [showPromptEdit, setShowPromptEdit] = useState(false);
  const [oneShotPrompt, setOneShotPrompt] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const [modalOpen, setModalOpen] = useState(false);

  // Load settings on mount
  useEffect(() => {
    let cancelled = false;
    api.getSettings()
      .then((s) => {
        if (cancelled) return;
        setSettings(s);
        setProvider(s.defaultProvider);
      })
      .catch(() => { /* leave defaults */ });
    return () => { cancelled = true; };
  }, []);

  // Tick elapsed counter while running
  useEffect(() => {
    if (phase !== 'running') return;
    setElapsed(0);
    const start = Date.now();
    const id = window.setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => window.clearInterval(id);
  }, [phase]);

  // Lock body scroll while modal open
  useEffect(() => {
    if (!modalOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [modalOpen]);

  // ESC to close modal
  useEffect(() => {
    if (!modalOpen) return;
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') setModalOpen(false); }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [modalOpen]);

  async function handleSummarize() {
    if (!provider) return;
    setPhase('running');
    setError('');
    setSummary('');
    setMeta(null);
    try {
      const r = await api.summarize({
        provider,
        customPrompt: oneShotPrompt.trim() || undefined,
      });
      setSummary(r.summary);
      setMeta({ model: r.model, n: r.articleCount, custom: r.usedCustomPrompt });
      setPhase('done');
      setModalOpen(true); // auto-open the result
    } catch (err) {
      setPhase('error');
      if (err instanceof ApiError) setError(`${err.code}: ${err.message}`);
      else if (err instanceof Error) setError(err.message);
      else setError('failed');
    }
  }

  const noKey = !!settings && !!provider && !settings.configuredProviders.includes(provider);
  const canRun = !!provider && !noKey && phase !== 'running';
  const activeModel = provider
    ? settings?.modelOverrides?.[provider] ?? settings?.defaultModels?.[provider] ?? null
    : null;

  return (
    <>
      <div className="border border-line bg-bg-elev flex flex-col">
        {/* header */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-line text-[11px] tracking-[0.16em] uppercase">
          <span className="text-mark font-bold">▸ ai brief</span>
          <span className="flex items-center gap-3">
            {activeModel && (
              <span className="text-fg-faint normal-case tracking-normal text-[10px] num-tabular">
                <span className="text-mark">·</span> {activeModel}
              </span>
            )}
            <Link
              href="/settings"
              className="text-fg-faint hover:text-mark text-[10px]"
              title="Settings"
            >
              [ settings ]
            </Link>
          </span>
        </div>

        {/* controls */}
        <div className="px-3 py-2 border-b border-line text-[11px] flex flex-wrap items-center gap-2">
          <span className="text-fg-faint">--provider</span>
          <span className="text-fg-faint">=</span>
          <div className="flex border border-line">
            {(Object.keys(PROVIDER_LABELS) as AIProvider[]).map((p, i) => {
              const on = provider === p;
              const configured = settings?.configuredProviders.includes(p);
              return (
                <button
                  key={p}
                  type="button"
                  onClick={() => setProvider(p)}
                  title={configured ? `use ${p}` : `${p} — no key configured`}
                  className={[
                    'px-2 py-px transition-colors',
                    i < 3 ? 'border-r border-line' : '',
                    on ? 'bg-mark text-bg font-semibold' : 'text-fg-soft hover:text-fg',
                    !configured && !on ? 'opacity-50' : '',
                  ].join(' ')}
                >
                  {PROVIDER_LABELS[p]}
                  {configured ? '' : ' ·'}
                </button>
              );
            })}
          </div>
          <button
            type="button"
            onClick={() => setShowPromptEdit((x) => !x)}
            className="ml-auto text-fg-faint hover:text-fg text-[10px] uppercase tracking-[0.1em]"
          >
            {showPromptEdit ? '× close' : '✎ prompt'}
          </button>
        </div>

        {showPromptEdit && (
          <div className="px-3 py-2 border-b border-line text-[11px]">
            <div className="text-fg-faint text-[10px] uppercase tracking-[0.16em] mb-1.5">
              override prompt for this run
            </div>
            <textarea
              value={oneShotPrompt}
              onChange={(e) => setOneShotPrompt(e.target.value)}
              placeholder={settings?.customPrompt
                ? 'leave empty to use your saved prompt'
                : 'leave empty to use the default prompt — see /settings'}
              spellCheck={false}
              className="w-full h-20 p-2 bg-bg border border-line text-fg-soft text-[11px] outline-none focus:border-mark-soft resize-none"
            />
          </div>
        )}

        {/* status row (compact) */}
        <div className="px-3 py-2 text-[11px] min-h-[44px] flex items-center">
          <StatusLine
            phase={phase}
            settings={settings}
            provider={provider || ''}
            noKey={noKey}
            elapsed={elapsed}
            error={error}
            hasSummary={!!summary}
            meta={meta}
          />
        </div>

        {/* action row */}
        <div className="border-t border-line px-3 py-2 flex items-center gap-2 text-[11px] flex-wrap">
          <button
            type="button"
            onClick={handleSummarize}
            disabled={!canRun}
            className="px-3 py-1 bg-mark text-bg font-semibold uppercase tracking-[0.08em] hover:bg-mark-soft disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {phase === 'running' ? '…running' : phase === 'done' ? '↻ regenerate' : '▸ summarize today'}
          </button>
          {summary && (
            <button
              type="button"
              onClick={() => setModalOpen(true)}
              className="px-3 py-1 border border-mark-soft text-mark uppercase tracking-[0.08em] hover:bg-[color-mix(in_oklch,var(--mark)_10%,transparent)]"
            >
              ↗ view
            </button>
          )}
        </div>
      </div>

      {modalOpen && summary && (
        <SummaryModal
          summary={summary}
          meta={meta}
          provider={provider || ''}
          onClose={() => setModalOpen(false)}
          onRegenerate={() => { setModalOpen(false); handleSummarize(); }}
        />
      )}
    </>
  );
}

function StatusLine({
  phase, settings, provider, noKey, elapsed, error, hasSummary, meta,
}: {
  phase: Phase;
  settings: AppSettings | null;
  provider: string;
  noKey: boolean;
  elapsed: number;
  error: string;
  hasSummary: boolean;
  meta: { model: string; n: number; custom: boolean } | null;
}) {
  if (!settings) return <span className="text-fg-faint">loading…</span>;

  if (phase === 'running') {
    return (
      <span className="flex items-center gap-2 text-fg-soft">
        <span className="inline-block w-1.5 h-1.5 bg-mark obs-pulse" />
        <span className="text-mark uppercase tracking-[0.08em]">summarizing…</span>
        <span className="text-fg-faint num-tabular">{elapsed}s · 30–90s expected</span>
      </span>
    );
  }
  if (phase === 'error') {
    return (
      <span className="text-hot truncate" title={error}>
        ! {error}
      </span>
    );
  }
  if (phase === 'done' && hasSummary && meta) {
    return (
      <span className="flex items-center gap-2 text-fg-soft flex-wrap">
        <span className="text-mark uppercase tracking-[0.08em]">✓ ready</span>
        <span className="text-fg-faint num-tabular">
          {meta.n} articles · {meta.model}{meta.custom ? ' · custom prompt' : ''}
        </span>
      </span>
    );
  }
  // idle
  if (settings.configuredProviders.length === 0) {
    return (
      <span className="text-fg-soft">
        no providers configured · <Link href="/settings" className="text-mark underline">add a key</Link>
      </span>
    );
  }
  if (noKey) {
    return (
      <span className="text-fg-soft truncate">
        <span className="text-fg-faint">no key for</span>{' '}
        <span className="text-mark">{provider}</span>{' · '}
        <Link href="/settings" className="text-mark underline">add</Link>
      </span>
    );
  }
  return (
    <span className="text-fg-faint">
      click ▸ to summarize the last 24h · grouped by country, in 中文
    </span>
  );
}

// ─────────────────────────────────────────────────────────────
// Modal
// ─────────────────────────────────────────────────────────────
function SummaryModal({
  summary,
  meta,
  provider,
  onClose,
  onRegenerate,
}: {
  summary: string;
  meta: { model: string; n: number; custom: boolean } | null;
  provider: string;
  onClose: () => void;
  onRegenerate: () => void;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(summary);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch { /* ignore */ }
  }

  return (
    <div
      role="dialog"
      aria-modal
      className="fixed inset-0 z-50 flex items-center justify-center px-4 py-8"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/* backdrop */}
      <div
        className="absolute inset-0 bg-bg/85 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />

      {/* panel */}
      <div
        ref={panelRef}
        className="relative bg-bg-elev border border-mark-soft w-full max-w-3xl max-h-[85vh] flex flex-col shadow-[0_8px_40px_rgba(0,0,0,0.5)]"
      >
        {/* header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-line text-[11px] uppercase tracking-[0.14em]">
          <span className="text-mark font-bold">▸ ai brief</span>
          {meta && (
            <span className="text-fg-faint normal-case tracking-normal text-[11px] num-tabular truncate">
              {meta.n} articles · {provider} · {meta.model}{meta.custom ? ' · custom' : ''}
            </span>
          )}
          <button
            type="button"
            onClick={onClose}
            className="text-fg-faint hover:text-fg text-[11px]"
            aria-label="Close"
          >
            × close
          </button>
        </div>

        {/* body — scrollable markdown render */}
        <div className="flex-1 overflow-auto px-6 py-6">
          <Markdown text={summary} />
        </div>

        {/* footer */}
        <div className="border-t border-line px-4 py-2.5 flex items-center gap-2 text-[11px] flex-wrap">
          <button
            type="button"
            onClick={onRegenerate}
            className="px-3 py-1 bg-mark text-bg font-semibold uppercase tracking-[0.08em] hover:bg-mark-soft"
          >
            ↻ regenerate
          </button>
          <button
            type="button"
            onClick={copy}
            className="px-3 py-1 border border-line text-fg-soft hover:text-fg hover:border-fg uppercase tracking-[0.08em]"
          >
            {copied ? '✓ copied' : '⎘ copy'}
          </button>
          <span className="ml-auto text-fg-faint text-[10px] uppercase tracking-[0.12em]">
            esc · click outside · close
          </span>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Tiny markdown renderer — handles ## / ### / - / * / **bold**
// (no library; ~30 lines, good enough for our prompt's output shape)
// ─────────────────────────────────────────────────────────────
function Markdown({ text }: { text: string }) {
  const lines = text.split('\n');
  const blocks: React.ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const ln = lines[i];
    if (/^### /.test(ln)) {
      blocks.push(
        <h3 key={i} className="font-serif text-[18px] font-semibold mt-5 mb-2 text-fg"
            style={{ fontVariationSettings: '"opsz" 24' }}>
          {inline(ln.slice(4))}
        </h3>,
      );
      i++; continue;
    }
    if (/^## /.test(ln)) {
      blocks.push(
        <h2 key={i} className="font-serif text-[22px] font-semibold mt-7 mb-3 text-mark border-b border-line pb-1"
            style={{ fontVariationSettings: '"opsz" 28' }}>
          {inline(ln.slice(3))}
        </h2>,
      );
      i++; continue;
    }
    if (/^# /.test(ln)) {
      blocks.push(
        <h1 key={i} className="font-serif text-[26px] font-semibold mt-8 mb-3 text-fg"
            style={{ fontVariationSettings: '"opsz" 32' }}>
          {inline(ln.slice(2))}
        </h1>,
      );
      i++; continue;
    }
    // collect consecutive bullet lines
    if (/^\s*[-*]\s+/.test(ln)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, ''));
        i++;
      }
      blocks.push(
        <ul key={`u${i}`} className="font-serif text-[15px] leading-[1.7] my-2 ml-5 list-disc text-fg"
            style={{ fontVariationSettings: '"opsz" 16' }}>
          {items.map((it, k) => (
            <li key={k} className="my-1.5 marker:text-fg-faint">{inline(it)}</li>
          ))}
        </ul>,
      );
      continue;
    }
    if (ln.trim() === '') {
      i++; continue;
    }
    // paragraph (collect until blank line)
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() !== '' && !/^[#-]/.test(lines[i])) {
      para.push(lines[i]);
      i++;
    }
    blocks.push(
      <p key={`p${i}`} className="font-serif text-[15px] leading-[1.7] my-3 text-fg"
         style={{ fontVariationSettings: '"opsz" 16' }}>
        {inline(para.join(' '))}
      </p>,
    );
  }
  return <>{blocks}</>;
}

function inline(s: string): React.ReactNode {
  // **bold** + `code` minimal; everything else passes through
  const parts: React.ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = re.exec(s)) !== null) {
    if (m.index > last) parts.push(s.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith('**')) {
      parts.push(<strong key={key++} className="font-semibold text-fg">{tok.slice(2, -2)}</strong>);
    } else {
      parts.push(<code key={key++} className="font-mono text-[0.92em] bg-bg-elev border border-line px-1">{tok.slice(1, -1)}</code>);
    }
    last = m.index + tok.length;
  }
  if (last < s.length) parts.push(s.slice(last));
  return parts;
}
