'use client';

import { useRouter, usePathname, useSearchParams } from 'next/navigation';
import type { Lang } from '@/lib/types';
import { ViewSwitch } from './ViewSwitch';

type Tier = 'all' | 'free' | 'paywall';

interface Props {
  initial: {
    lang: Lang | 'all';
    region: string | 'all';
    tier: Tier;
  };
  totalCount: number;
  filteredCount: number;
}

export function FilterBarClient({ initial, totalCount, filteredCount }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  function setFilter(key: 'lang' | 'region' | 'tier', value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value === 'all') params.delete(key);
    else params.set(key, value);
    const qs = params.toString();
    router.push(qs ? `${pathname}?${qs}` : pathname);
  }

  return (
    <div className="border-b border-line">
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-3 py-3 text-[12px]">
        <Flag
          name="--lang"
          options={[
            { v: 'all', label: 'all' },
            { v: 'en',  label: 'en' },
            { v: 'ja',  label: 'ja' },
            { v: 'zh',  label: 'zh' },
          ]}
          current={initial.lang}
          onSelect={(v) => setFilter('lang', v)}
        />
        <Flag
          name="--region"
          options={[
            { v: 'all', label: 'all' },
            { v: 'UK',  label: 'uk' },
            { v: 'US',  label: 'us' },
            { v: 'JP',  label: 'jp' },
            { v: 'CN',  label: 'cn' },
            { v: 'HK',  label: 'hk' },
          ]}
          current={initial.region}
          onSelect={(v) => setFilter('region', v)}
        />
        <Flag
          name="--tier"
          options={[
            { v: 'all',     label: 'all' },
            { v: 'free',    label: 'free' },
            { v: 'paywall', label: 'paywall' },
          ]}
          current={initial.tier}
          onSelect={(v) => setFilter('tier', v)}
        />

        <div className="ml-auto flex items-center gap-4 text-fg-faint num-tabular">
          <span>
            <span className="text-fg font-medium">{filteredCount}</span> /{' '}
            <span className="text-fg font-medium">{totalCount}</span> rows
          </span>
          <ViewSwitch />
        </div>
      </div>
    </div>
  );
}

interface FlagProps {
  name: string;
  options: { v: string; label: string }[];
  current: string;
  onSelect: (v: string) => void;
}

function Flag({ name, options, current, onSelect }: FlagProps) {
  return (
    <div className="flex items-baseline gap-1">
      <span className="text-fg-faint">{name}</span>
      <span className="text-fg-faint">=</span>
      <span className="flex gap-0.5">
        {options.map((o) => {
          const on = o.v === current;
          return (
            <button
              key={o.v}
              type="button"
              onClick={() => onSelect(o.v)}
              className={[
                'px-1.5 py-px border transition-colors',
                on
                  ? 'text-mark border-mark-soft bg-[color-mix(in_oklch,var(--mark)_8%,transparent)]'
                  : 'text-fg-soft border-transparent hover:text-fg',
              ].join(' ')}
            >
              {o.label}
            </button>
          );
        })}
      </span>
    </div>
  );
}

