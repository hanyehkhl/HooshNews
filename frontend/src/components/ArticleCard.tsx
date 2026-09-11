import type { ProcessedArticle } from "../types";

interface ArticleCardProps {
  article: ProcessedArticle;
}

export function ArticleCard({ article }: ArticleCardProps) {
  return (
    <article className="rounded-xl border border-neutral-200 p-4 shadow-sm transition hover:shadow-md dark:border-neutral-800">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-neutral-500 dark:text-neutral-400">
        <span className="rounded-full bg-neutral-100 px-2 py-0.5 dark:bg-neutral-800">
          {article.category}
        </span>
        <span>{article.source}</span>
        <span className="ms-auto font-mono">امتیاز اهمیت: {article.importance_score.toFixed(1)}</span>
      </div>

      <h3 className="mb-1 text-lg font-semibold leading-snug">
        <a href={article.original_url} target="_blank" rel="noreferrer" className="hover:underline">
          {article.title_fa}
        </a>
      </h3>
      <p className="mb-2 text-sm text-neutral-500 dark:text-neutral-400">{article.title_en}</p>

      <p className="mb-3 leading-relaxed">{article.summary_fa}</p>

      <p className="rounded-lg bg-emerald-50 p-3 text-sm leading-relaxed text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200">
        <strong>چرا مهم است؟</strong> {article.why_it_matters}
      </p>

      {article.tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {article.tags.map((tag) => (
            <span
              key={tag}
              className="rounded-full border border-neutral-200 px-2 py-0.5 text-xs text-neutral-500 dark:border-neutral-700 dark:text-neutral-400"
            >
              #{tag}
            </span>
          ))}
        </div>
      )}
    </article>
  );
}
