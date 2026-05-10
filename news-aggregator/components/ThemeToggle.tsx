'use client';

import { useEffect, useState } from 'react';
import { useTheme } from 'next-themes';

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const isDark = mounted && resolvedTheme === 'dark';

  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      className="text-fg-faint hover:text-fg transition-colors text-[11px] tracking-[0.06em] uppercase"
      aria-label="Toggle theme"
      title="Toggle theme"
    >
      {mounted ? (isDark ? '☾ dark' : '☀ light') : '·'}
    </button>
  );
}
