// These types mirror the backend's pydantic schemas 1:1.
// Backend uses alias_generator=to_camel, so wire format is camelCase; DB is snake_case.
// If you change anything here, update app/schemas/*.py on the backend — and vice versa.

export type Lang = 'zh' | 'ja' | 'en';

export type SourceKind = 'rss' | 'html' | 'api';

export type SourceTier = 'free' | 'paywall';

export type CookieStatus = 'missing' | 'ok' | 'expiring' | 'expired';

export type EntityKind = 'person' | 'company';

export interface Source {
  slug: string;
  name: string;
  nameLocal?: string | null;
  lang: Lang;
  region: string;
  kind: SourceKind;
  tier: SourceTier;
  feedUrl?: string | null;
  needsCookies: boolean;
  enabled: boolean;
  lastFetchedAt?: string | null;
  articleCount24h: number;
  cookieStatus?: CookieStatus | null;
  cookieExpiresAt?: string | null;
}

export interface Article {
  id: number;
  sourceSlug: string;
  url: string;
  title: string;
  author?: string | null;
  publishedAt: string;
  lang: Lang;
  summary: string;
  leadImageUrl?: string | null;
  readingTimeMin?: number | null;
  entities: string[];
}

export interface ArticleDetail extends Article {
  contentHtml?: string | null;
  fetchedAt: string;
}

export interface Entity {
  slug: string;
  canonicalName: string;
  nameLocal?: string | null;
  kind: EntityKind;
  aliases: string[];
  description?: string | null;
  imageUrl?: string | null;
  articleCount7d: number;
  subscribed: boolean;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// ─── UI-local helpers (not on the wire) ─────────
// Deterministic hue used only by the placeholder hero image. Computed client-side.
export function heroHueFor(id: number | string): number {
  const s = String(id);
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h % 360;
}
