/** Mirrors backend/src/persian_ai_pulse/schemas.py — keep these two in sync
 * whenever a field is added/removed on either side. */

export interface ProcessedArticle {
  id: string;
  title_fa: string;
  title_en: string;
  source: string;
  category: string;
  importance_score: number;
  summary_fa: string;
  why_it_matters: string;
  original_url: string;
  tags: string[];
  published_at: string;
}

export interface DailyDigest {
  date: string;
  generated_at: string;
  daily_audio_url: string | null;
  articles: ProcessedArticle[];
}

export interface DigestIndexEntry {
  date: string;
  article_count: number;
  has_audio: boolean;
}

export interface DigestIndex {
  updated_at: string;
  days: DigestIndexEntry[];
}
