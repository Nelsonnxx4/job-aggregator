# Remote Job Aggregator

FastAPI backend and scheduled worker for collecting permitted job feeds,
filtering and scoring listings, persisting ingestion history, and sending
optional Telegram alerts.

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
repeats at `INGESTION_INTERVAL_SECONDS`.

For a local Python environment, install `requirements.txt`, run
`python -m alembic upgrade head`, then start the API with
`uvicorn app.main:app --reload`. Start the scheduled worker separately with
`python -m app.worker`.

## Feed configuration

The service supports permitted RSS 2.0, Atom, or JSON Feed URLs for Hiring
Cafe, Dover, Wellfound, Jobberman, and JobTogether. It does not scrape job-board
pages. Only configure URLs that the source authorizes for automated access.

```dotenv
HIRING_CAFE_FEED_URL=
DOVER_FEED_URL=
WELLFOUND_FEED_URL=
JOBBERMAN_FEED_URL=
JOBTOGETHER_FEED_URL=
```

A listing needs a title, company (or feed author), application URL, and valid
publication timestamp. Missing or invalid fields are skipped, and jobs older
than `INGESTION_FRESHNESS_DAYS` are excluded. Remote-work status and geographic
eligibility are stored separately. Importers infer geography only
from explicit text such as “worldwide” or “EMEA”; those labels are marked
inferred, not verified. A generic “remote” label does not mean worldwide.

Arbeitnow is also supported through its documented job-board API. The
`POST /ingestion/arbeitnow/run` and `POST /ingestion/feeds/run` endpoints allow
manual runs. Each feed is isolated, so one source failure does not stop other
sources. `GET /ingestion/runs` returns the latest run records and statistics;
filter with `source_id` and/or `status`.

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
- This MVP does not include the React dashboard, user accounts, or
  authentication/authorization for write and ingestion endpoints. Do not expose
  those endpoints to an untrusted public network until access controls are
  added.
- Live Neon migration and Telegram delivery still require valid deployment
  configuration and must be verified in that environment.
