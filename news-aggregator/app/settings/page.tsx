import { Suspense } from 'react';
import { api } from '@/lib/api';
import type { Entity } from '@/lib/types';
import { SettingsClient } from './SettingsClient';

export const dynamic = 'force-dynamic';

export default async function SettingsPage() {
  let initial;
  let entities: Entity[] = [];
  try {
    initial = await api.getSettings();
    try {
      entities = await api.getEntities();
    } catch {
      entities = [];
    }
  } catch {
    return (
      <div className="shell pt-12">
        <div className="flex items-baseline gap-2 text-[13px] mb-4">
          <span className="text-hot font-bold">!</span>
          <span className="text-hot">backend unreachable</span>
        </div>
        <h1 className="font-mono text-[24px] font-semibold mb-3">
          Couldn&rsquo;t reach <code className="text-mark">/api/settings</code>.
        </h1>
        <p className="text-fg-soft text-[13px]">
          Start the backend and refresh.
        </p>
      </div>
    );
  }

  return (
    <Suspense>
      <SettingsClient initial={initial} initialEntities={entities} />
    </Suspense>
  );
}
