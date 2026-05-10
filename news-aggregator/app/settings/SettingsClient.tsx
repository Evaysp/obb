'use client';

import Link from 'next/link';
import { useState } from 'react';
import { api, ApiError, type AIProvider, type AppSettings } from '@/lib/api';
import type { Entity } from '@/lib/types';
import { EntityTrackingSection } from './EntityTrackingSection';

const PROVIDERS: { v: AIProvider; label: string; hint: string; modelHint: string }[] = [
  { v: 'anthropic', label: 'Anthropic Claude', hint: 'sk-ant-…', modelHint: 'e.g. claude-sonnet-4-6, claude-opus-4-7' },
  { v: 'openai',    label: 'OpenAI',           hint: 'sk-…',     modelHint: 'e.g. gpt-4o, gpt-4o-mini, o1-mini' },
  { v: 'deepseek',  label: 'DeepSeek',         hint: 'sk-…',     modelHint: 'e.g. deepseek-chat, deepseek-reasoner' },
  { v: 'minimax',   label: 'Minimax',          hint: 'eyJ…',     modelHint: 'e.g. MiniMax-M2.7, MiniMax-Text-01' },
];

interface SettingsClientProps {
  initial: AppSettings;
  initialEntities: Entity[];
}

export function SettingsClient({ initial, initialEntities }: SettingsClientProps) {
  const [defaults, setDefaults] = useState<AppSettings>(initial);
  const [defaultProvider, setDefaultProvider] = useState<AIProvider>(initial.defaultProvider);
  const [customPrompt, setCustomPrompt] = useState<string>(initial.customPrompt ?? '');
  const [keys, setKeys] = useState<Record<AIProvider, string>>({
    anthropic: '',
    openai: '',
    deepseek: '',
    minimax: '',
  });
  const [models, setModels] = useState<Record<AIProvider, string>>({
    anthropic: initial.modelOverrides.anthropic ?? '',
    openai:    initial.modelOverrides.openai    ?? '',
    deepseek:  initial.modelOverrides.deepseek  ?? '',
    minimax:   initial.modelOverrides.minimax   ?? '',
  });
  const [endpoints, setEndpoints] = useState<Record<AIProvider, string>>({
    anthropic: initial.endpointOverrides.anthropic ?? '',
    openai:    initial.endpointOverrides.openai    ?? '',
    deepseek:  initial.endpointOverrides.deepseek  ?? '',
    minimax:   initial.endpointOverrides.minimax   ?? '',
  });
  const [reveal, setReveal] = useState<Record<AIProvider, boolean>>({
    anthropic: false, openai: false, deepseek: false, minimax: false,
  });
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<'idle' | 'ok' | 'error'>('idle');
  const [message, setMessage] = useState('');

  function isConfigured(p: AIProvider) {
    return defaults.configuredProviders.includes(p);
  }

  async function save() {
    setBusy(true);
    setStatus('idle');
    setMessage('');

    const apiKeys: Partial<Record<AIProvider, string | null>> = {};
    for (const p of Object.keys(keys) as AIProvider[]) {
      if (keys[p].trim()) apiKeys[p] = keys[p].trim();
    }

    // Send every model field — empty string means "clear override".
    // Only include providers whose value differs from the saved override
    // so we don't overwrite something we didn't intend to.
    const modelDiffs: Partial<Record<AIProvider, string | null>> = {};
    for (const p of Object.keys(models) as AIProvider[]) {
      const next = models[p].trim();
      const prev = (defaults.modelOverrides[p] ?? '').trim();
      if (next !== prev) modelDiffs[p] = next === '' ? null : next;
    }

    const endpointDiffs: Partial<Record<AIProvider, string | null>> = {};
    for (const p of Object.keys(endpoints) as AIProvider[]) {
      const next = endpoints[p].trim();
      const prev = (defaults.endpointOverrides[p] ?? '').trim();
      if (next !== prev) endpointDiffs[p] = next === '' ? null : next;
    }

    const promptChanged = customPrompt.trim() !== (defaults.customPrompt ?? '').trim();
    const clearPrompt = customPrompt.trim() === '' && !!defaults.customPrompt;

    try {
      const updated = await api.updateSettings({
        defaultProvider,
        customPrompt: promptChanged && !clearPrompt ? customPrompt : undefined,
        clearCustomPrompt: clearPrompt,
        apiKeys: Object.keys(apiKeys).length > 0 ? apiKeys : undefined,
        models: Object.keys(modelDiffs).length > 0 ? modelDiffs : undefined,
        endpoints: Object.keys(endpointDiffs).length > 0 ? endpointDiffs : undefined,
      });
      setDefaults(updated);
      setKeys({ anthropic: '', openai: '', deepseek: '', minimax: '' });
      setModels({
        anthropic: updated.modelOverrides.anthropic ?? '',
        openai:    updated.modelOverrides.openai    ?? '',
        deepseek:  updated.modelOverrides.deepseek  ?? '',
        minimax:   updated.modelOverrides.minimax   ?? '',
      });
      setEndpoints({
        anthropic: updated.endpointOverrides.anthropic ?? '',
        openai:    updated.endpointOverrides.openai    ?? '',
        deepseek:  updated.endpointOverrides.deepseek  ?? '',
        minimax:   updated.endpointOverrides.minimax   ?? '',
      });
      setStatus('ok');
      setMessage('▸ saved');
    } catch (err) {
      setStatus('error');
      if (err instanceof ApiError) setMessage(`${err.code}: ${err.message}`);
      else if (err instanceof Error) setMessage(err.message);
      else setMessage('save failed');
    } finally {
      setBusy(false);
    }
  }

  async function clearKey(p: AIProvider) {
    setBusy(true);
    setStatus('idle');
    try {
      const updated = await api.updateSettings({ apiKeys: { [p]: null } });
      setDefaults(updated);
      setStatus('ok');
      setMessage(`▸ cleared ${p} key`);
    } catch (err) {
      setStatus('error');
      setMessage(err instanceof Error ? err.message : 'clear failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <section className="shell pt-7 pb-5 border-b border-line">
        <div className="flex items-baseline gap-2 text-[13px] mb-3">
          <span className="text-mark font-bold">$</span>
          <span className="text-fg">
            observer config <span className="text-mark">--ai</span>
          </span>
        </div>
        <h1 className="font-mono text-[24px] font-semibold text-fg leading-tight m-0">
          settings <span className="text-mark">·</span> ai providers
        </h1>
        <p className="text-fg-soft text-[13px] leading-[1.6] max-w-[76ch] mt-2">
          Add an API key for any provider you want to use. Keys are encrypted
          (Fernet) at rest in the same database column scheme as your cookies.
          They&rsquo;re never sent back to the browser — only{' '}
          <span className="text-mark">[ configured ]</span> markers.
        </p>
      </section>

      <section className="shell py-6 max-w-[860px]">
        {/* default provider */}
        <Block title="default provider" hint="used by the AI Brief panel on the home page when you click summarize">
          <div className="flex flex-wrap gap-1 border border-line w-fit">
            {PROVIDERS.map((p, i) => {
              const on = defaultProvider === p.v;
              const conf = isConfigured(p.v);
              return (
                <button
                  key={p.v}
                  type="button"
                  onClick={() => setDefaultProvider(p.v)}
                  className={[
                    'px-3 py-1 text-[12px] transition-colors',
                    i < PROVIDERS.length - 1 ? 'border-r border-line' : '',
                    on ? 'bg-mark text-bg font-semibold' : 'text-fg-soft hover:text-fg',
                  ].join(' ')}
                  title={conf ? '' : 'no key configured'}
                >
                  {p.label}{conf ? '' : ' ·'}
                </button>
              );
            })}
          </div>
        </Block>

        {/* api keys + per-provider model */}
        <Block title="providers" hint="api key (encrypted at rest) + model id. leave model blank to use the built-in default.">
          <div className="grid gap-3">
            {PROVIDERS.map((p) => {
              const conf = isConfigured(p.v);
              const fallbackModel = defaults.defaultModels[p.v];
              const overrideModel = defaults.modelOverrides[p.v];
              return (
                <div
                  key={p.v}
                  className="border border-line p-3 bg-bg-elev grid gap-2"
                >
                  <div className="flex items-baseline justify-between gap-3 flex-wrap">
                    <div className="flex items-baseline gap-3">
                      <span className="text-[12px] text-fg font-semibold">{p.label}</span>
                      <span className="text-[10px] uppercase tracking-[0.12em] text-fg-faint">
                        {conf ? '▸ configured' : '◌ not set'}
                      </span>
                    </div>
                    {conf && (
                      <button
                        type="button"
                        onClick={() => clearKey(p.v)}
                        disabled={busy}
                        className="text-[10px] uppercase tracking-[0.1em] text-fg-faint hover:text-hot border border-line hover:border-hot px-2 py-0.5"
                      >
                        clear key
                      </button>
                    )}
                  </div>

                  <label className="grid grid-cols-1 md:grid-cols-[110px_1fr_auto] gap-2 md:gap-3 items-center">
                    <span className="text-[10px] uppercase tracking-[0.14em] text-fg-faint">
                      api key
                    </span>
                    <input
                      type={reveal[p.v] ? 'text' : 'password'}
                      value={keys[p.v]}
                      onChange={(e) => setKeys({ ...keys, [p.v]: e.target.value })}
                      placeholder={conf ? '(replace) ' + p.hint : p.hint}
                      autoComplete="new-password"
                      spellCheck={false}
                      className="min-w-0 bg-bg border border-line text-fg-soft text-[12px] px-2 py-1 outline-none focus:border-mark-soft font-mono"
                    />
                    <button
                      type="button"
                      onClick={() => setReveal({ ...reveal, [p.v]: !reveal[p.v] })}
                      className="text-fg-faint hover:text-fg text-[10px] uppercase tracking-[0.08em] px-1.5"
                      tabIndex={-1}
                    >
                      {reveal[p.v] ? 'hide' : 'show'}
                    </button>
                  </label>

                  <label className="grid grid-cols-1 md:grid-cols-[110px_1fr_auto] gap-2 md:gap-3 items-center">
                    <span className="text-[10px] uppercase tracking-[0.14em] text-fg-faint">
                      model
                    </span>
                    <input
                      type="text"
                      value={models[p.v]}
                      onChange={(e) => setModels({ ...models, [p.v]: e.target.value })}
                      placeholder={p.modelHint}
                      spellCheck={false}
                      className="min-w-0 bg-bg border border-line text-fg-soft text-[12px] px-2 py-1 outline-none focus:border-mark-soft font-mono"
                    />
                    <span className="text-[10px] uppercase tracking-[0.08em] text-fg-faint num-tabular">
                      {overrideModel
                        ? <>active <span className="text-mark">{overrideModel}</span></>
                        : <>default <span className="text-fg">{fallbackModel}</span></>}
                    </span>
                  </label>

                  <label className="grid grid-cols-1 md:grid-cols-[110px_1fr_auto] gap-2 md:gap-3 items-center">
                    <span className="text-[10px] uppercase tracking-[0.14em] text-fg-faint">
                      endpoint
                    </span>
                    <input
                      type="text"
                      value={endpoints[p.v]}
                      onChange={(e) => setEndpoints({ ...endpoints, [p.v]: e.target.value })}
                      placeholder={defaults.defaultEndpoints[p.v]}
                      spellCheck={false}
                      className="min-w-0 bg-bg border border-line text-fg-soft text-[11px] px-2 py-1 outline-none focus:border-mark-soft font-mono"
                    />
                    <span className="text-[10px] uppercase tracking-[0.08em] text-fg-faint">
                      {defaults.endpointOverrides[p.v] ? (
                        <span className="text-mark">overridden</span>
                      ) : (
                        <span>default</span>
                      )}
                    </span>
                  </label>
                </div>
              );
            })}
          </div>
        </Block>

        {/* custom prompt */}
        <Block
          title="custom prompt"
          hint="leave empty to use the default. include {articles} where the article list should be inserted (auto-appended if missing)."
        >
          <textarea
            value={customPrompt}
            onChange={(e) => setCustomPrompt(e.target.value)}
            spellCheck={false}
            placeholder="(empty → use default, shown below)"
            className="w-full h-56 p-3 bg-bg-elev border border-line text-fg text-[12px] font-mono leading-relaxed outline-none focus:border-mark-soft"
          />
          <details className="mt-2">
            <summary className="text-[10px] uppercase tracking-[0.16em] text-fg-faint cursor-pointer hover:text-fg-soft">
              ▸ view default prompt
            </summary>
            <pre className="mt-2 p-3 bg-bg-elev border border-line text-fg-soft text-[11px] font-mono whitespace-pre-wrap leading-relaxed">
              {defaults.defaultPrompt}
            </pre>
          </details>
        </Block>

        {/* save */}
        <div className="flex items-center gap-3 mt-6 flex-wrap">
          <button
            type="button"
            onClick={save}
            disabled={busy}
            className="px-4 py-1.5 bg-mark text-bg text-[12px] font-semibold uppercase tracking-[0.08em] hover:bg-mark-soft transition-colors disabled:opacity-40"
          >
            {busy ? '…saving' : '▸ save settings'}
          </button>
          <Link
            href="/"
            className="text-[12px] uppercase tracking-[0.08em] text-fg-soft hover:text-mark"
          >
            ◂ back to brief
          </Link>
          {status !== 'idle' && (
            <span
              className={[
                'ml-auto text-[12px]',
                status === 'ok' ? 'text-mark' : 'text-hot',
              ].join(' ')}
            >
              {message}
            </span>
          )}
        </div>

        {/* ── Tracking (people / companies) ── */}
        <Block
          title="tracking"
          hint="follow people or companies. articles mentioning them surface across sources and languages, and fire push notifications when subscribers are wired up."
        >
          <EntityTrackingSection initialEntities={initialEntities} />
        </Block>
      </section>
    </>
  );
}

function Block({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mt-6 first:mt-0">
      <div className="text-[10px] tracking-[0.16em] uppercase text-fg-faint mb-1.5">
        <span className="text-mark">▸</span> {title}
      </div>
      {hint && (
        <div className="text-fg-faint text-[11px] mb-3 max-w-[68ch]">{hint}</div>
      )}
      {children}
    </div>
  );
}
