import { useEffect, useState } from "react";

import { fetchDay, fetchIndex } from "./api/fetchDigest";
import { AudioPlayer } from "./components/AudioPlayer";
import { DaySelector } from "./components/DaySelector";
import { DigestList } from "./components/DigestList";
import type { DailyDigest, DigestIndex } from "./types";

type LoadState = { status: "loading" } | { status: "error"; message: string } | { status: "ready" };

export default function App() {
  const [index, setIndex] = useState<DigestIndex | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [digest, setDigest] = useState<DailyDigest | null>(null);
  const [state, setState] = useState<LoadState>({ status: "loading" });

  // Load the index once, then default to the most recent day.
  useEffect(() => {
    fetchIndex()
      .then((loadedIndex) => {
        setIndex(loadedIndex);
        setSelectedDate(loadedIndex.days[0]?.date ?? null);
        if (loadedIndex.days.length === 0) {
          setState({ status: "error", message: "هنوز هیچ خلاصه‌ای منتشر نشده است." });
        }
      })
      .catch((error: unknown) => {
        setState({ status: "error", message: (error as Error).message });
      });
  }, []);

  // Fetch the selected day's full digest on demand.
  useEffect(() => {
    if (!selectedDate) return;
    setState({ status: "loading" });
    fetchDay(selectedDate)
      .then((loadedDigest) => {
        setDigest(loadedDigest);
        setState({ status: "ready" });
      })
      .catch((error: unknown) => {
        setState({ status: "error", message: (error as Error).message });
      });
  }, [selectedDate]);

  return (
    <div className="mx-auto min-h-screen max-w-4xl px-4 py-8 font-sans">
      <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Persian AI Pulse</h1>
          <p className="text-sm text-neutral-500">نبض روزانه‌ی هوش مصنوعی، به فارسی</p>
        </div>
        {index && selectedDate && (
          <DaySelector days={index.days} selected={selectedDate} onSelect={setSelectedDate} />
        )}
      </header>

      {state.status === "error" && (
        <p className="rounded-lg bg-red-50 p-4 text-red-700 dark:bg-red-950 dark:text-red-200">
          {state.message}
        </p>
      )}

      {state.status === "loading" && <p className="text-neutral-500">در حال بارگذاری…</p>}

      {state.status === "ready" && digest && (
        <div className="flex flex-col gap-6">
          {digest.daily_audio_url && (
            <AudioPlayer src={digest.daily_audio_url} label={`پادکست خبری ${digest.date}`} />
          )}
          <DigestList articles={digest.articles} />
        </div>
      )}

      <footer className="mt-12 text-center text-xs text-neutral-400">
        <a
          href="https://github.com/hanyehkhl/HooshNews"
          target="_blank"
          rel="noreferrer"
          className="hover:underline"
        >
          Persian AI Pulse on GitHub
        </a>
      </footer>
    </div>
  );
}
