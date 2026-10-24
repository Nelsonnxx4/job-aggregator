# Remote Job Aggregator

FastAPI backend, scheduled worker, and React dashboard for collecting
permitted job feeds, filtering and scoring listings, persisting ingestion
history, and sending optional Telegram alerts.

## Run locally with Docker Compose

1. Copy `.env.example` to `.env`.
2. Set `POSTGRES_PASSWORD` and `DATABASE_URL`/feed/Telegram configuration as
   appropriate. Do not commit `.env` or production credentials.
3. Start the database, API, and worker:

   ```powershell
   docker compose up --build
   ```

The API applies Alembic migrations before starting. The worker waits for the
API health check, runs an ingestion/notification cycle immediately, then
repeats at `INGESTION_INTERVAL_SECONDS`. Open the dashboard at
`http://localhost:4173`; the frontend proxy forwards API requests over the
Compose network.

## Dashboard development

The React + TypeScript app lives in `frontend/`. It reads jobs, sources,
ingestion runs, and database health from the FastAPI API. It supports
searching/filtering the latest 100 jobs, viewing job details and the original
application link, monitoring source runs, and manually starting ingestion.

For standalone development, start the API on port 8000, then run:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Vite serves the dashboard at `http://localhost:5173` and proxies `/api` to
`http://127.0.0.1:8000`. Set `VITE_API_BASE_URL` only if the API is hosted at a
different base URL.

The dashboard styling uses Tailwind CSS. Shared API shapes live in
`frontend/src/types.ts`; API requests, dashboard state, filters, and view
components are separated into `api.ts`, `hooks/`, `utils/`, and `components/`
under `frontend/src/`.

For a local Python environment, install `requirements.txt`, run
`python -m alembic upgrade head`, then start the API with
`uvicorn app.main:app --reload`. Start the scheduled worker separately with
`python -m app.worker`.

## Job listing sources

The service collects listings from public job-board APIs (Arbeitnow, Remote
OK, Remotive, and JustJoin.it) and can additionally consume authorized RSS 2.0,
Atom, or JSON feeds. It does not scrape arbitrary job-board pages. Leave feed
settings blank unless you have a feed URL the provider permits you to use.

```dotenv
HIRING_CAFE_FEED_URL=
DOVER_FEED_URL=
WELLFOUND_FEED_URL=
JOBBERMAN_FEED_URL=
JOBTOGETHER_FEED_URL=
JUSTJOINIT_CATEGORIES=1,2
```

A listing needs a title, company (or feed author), application URL, and valid
publication timestamp. Missing or invalid fields are skipped, and jobs older
than `INGESTION_FRESHNESS_DAYS` are excluded. Remote-work status and geographic
eligibility are stored separately. Importers infer geography only
from explicit text such as “worldwide” or “EMEA”; those labels are marked
inferred, not verified. A generic “remote” label does not mean worldwide.

The public APIs do not require a paid subscription or API key. Review the
providers' current terms before publishing listings. Remote OK requires a
followable link to Remote OK and source attribution; the dashboard links each
listing's source and original job listing. Do not use the Remote OK logo
without written permission. A provider may change API access or terms.
See the [Arbeitnow Job Board API](https://www.arbeitnow.com/api/job-board-api),
[Remote OK API terms](https://remoteok.com/api), and the
[Remotive remote jobs API](https://remotive.com/api) for current provider
details. The JustJoin.it adapter uses its public unauthenticated offer API.

`POST /ingestion/arbeitnow/run`, `POST /ingestion/remoteok/run`,
`POST /ingestion/remotive/run`, `POST /ingestion/justjoinit/run`, and
`POST /ingestion/feeds/run` allow manual runs. The worker runs the public API
sources on its schedule. Each source has independent run tracking, and a
failure at one source does not stop collection from others.
`GET /ingestion/runs` returns the latest run records and statistics; filter
with `source_id` and/or `status`.

Source registration is idempotent for an exact matching name, slug, and base
URL (`POST /sources` returns `200` for a reused source). Use
`PATCH /sources/{source_id}` with `{"is_active": false}` to disable a source.
The configured worker respects disabled sources.

## Jobs and geographic eligibility

`GET /jobs` supports filtering by source, remote scope, region, freshness,
eligibility, and minimum relevance score. Results include a transparent
heuristic score and reasons. Cross-source duplicates are retained with their
source attribution and linked through `duplicate_of_id`; exact matching uses
normalized application URLs plus matching title and company.

Job records include first/last-seen timestamps, remote status, eligible
countries, eligibility confidence, source, and reason. Feed imports record
remote status independently and leave geographic eligibility `unknown` unless
the text provides evidence.
Eligibility inferred from listing text is useful for discovery but should be
verified before applying.

## Telegram notifications

Configure both values to enable notifications:

```dotenv
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

The worker alerts only on fresh, sufficiently relevant jobs marked remote with
explicit worldwide or EMEA eligibility. Country-restricted alerts are off by default;
enabling `TELEGRAM_INCLUDE_COUNTRY_RESTRICTED` also requires Nigeria to appear
in the job's eligible-country list. Configure the relevance threshold with
`TELEGRAM_MIN_RELEVANCE_SCORE`.

Delivery state is persisted with a unique record per job. Telegram rate limits
are retried within the configured bounds. A delivery left in `sending` after a
worker crash is not resent automatically, avoiding duplicate alerts when the
original delivery may have succeeded; inspect it before manually retrying.

To verify the configured bot and chat without waiting for a qualifying job,
run this one-off test message from the project root:

```powershell
python -m app.telegram_test
```

The command uses the configured Telegram retry settings and reports success
without printing the bot token. With Docker Compose, run
`docker compose run --rm worker python -m app.telegram_test`.

## Operations and limitations

- `GET /health` checks database connectivity; interactive API docs are at
  `/docs`.
- External HTTP requests use timeouts and bounded retries. Run errors are
  logged and persisted without returning upstream exception details.
- Run `python -m alembic upgrade head` when deploying outside Compose. Do not
  reset a production database to resolve migration errors.
- For local Compose backups, export before maintenance with
  `docker compose exec -T db pg_dump -U jobapp job_aggregator > backup.sql`.
  Restore only into a verified target database with
  `docker compose exec -T db psql -U jobapp -d job_aggregator < backup.sql`.
  Keep backups encrypted and outside the repository. For Neon, use the
  provider's backup/restore workflow and verify the Alembic revision before
  resuming ingestion.
- Feed URLs and job text are external data; validate a source's terms and
  geographic eligibility independently.
- User accounts and authentication/authorization for write and ingestion
  endpoints are not included. Do not expose those endpoints to an untrusted
  public network until access controls are added.
- Live Neon migration and Telegram delivery still require valid deployment
  configuration and must be verified in that environment.
