'use client';

import { useEffect, useState } from 'react';

export function FootBar() {
  const [time, setTime] = useState<string>(() => fmtTime());
  useEffect(() => {
    const id = window.setInterval(() => setTime(fmtTime()), 30_000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <footer className="sticky bottom-0 bg-bg-elev border-t border-line text-fg-soft text-[11px]">
      <div className="shell flex items-center gap-4 h-7 flex-wrap">
        <span><span className="kbd">/</span>search</span>
        <span><span className="kbd">1</span><span className="kbd">2</span><span className="kbd">3</span>view</span>
        <span className="hidden sm:inline"><span className="kbd">enter</span>open</span>
        <span className="ml-auto flex items-center gap-3 text-fg-faint num-tabular">
          <span className="hidden md:inline">build dev · v0.1</span>
          <span className="sep hidden md:inline">│</span>
          <span>{time}</span>
        </span>
      </div>
    </footer>
  );
}

function fmtTime() {
  const d = new Date();
  const hh = String(d.getUTCHours()).padStart(2, '0');
  const mm = String(d.getUTCMinutes()).padStart(2, '0');
  return `${hh}:${mm} UTC`;
}
