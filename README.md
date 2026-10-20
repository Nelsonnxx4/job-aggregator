# Remote Job Aggregator

## Ingesting configured job feeds

The API can ingest permitted RSS, Atom, or JSON Feed endpoints for Hiring Cafe,
Dover, Wellfound, Jobberman, and JobTogether. It does not scrape board pages.
Configure only feed URLs that the source authorizes for automated use:

```dotenv
HIRING_CAFE_FEED_URL=
DOVER_FEED_URL=
WELLFOUND_FEED_URL=
JOBBERMAN_FEED_URL=
JOBTOGETHER_FEED_URL=
```

Each value must be an absolute HTTP(S) URL serving an RSS 2.0, Atom, or
JSON Feed document. A job needs a title, company (or feed author), application
URL, and publication date to be imported. Entries without those fields or
outside the 30-day freshness window are skipped. Feed jobs retain
`remote_scope="unknown"` because a feed alone does not prove that a role is
open to applicants worldwide. Configure feeds that are already limited to
remote vacancies; these feed formats do not standardize remote eligibility.

Run the configured feeds with:

```text
POST /ingestion/feeds/run
```

The response reports each source as `completed`, `failed`, or
`not_configured`. A failed source does not prevent the other feeds from being
processed. Failures are logged server-side; the response includes the exception
type but not upstream error details. Existing Arbeitnow ingestion remains
available at `POST /ingestion/arbeitnow/run`.
