'use client';

import { useTranslation } from './TranslationProvider';

export function TranslateToggle() {
  const { enabled, setEnabled, loading, error, translations } = useTranslation();
  const cachedCount = Object.keys(translations).length;

  return (
    <span className="flex items-center gap-2">
      <button
        type="button"
        onClick={() => setEnabled(!enabled)}
        title={
          error
            ? `translation error: ${error}`
            : enabled
            ? `showing Chinese translations · ${cachedCount} cached · click to revert`
            : 'click to translate articles to Chinese'
        }
        className={[
          'flex items-center gap-1 text-[11px] tracking-[0.06em] uppercase transition-colors',
          error
            ? 'text-hot'
            : enabled
            ? 'text-mark'
            : 'text-fg-faint hover:text-fg',
        ].join(' ')}
      >
        <span className={loading ? 'inline-block animate-spin' : ''}>
          {loading ? '⟳' : '中'}
        </span>
        <span>{enabled ? 'zh' : 'orig'}</span>
        {enabled && cachedCount > 0 && !loading && (
          <span className="text-fg-faint num-tabular normal-case tracking-normal">
            ·{cachedCount}
          </span>
        )}
      </button>
      {error && (
        <span
          className="text-hot text-[10px] normal-case tracking-normal max-w-[260px] truncate"
          title={error}
        >
          ! {error}
        </span>
      )}
    </span>
  );
}
