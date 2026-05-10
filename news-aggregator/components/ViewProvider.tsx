'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

export type View = 'list' | 'grid' | 'compact';

interface Ctx {
  view: View;
  setView: (v: View) => void;
}

const ViewCtx = createContext<Ctx>({ view: 'list', setView: () => {} });

export function useView() {
  return useContext(ViewCtx);
}

export function ViewProvider({ children }: { children: ReactNode }) {
  const [view, setViewState] = useState<View>('list');

  useEffect(() => {
    try {
      const saved = localStorage.getItem('observer-view') as View | null;
      if (saved === 'list' || saved === 'grid' || saved === 'compact') {
        setViewState(saved);
        document.body.dataset.view = saved;
      } else {
        document.body.dataset.view = 'list';
      }
    } catch {
      document.body.dataset.view = 'list';
    }
  }, []);

  // 1 / 2 / 3 keyboard shortcuts
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      if (e.key === '1') apply('list');
      else if (e.key === '2') apply('grid');
      else if (e.key === '3') apply('compact');
    }
    function apply(v: View) {
      setViewState(v);
      document.body.dataset.view = v;
      try { localStorage.setItem('observer-view', v); } catch {}
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  function setView(v: View) {
    setViewState(v);
    document.body.dataset.view = v;
    try { localStorage.setItem('observer-view', v); } catch {}
  }

  return <ViewCtx.Provider value={{ view, setView }}>{children}</ViewCtx.Provider>;
}
