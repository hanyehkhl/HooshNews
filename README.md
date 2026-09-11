# Persian AI Pulse

پایپ‌لاین خودکار و ماژولار برای تولید یک خلاصه‌ی روزانه‌ی اخبار هوش مصنوعی به فارسی — همراه با یک پادکست صوتی کوتاه — بدون هیچ سروری: داده‌ها به‌صورت JSON در همین ریپو (git-as-a-database) ذخیره می‌شوند و یک سایت استاتیک آن‌ها را نمایش می‌دهد.

## معماری

```text
[ RSS / arXiv / Telegram ]  →  backend/.../ingest      (فچ + نرمال‌سازی + coverage gate)
                             →  backend/.../intelligence (dedup embedding-based، خلاصه‌ی فارسی با LLM، رتبه‌بندی، تولید پادکست)
                             →  backend/.../publish      (نوشتن JSON بر اساس روز + ارسال به تلگرام)
                             →  frontend/public/data/*.json  →  React + Vite + Tailwind (استاتیک)
```

هر مرحله یک لایه‌ی مستقل پایتونی است با یک `Protocol` در ورودی/خروجی (`RawArticle` → `ProcessedArticle` → `DailyDigest`)، پس هر لایه را می‌توان جدا اجرا، تست، یا جایگزین کرد — نه یک اسکریپت یکپارچه.

## ساختار ریپو

```
backend/
  src/persian_ai_pulse/
    schemas.py          # RawArticle / ProcessedArticle / DailyDigest / DigestIndex
    ids.py               # id پایدار بر اساس hash(normalized_url) — نه شمارنده یا timestamp
    config.py            # تنظیمات از env، به تفکیک هر provider
    retry.py             # دکوراتور retry-with-backoff سبک (به‌جای وابستگی به tenacity)
    ingest/               # RSS, arXiv, Telegram (Telethon) → RawArticle
    intelligence/         # dedup (embedding)، خلاصه‌سازی فارسی (LLM)، رتبه‌بندی، TTS
    publish/              # JSON store (به تفکیک روز) + انتشار در تلگرام (Bot API)
    cli.py                # pap ingest / process / publish-site / publish-telegram
  config/sources.example.json
  tests/                  # pytest؛ هر لایه با fake provider/embedder جدا تست می‌شود
frontend/
  src/
    types.ts              # آینه‌ی schemas.py سمت فرانت
    api/fetchDigest.ts
    components/           # ArticleCard, DigestList, AudioPlayer, DaySelector
  public/data/             # index.json + days/<date>.json  (خروجی publish layer)
  public/media/            # digest-<date>.mp3
.github/workflows/
  pipeline.yml            # اجرای روزانه‌ی کامل پایپ‌لاین
  ci.yml                   # lint + pytest + build فرانت روی هر push/PR
```

## شروع سریع (لوکال)

```bash
# بک‌اند
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,intelligence,tts,telegram]"
cp ../.env.example ../.env   # و مقادیر را پر کنید
cp config/sources.example.json config/sources.json  # و فیدهای دلخواه را اضافه/ویرایش کنید

pytest                       # تست‌های واحد
pap ingest --config config/sources.json
pap process
pap publish-site --with-audio
pap publish-telegram         # اختیاری، نیاز به PAP_TG_PUBLISH_*

# فرانت
cd ../frontend
npm install
npm run dev
```

## متغیرهای محیطی

همه در `.env.example` مستندند. خلاصه:

| گروه | متغیر | توضیح |
|---|---|---|
| LLM | `PAP_LLM_API_KEY`, `PAP_LLM_BASE_URL`, `PAP_LLM_MODEL` | هر endpoint سازگار با OpenAI Chat Completions (OpenAI، Groq، Together، یا سلف‌هاست) |
| TTS | `PAP_TTS_PROVIDER` (`edge`\|`openai`), `PAP_TTS_VOICE` | پیش‌فرض `edge-tts` رایگان با صدای فارسی |
| Telegram ingestion | `PAP_TG_INGEST_API_ID/HASH/SESSION_STRING` | نیاز به **user session** (Telethon)، نه بات |
| Telegram publish | `PAP_TG_PUBLISH_BOT_TOKEN/CHAT_ID` | یک بات ساده، مجزا از ingestion |

**چرا ingestion و publish تلگرام دو مسیر جدا دارند:** بات تلگرام نمی‌تواند تاریخچه‌ی یک کانال را بخواند (فقط user session می‌تواند)، و چرخش توکن بات هم نباید scraping را بشکند. این تفکیک از ابتدا در معماری لحاظ شده.

## استقرار (GitHub Actions)

