'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const items = [
  { href: '/',              label: 'brief' },
  { href: '/sources',       label: 'sources' },
  { href: '/subscriptions', label: 'subscriptions' },
  { href: '/search',        label: 'search' },
  { href: '/settings',      label: 'settings' },
];

export function TopNav() {
  const path = usePathname();

  return (
    <nav className="border-b border-line">
      <div className="shell flex items-center gap-1 py-3 text-[13px] no-scrollbar overflow-x-auto">
        {items.map((it) => {
          const active = it.href === '/' ? path === '/' : path.startsWith(it.href);
          return (
            <Link
              key={it.href}
              href={it.href}
              className={[
                'shrink-0 px-2.5 py-1 border transition-colors',
                active
                  ? 'text-mark border-mark-soft'
                  : 'text-fg-soft border-transparent hover:text-fg hover:border-line',
              ].join(' ')}
            >
              {active && <span className="text-mark mr-1">▸</span>}
              {it.label}
            </Link>
          );
        })}
        <span className="ml-auto hidden md:inline text-fg-faint text-[12px] num-tabular">
          ~/observer{path === '/' ? '/brief.feed' : path}
        </span>
      </div>
    </nav>
  );
}
