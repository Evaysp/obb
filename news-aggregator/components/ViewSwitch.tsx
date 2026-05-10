'use client';

import { useView, type View } from './ViewProvider';

const VIEWS: { v: View; label: string; title: string }[] = [
  { v: 'list',    label: '▤ list',  title: 'List view (1)' },
  { v: 'grid',    label: '▦ grid',  title: 'Grid view (2)' },
  { v: 'compact', label: '≡ cmpct', title: 'Compact view (3)' },
];

/**
 * Reads/writes view from ViewProvider context — drop in anywhere.
 * Used on the home feed (inside FilterBarClient) and on /sources/[slug].
 */
export function ViewSwitch() {
  const { view, setView } = useView();
  return (
    <div className="flex border border-line">
      {VIEWS.map((vw, i) => {
        const on = vw.v === view;
        return (
          <button
            key={vw.v}
            type="button"
            onClick={() => setView(vw.v)}
            title={vw.title}
            className={[
              'px-2 py-px text-[11px]',
              i < VIEWS.length - 1 ? 'border-r border-line' : '',
              on
                ? 'bg-mark text-bg font-semibold'
                : 'text-fg-soft hover:text-fg',
            ].join(' ')}
          >
            {vw.label}
          </button>
        );
      })}
    </div>
  );
}
