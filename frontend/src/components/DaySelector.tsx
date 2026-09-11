import type { DigestIndexEntry } from "../types";

interface DaySelectorProps {
  days: DigestIndexEntry[];
  selected: string;
  onSelect: (date: string) => void;
}

export function DaySelector({ days, selected, onSelect }: DaySelectorProps) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="text-neutral-500">تاریخ:</span>
      <select
        value={selected}
        onChange={(event) => onSelect(event.target.value)}
        className="rounded-lg border border-neutral-300 bg-white px-2 py-1 dark:border-neutral-700 dark:bg-neutral-900"
      >
        {days.map((day) => (
          <option key={day.date} value={day.date}>
            {day.date} ({day.article_count} خبر{day.has_audio ? " + پادکست" : ""})
          </option>
        ))}
      </select>
    </label>
  );
}