1. در تنظیمات ریپو → Secrets، مقادیر بالا را اضافه کنید (حداقل `PAP_LLM_API_KEY` و `PAP_TG_PUBLISH_*` برای فعال بودن کامل پایپ‌لاین؛ بدون Telegram هم سایت به‌تنهایی کار می‌کند).
2. `backend/config/sources.example.json` را به `backend/config/sources.json` کپی و فیدهای واقعی را وارد کنید (این فایل commit می‌شود؛ فقط `.env` مخفی می‌ماند).
3. `.github/workflows/pipeline.yml` هرروز ساعت ۰۶:۰۰ UTC اجرا می‌شود (یا دستی از تب Actions). خروجی در `frontend/public/data/` و `frontend/public/media/` commit می‌شود.
4. فرانت را در Vercel/Cloudflare Pages به ریشه‌ی `frontend/` وصل کنید — با هر push به این مسیر، دیپلوی خودکار انجام می‌شود.

## تصمیم‌های طراحی (و چرا)

این پروژه از یک بررسی معماری اولیه شروع شد که چند ریسک را از قبل مشخص کرد؛ راه‌حل هرکدام مستقیماً در کد پیاده شده:

- **`releases.json` واحد و رو-به-رشد** → به‌جای آن یک `index.json` سبک + یک فایل جدا برای هر روز (`publish/json_store.py`). فرانت همیشه فقط ایندکس + یک روز را می‌خواند، نه کل آرشیو را.
- **race condition در commit خودکار** → `concurrency` group در `pipeline.yml` مانع همپوشانی دو اجرای هم‌زمان می‌شود.
- **id ناپایدار (شمارنده/timestamp)** → `ids.py` بر اساس hash از URL نرمال‌شده (بدون UTM و...)، پس اجرای دوباره‌ی همان روز تکراری تولید نمی‌کند (`JsonStore.upsert_day` بر اساس id مرج می‌کند).
- **غلبه‌ی یک منبع پرحجم بر کل اخبار** → coverage gate در `ingest/pipeline.py` (الهام‌گرفته از AiNews).
- **هزینه‌ی نمایی dedup روی کل آرشیو** → پنجره‌ی زمانی محدود (`dedup_window_hours`) در `intelligence/dedup.py`.
- **کندی/هزینه‌ی TTS خودمیزبان روی GitHub Actions (بدون GPU)** → پیش‌فرض `edge-tts` (رایگان، صدای فارسی، بدون نیاز به مدل سنگین لوکال)، با امکان سوییچ به یک API پولی از طریق تنظیمات.
- **alerting نداشتن** → مرحله‌ی `notify_failure` در `pipeline.yml` یک پیام به تلگرام ادمین می‌فرستد اگر هر مرحله شکست بخورد.
- **وابستگی سنگین برای صرفاً retry** → به‌جای `tenacity`، یک دکوراتور کوچک (`retry.py`) نوشته شده؛ سه محل استفاده، توجیه یک پکیج خارجی را نداشت.

## منابع / الهام‌گرفته از

این معماری (git-as-a-database + سایت استاتیک، به‌جای دیتابیس/سرور) الگوی جدیدی نیست؛ چند پروژه‌ی مشابه که در طراحی این ریپو بررسی شدند:

- [smol-ai/ainews-web-2025](https://github.com/smol-ai/ainews-web-2025) — منبع اصلی ایده‌ی «git-as-a-database + سایت استاتیک» و coverage gate بین منابع خبری.
- [viochris/daily-ai-news-digest](https://github.com/viochris/daily-ai-news-digest) — نمونه‌ی نزدیک همین pipeline (RSS → خلاصه‌سازی با LLM → دایجست روزانه در تلگرام)، برای اندونزیایی.
- [taielab/awesome-ai-news](https://github.com/taielab/awesome-ai-news) — فهرست ابزارهای aggregation/automation خبر با هوش مصنوعی، برای بررسی الگوهای رایج.

هیچ نمونه‌ی مشابهی با همین ترکیب (فارسی + RSS/arXiv/Telegram + پادکست صوتی + انتشار خودکار در تلگرام) پیدا نشد — این بخش‌ها ترکیب و پیاده‌سازی تازه‌ای هستند.

## محدودیت‌های شناخته‌شده / گام بعدی

- Telegram ingestion (`ingest/telegram_source.py`) به یک session string معتبر نیاز دارد که باید یک‌بار لوکال با Telethon تولید و به‌صورت secret ذخیره شود؛ اگر session باطل شود، آن منبع بی‌صدا نادیده گرفته می‌شود (لاگ می‌شود، ولی کل اجرا را نمی‌شکند).
- `backend/config/sources.example.json` شامل چند فید نمونه است — قبل از اجرای واقعی، آدرس‌ها را verify کنید (RSS برخی سرویس‌ها تغییر می‌کند).
- OG tags پویا برای اشتراک‌گذاری در شبکه‌های اجتماعی هنوز اضافه نشده (SPA خالص آن را درست نشان نمی‌دهد) — گام بعدی طبیعی است.

## لایسنس

MIT — به [LICENSE](LICENSE) نگاه کنید.
