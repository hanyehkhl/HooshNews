interface AudioPlayerProps {
  src: string;
  label: string;
}

export function AudioPlayer({ src, label }: AudioPlayerProps) {
  return (
    <div className="rounded-xl border border-neutral-200 bg-neutral-50 p-4 dark:border-neutral-800 dark:bg-neutral-900">
      <p className="mb-2 text-sm font-medium text-neutral-600 dark:text-neutral-300">{label}</p>
      {/* eslint-disable-next-line jsx-a11y/media-has-caption -- generated speech, no captions source */}
      <audio controls preload="none" className="w-full" src={src}>
        مرورگر شما از پخش صوت پشتیبانی نمی‌کند.
      </audio>
    </div>
  );
}
