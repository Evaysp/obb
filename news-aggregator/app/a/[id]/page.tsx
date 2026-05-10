import { notFound } from 'next/navigation';
import { ApiError, api } from '@/lib/api';
import type { Source } from '@/lib/types';
import { ArticleReader } from './ArticleReader';

interface Props {
  params: { id: string };
}

export default async function ArticlePage({ params }: Props) {
  const id = Number(params.id);
  if (!Number.isFinite(id) || id <= 0) notFound();

  let article;
  let source: Source | undefined;
  try {
    article = await api.getArticle(id);
    const sources = await api.getSources();
    source = sources.find((s) => s.slug === article!.sourceSlug);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }
  if (!source) notFound();

  return <ArticleReader article={article} source={source} />;
}
