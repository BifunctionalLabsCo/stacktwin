# stacktwin
A serverless AI pipeline that turns weekly tech noise into a personalized learning track for developers

## Direction

StackTwin is a weekly learning interface for developers, powered by a serverless AI pipeline. The product should feel less like a feed reader or operations dashboard and more like a focused learning module: each week, the user gets a small set of high-signal lesson launch cards, a lesson player, and a lightweight progress tracker.

The serverless backend exists to prepare that experience:

- ingest current technical signals from sources like Hacker News, arXiv, and Dev.to
- build a structured developer profile from CV, LinkedIn, or manual input
- score and cluster sources against the user's stack, goals, preferences, and time budget
- generate weekly learning modules with objectives, context, exercises, checks, and source references

The primary UI should be a high-fidelity web learning app. Pipeline controls and job status are secondary: useful for reproducibility and trust, but not the center of the product. Exports to Notion, Markdown, or GitHub can be added as publishing targets without replacing the native learning interface.

The long-term foundation should treat generated output as reusable learning objects, not disposable digests. A weekly track today should be modeled as a sequence of learning modules with provenance, objectives, prerequisites, difficulty, assessments, and editable draft state. That keeps the project focused for developers now while leaving a clean path toward an educator-facing AI course builder later.

## Repository Shape

- `backend/stacktwin/`: FastAPI service, ingestion pipeline, profile builder, scoring, digest generation, and Nebius integration
- `src/`: Next.js learning interface compiled to static assets
- `backend/db/`: database schema and persistence artifacts
- `AGENTS.md`: product, engineering, build, and writing guidelines for future agents

## Development

StackTwin uses `uv` for Python and a root frontend build script. The intended full-app flow is:

```bash
uv sync --extra dev
npm install --prefix src
npm run build
uv run uvicorn stacktwin.api.main:app --app-dir backend --reload
```

The frontend is built into `src/out` and served by FastAPI. Backend routes should stay focused on triggering or observing serverless jobs, profile extraction, ingestion, scoring, and module generation.

## Sources

The default ingestion run uses four keyless sources that require no OAuth token, paid tier, or expiring credential:

- **Hacker News** — top stories via the public Firebase API
- **arXiv** — recent papers via public RSS feeds across five computer science categories
- **Dev.to** — top weekly articles via the public REST API
- **YouTube** — recent videos from curated developer channels via public RSS feeds, no API key required

GitHub Trending is commented out of the default registry. It scrapes HTML and may break if GitHub changes its page structure. Uncomment `GitHubTrendingSource()` in `backend/stacktwin/pipeline/ingest.py` to enable it locally.

**Windows SSL compatibility.** arXiv and YouTube RSS use Python's `urllib` to fetch RSS feeds. On Windows, the system certificate store may cause SSL verification failures. Set the following in your local `.env` to bypass verification:

ARXIV_SSL_VERIFY=false

YOUTUBE_SSL_VERIFY=false

Do not set these in production. The default (`true`) enforces SSL verification in every deployed environment.

**Degraded source behavior.** Each source is isolated — a single source failure does not stop the pipeline. Every source reports a status string after each fetch: `ok:…` for success, `degraded:…` for partial results, and `failed:…` for no results. The pipeline continues with whichever sources succeed and can generate a weekly track from partial output.


## Classroom Experience

The compiled app opens on the learner's latest generated weekly track. It includes lesson launch cards, a lesson player, progress scoped to the generated track, source provenance, and a compact explanation of which profile signals influenced the week. The archive at `/archive/` lists earlier tracks and opens their source-backed learning material inline.

The nav includes a learner switcher that changes the active `user_id` in-browser without a reload. By default the app ships with a small demo set:

- `engineer@stacktwin.dev`
- `creator@stacktwin.dev`
- `researcher@stacktwin.dev`

Set `NEXT_PUBLIC_STACKTWIN_DEMO_USERS` before `npm run build` to replace that list. It accepts either a JSON array of `{ id, label, description }` objects or a comma-separated `id|label|description` list. The active learner persists in `localStorage` for the browser session.

The production classroom reads `GET /api/track/current` and week-scoped lesson routes. Set `NEXT_PUBLIC_STACKTWIN_DEMO_MODE=true` only when intentionally using the hardcoded preview fixture. Generated tracks are persisted separately from raw digests so current and archived weeks share one reusable learning-module contract.

## Pipeline Configuration

### Nebius weekly pipeline Job

Production-like development runs use a finite Nebius Serverless AI Job instead
of an always-on model endpoint. Each Job starts local vLLM, waits for the model,
runs the complete weekly pipeline for one learner, persists its results to Nebius
Object Storage, terminates vLLM, and exits. GPU billing ends with the Job.

### Monday shared-content prefetch

At 00:00 UTC each Monday, `.github/workflows/monday-content-prefetch.yml` calls
`POST /api/digest/prefetch`. It fetches and tags the shared weekly source pool,
then stores it in the configured storage backend. Triggering a learner pipeline
later in the week reuses that pool and only performs profile-specific scoring,
digest generation, and lesson creation.

Configure these repository secrets before enabling the workflow:

- `STACKTWIN_PREFETCH_URL`: deployed `https://…/api/digest/prefetch` URL.
- `STACKTWIN_SCHEDULE_TOKEN`: matches the deployed `STACKTWIN_SCHEDULE_TOKEN`.

Create a Nebius Container Registry once, configure its Docker credential helper,
then build and push the Job image:

