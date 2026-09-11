import type { DailyDigest, DigestIndex } from "../types";

// import.meta.env.BASE_URL always ends with "/" (Vite guarantee), so plain
// concatenation with a slash-free relative path is safe here.
const BASE = import.meta.env.BASE_URL;

async function getJson<T>(relativePath: string): Promise<T> {
  const response = await fetch(`${BASE}${relativePath}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to fetch ${relativePath}: ${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

/** The cheap manifest of available days — fetched once on load. Fetching
 * only this (instead of every day's full article list) is what keeps
 * page-load cost flat as the archive grows. */
export function fetchIndex(): Promise<DigestIndex> {
  return getJson<DigestIndex>("data/index.json");
}

/** One day's full digest, fetched on demand when the user selects it. */
export function fetchDay(date: string): Promise<DailyDigest> {
  return getJson<DailyDigest>(`data/days/${date}.json`);
}
