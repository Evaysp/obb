/**
 * API client — the only place the frontend talks to the backend.
 *
 * Conventions:
 *  - Server components import and call these directly (await api.getFeed(...))
 *  - Client components call them via fetch inside useEffect or server actions
 *  - All functions return the parsed, typed response or throw ApiError
 *
 * Cache policy per CONVENTIONS §3:
 *  - Feed: revalidate 60s
 *  - Article detail: revalidate 300s
 *  - Sources / Entities: no-store (health-type data)
 *
 * To override the base URL, set NEXT_PUBLIC_API_URL in .env.local.
 * The default 127.0.0.1:8000 is what the local docker-compose exposes.
 */

import type {
  Article,
  ArticleDetail,
  Entity,
  Lang,
  Page,
  Source,
} from './types';

// Server-side: hit the backend directly via loopback (avoids LAN/VPN quirks).
// Client-side: use a relative URL — Next.js rewrites /api/* to the backend
// (see next.config.mjs), so the browser only ever talks to its own origin.
const BASE_URL =
  typeof window === 'undefined'
    ? (process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000')
    : '';

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly path: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

type FetchOpts = {
  revalidate?: number | false; // Next.js ISR: seconds, or false for no-store
  signal?: AbortSignal;
};

async function request<T>(
  path: string,
  init: RequestInit = {},
  opts: FetchOpts = {},
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const next: { revalidate?: number } = {};
  if (opts.revalidate === false) {
    // handled by cache: 'no-store' below
  } else if (typeof opts.revalidate === 'number') {
    next.revalidate = opts.revalidate;
  }

  const res = await fetch(url, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...init.headers,
    },
    cache: opts.revalidate === false ? 'no-store' : undefined,
    next: Object.keys(next).length ? next : undefined,
    signal: opts.signal,
  });

  if (!res.ok) {
    let code = 'http_error';
    let message = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
      }
    } catch {
      // non-JSON error body — use the statusText fallback
    }
    throw new ApiError(res.status, code, message, path);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ─── Feed ──────────────────────────────────────
export interface FeedQuery {
  lang?: Lang;
  region?: string;
  tier?: 'all' | 'free' | 'paywall';
  source?: string;
  limit?: number;
  offset?: number;
}

function toQuery(params: Record<string, string | number | boolean | undefined | null>) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue;
    q.append(k, String(v));
  }
  const s = q.toString();
  return s ? `?${s}` : '';
}

export async function getFeed(query: FeedQuery = {}): Promise<Page<Article>> {
  return request<Page<Article>>(
    `/api/feed${toQuery(query)}`,
    {},
    { revalidate: 60 },
  );
}

export async function getArticle(id: number): Promise<ArticleDetail> {
  return request<ArticleDetail>(
    `/api/articles/${id}`,
    {},
    { revalidate: 300 },
  );
}

// ─── Sources ───────────────────────────────────
export async function getSources(): Promise<Source[]> {
  return request<Source[]>(`/api/sources`, {}, { revalidate: false });
}

export async function getSourceBySlug(slug: string): Promise<Source> {
  return request<Source>(`/api/sources/${slug}`, {}, { revalidate: false });
}

export interface CreateSourceInput {
  name: string;
  feedUrl: string;
  lang: Lang;
  region: string;
  nameLocal?: string;
  slug?: string;
}

export async function createSource(input: CreateSourceInput): Promise<Source> {
  return request<Source>(
    `/api/sources`,
    { method: 'POST', body: JSON.stringify(input) },
    { revalidate: false },
  );
}

export interface RefreshResult {
  triggered: {
    slug: string;
    ok: number;
    skipped: number;
    errors: number;
    errorMessage?: string | null;
  }[];
  skippedRecent: string[];
  totalNew: number;
}

export async function refreshSources(): Promise<RefreshResult> {
  return request<RefreshResult>(
    `/api/sources/refresh`,
    { method: 'POST' },
    { revalidate: false },
  );
}

// ─── Settings ──────────────────────────────────
export type AIProvider = 'anthropic' | 'openai' | 'deepseek' | 'minimax';

export interface AppSettings {
  defaultProvider: AIProvider;
  customPrompt: string | null;
  configuredProviders: AIProvider[];
  modelOverrides: Partial<Record<AIProvider, string>>;
  endpointOverrides: Partial<Record<AIProvider, string>>;
  defaultModels: Record<AIProvider, string>;
  defaultEndpoints: Record<AIProvider, string>;
  defaultPrompt: string;
}

export interface SettingsUpdateInput {
  defaultProvider?: AIProvider;
  customPrompt?: string | null;
  clearCustomPrompt?: boolean;
  apiKeys?: Partial<Record<AIProvider, string | null>>;
  models?: Partial<Record<AIProvider, string | null>>;
  endpoints?: Partial<Record<AIProvider, string | null>>;
}

export async function getSettings(): Promise<AppSettings> {
  return request<AppSettings>(`/api/settings`, {}, { revalidate: false });
}

export async function updateSettings(input: SettingsUpdateInput): Promise<AppSettings> {
  return request<AppSettings>(
    `/api/settings`,
    { method: 'PUT', body: JSON.stringify(input) },
    { revalidate: false },
  );
}

