import type { ProcessedArticle } from "../types";
import { ArticleCard } from "./ArticleCard";

interface DigestListProps {
  articles: ProcessedArticle[];
}

export function DigestList({ articles }: DigestListProps) {
  if (articles.length === 0) {
    return <p className="text-center text-neutral-500">خبری برای این روز ثبت نشده است.</p>;
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {articles.map((article) => (
        <ArticleCard key={article.id} article={article} />
      ))}
    </div>
  );
}