```bash
nebius registry create --name stacktwin
nebius registry configure-helper

docker build \
  --platform linux/amd64 \
  -f backend/stacktwin/pipeline/Dockerfile \
  -t cr.eu-north1.nebius.cloud/<registry-path>/stacktwin-job:dev \
  .
docker push cr.eu-north1.nebius.cloud/<registry-path>/stacktwin-job:dev
```

Configure `.env` with the image, subnet, model, and Object Storage credentials:

```bash
STACKTWIN_PIPELINE_EXECUTION=nebius_job
STACKTWIN_JOB_IMAGE=cr.eu-north1.nebius.cloud/e00wkter9vcdmapban/stacktwin-job@sha256:9a219ea40337cca143becbd6e3d9bf48b28c2ccbc4ebc7bfb550af87f689b0d3
STACKTWIN_JOB_SUBNET_ID=<subnet-id>
STACKTWIN_JOB_ENV_FILE=.env
NEBIUS_MODEL_MODE=test
NEBIUS_MODEL_TEST=Qwen/Qwen3-0.6B
NEBIUS_MODEL_MAP=NousResearch/Hermes-4-70B
NEBIUS_MODEL_RED=Qwen/Qwen3-235B-A22B-Thinking-2507
STORAGE_BACKEND=nebius
```

The published digest pins the tested amd64 image used by this branch. Developers
do not need to build or push an image for ordinary Job testing. Rebuild and push
only when changing the Job container or backend code, then update the digest.

`NEBIUS_MODEL_MODE=test` forces `NEBIUS_MODEL_TEST` for every LLM adapter:
profile preparation, tag normalization, scoring, summaries, explanations, and
quizzes. This guarantees that plumbing tests load only the small Qwen model.

Production routing is prepared but deliberately not enabled in the single-model
Job. In `prod` mode, map/preparation adapters resolve `NEBIUS_MODEL_MAP` and
reduce/generation adapters resolve `NEBIUS_MODEL_RED`. Those models require
different, substantially larger GPU presets, so production execution will split
them into separate Job phases rather than loading both into the test Job.

The API process needs the Nebius CLI installed and authenticated. A pipeline
trigger submits the Job and returns `202 Accepted` with its ID:

```bash
curl -X POST "http://127.0.0.1:8000/api/digest/run?user_id=<learner-email>"
nebius ai job logs <job-id> --follow
nebius ai job get <job-id>
```

For development, the launcher injects the configured local `.env` as a read-only
Job file. Never commit that file. Production should replace file injection with
MysteryBox-backed `--env-secret` values.

Do not use the production models for Job plumbing tests. Resize the GPU presets
and implement separate map/reduce phases before setting `NEBIUS_MODEL_MODE=prod`.

Two environment variables control how much work the pipeline does each week:

| Variable | Default | Effect |
|---|---|---|
| `SOURCE_LIMIT` | `50` | Articles fetched per source per week |
| `DIGEST_SIZE` | `10` | Articles included in the final weekly digest |

For quick end-to-end runs during development, add to `.env`:

```
SOURCE_LIMIT=5
DIGEST_SIZE=3
```

**Tag index.** After ingestion the pipeline calls Nebius once per week (not once per user) to assign normalized topic tags to every article. The result is cached as `outputs/articles_{week}_tags.json`. On subsequent requests that week the cache is reused. When no API key is set, existing article tags from each source are used as a fallback.

**Profile-driven filtering.** Before LLM scoring, each user's profile signals (stack, learning goals, domains, topics to track) are matched against the tag index. Only articles with at least one matching tag are passed to the scorer, reducing per-user LLM calls from ~100+ to ~20–30 while preserving recall via partial-match and substring logic.

## Storage And Idempotency

Local development uses JSON files by default. Production can use Nebius Object Storage through the same `StorageBackend` contract:

1. Copy `.env.example` to `.env` and create a Nebius Object Storage bucket plus a service-account access key.
2. Populate the `NEBIUS_S3_*` values.
3. Set `STORAGE_BACKEND=nebius`.
4. Build and serve the unified app with the commands in the Development section.

Profiles and weekly tracks retain identical API behavior in either backend. Uploaded CV bytes are SHA-256 hashed; an identical re-upload returns the stored profile without another model extraction. Digest generation checks the user and Monday week key first; retries return the completed track instead of running ingestion, scoring, and generation again.

**Resumable pipeline runs.** Each article is checkpointed to storage individually as it is scored (`scored/{user}/{week}/{url_hash}.json` in S3, `outputs/scored/{user}/{week}/` locally). If a run fails mid-scoring, the next invocation loads the checkpoint and skips already-scored articles — only the remaining batch is sent to the LLM. On successful completion the checkpoint is deleted automatically. This means a retry after a partial failure never duplicates LLM calls for articles that were already processed.

Run the deterministic contract suite with:

```bash
uv run pytest tests/test_storage.py tests/test_idempotency.py tests/test_track_api.py -q
```

To exercise a real bucket, configure the test credentials and isolated prefix in `.env`, then run:

```bash
RUN_NEBIUS_STORAGE_TESTS=true uv run pytest tests/test_storage.py::test_live_nebius_storage_contract -q
```

The live test deletes the profile and digest objects it creates under its unique test prefix.

## Performance Direction

Use fast, mature tooling by default: `uv`, `ruff`, `pydantic-core` through Pydantic, `orjson`, and `uvicorn[standard]`. Prefer Rust-backed or native-accelerated libraries when they fit the problem and keep the architecture simple.