// ─── AI ────────────────────────────────────────
export interface SummarizeInput {
  provider?: AIProvider;
  model?: string;
  customPrompt?: string;
  hours?: number;
}

export interface SummarizeResponse {
  summary: string;
  provider: AIProvider;
  model: string;
  articleCount: number;
  usedCustomPrompt: boolean;
}

export async function summarize(input: SummarizeInput = {}): Promise<SummarizeResponse> {
  return request<SummarizeResponse>(
    `/api/ai/summarize`,
    { method: 'POST', body: JSON.stringify(input) },
    { revalidate: false },
  );
}

// ─── Translation ──────────────────────────────
export interface TranslationItem {
  title: string;
  summary: string;
  cached: boolean;
  error?: string | null;
}

export interface TranslateResponse {
  targetLang: string;
  translations: Record<number, TranslationItem>;
}

export async function translateArticles(
  input: { articleIds: number[]; targetLang?: string },
): Promise<TranslateResponse> {
  return request<TranslateResponse>(
    `/api/translate/articles`,
    {
      method: 'POST',
      body: JSON.stringify({
        articleIds: input.articleIds,
        targetLang: input.targetLang ?? 'zh',
      }),
    },
    { revalidate: false },
  );
}

export interface FullTranslation {
  id: number;
  title: string;
  summary: string;
  contentHtml: string;
  cached: boolean;
}

export async function translateArticle(
  articleId: number,
  targetLang: string = 'zh',
): Promise<FullTranslation> {
  return request<FullTranslation>(
    `/api/translate/article/${articleId}`,
    {
      method: 'POST',
      body: JSON.stringify({ targetLang }),
    },
    { revalidate: false },
  );
}

export interface BlocksTranslation {
  targetLang: string;
  translations: (string | null)[];
  cached: boolean[];
}

export async function translateBlocks(
  texts: string[],
  targetLang: string = 'zh',
): Promise<BlocksTranslation> {
  return request<BlocksTranslation>(
    `/api/translate/blocks`,
    {
      method: 'POST',
      body: JSON.stringify({ texts, targetLang }),
    },
    { revalidate: false },
  );
}

export async function importCookies(
  slug: string,
  payload: { cookies: unknown[]; userAgent?: string },
): Promise<{ ok: boolean; error?: string; message?: string }> {
  return request(
    `/api/sources/${slug}/cookies`,
    { method: 'POST', body: JSON.stringify(payload) },
    { revalidate: false },
  );
}

// ─── Auto-import (Playwright) ─────────────────
export type AutoCapturePhase =
  | 'pending' | 'browser_open' | 'waiting_login'
  | 'saving' | 'done' | 'error' | 'cancelled';

export interface AutoCaptureStatus {
  jobId: string;
  slug: string;
  phase: AutoCapturePhase;
  message: string;
  startedAt: string;
  updatedAt: string;
  durationMs: number;
  error: string | null;
  result: { cookieCount: number; expiresAt: string | null } | null;
}

export async function startAutoCapture(slug: string): Promise<{ jobId: string }> {
  return request<{ jobId: string }>(
    `/api/sources/${slug}/cookies/auto-start`,
    { method: 'POST' },
    { revalidate: false },
  );
}

export async function getAutoCaptureStatus(
  slug: string, jobId: string,
): Promise<AutoCaptureStatus> {
  return request<AutoCaptureStatus>(
    `/api/sources/${slug}/cookies/auto-status/${jobId}`,
    {},
    { revalidate: false },
  );
}

export async function cancelAutoCapture(
  slug: string, jobId: string,
): Promise<AutoCaptureStatus> {
  return request<AutoCaptureStatus>(
    `/api/sources/${slug}/cookies/auto-cancel/${jobId}`,
    { method: 'POST' },
    { revalidate: false },
  );
}

// ─── Entities ──────────────────────────────────
export async function getEntities(
  opts: { subscribedOnly?: boolean } = {},
): Promise<Entity[]> {
  return request<Entity[]>(
    `/api/entities${toQuery({ subscribedOnly: opts.subscribedOnly })}`,
    {},
    { revalidate: false },
  );
}

export async function subscribe(
  entitySlug: string,
  notifyChannels: string[] = ['webpush'],
): Promise<void> {
  await request<void>(
    `/api/subscriptions`,
    {
      method: 'POST',
      body: JSON.stringify({ entitySlug, notifyChannels }),
    },
    { revalidate: false },
  );
}

export async function unsubscribe(entitySlug: string): Promise<void> {
  await request<void>(
    `/api/subscriptions/${entitySlug}`,
    { method: 'DELETE' },
    { revalidate: false },
  );
}

export const api = {
  getFeed,
  getArticle,
  getSources,
  getSourceBySlug,
  createSource,
  refreshSources,
  importCookies,
  startAutoCapture,
  getAutoCaptureStatus,
  cancelAutoCapture,
  getEntities,
  subscribe,
  unsubscribe,
  getSettings,
  updateSettings,
  summarize,
  translateArticles,
  translateArticle,
  translateBlocks,
};
