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

- `demo@stacktwin.dev`
- `soumya@gmail.com`
- `john@company.com`

Set `NEXT_PUBLIC_STACKTWIN_DEMO_USERS` before `npm run build` to replace that list. It accepts either a JSON array of `{ id, label, description }` objects or a comma-separated `id|label|description` list. The active learner persists in `localStorage` for the browser session.

The production classroom reads `GET /api/track/current` and week-scoped lesson routes. Set `NEXT_PUBLIC_STACKTWIN_DEMO_MODE=true` only when intentionally using the hardcoded preview fixture. Generated tracks are persisted separately from raw digests so current and archived weeks share one reusable learning-module contract.

## Pipeline Configuration

### Nebius development endpoint

StackTwin currently sends synchronous OpenAI-compatible requests to a Nebius
Serverless AI Endpoint. Configure the endpoint's public URL with `/v1`, its auth
token, and the exact served model ID:

```bash
NEBIUS_API_URL=https://<endpoint-public-host>/v1
NEBIUS_TOKEN=<endpoint-token>
NEBIUS_MODEL=Qwen/Qwen3-0.6B
```

The development endpoint uses the pinned vLLM image and command layout from the
Nebius deployment guide:

```bash
nebius ai endpoint create \
  --name stacktwin-dev-endpoint-v2 \
  --image vllm/vllm-openai:v0.18.0-cu130 \
  --container-command "python3 -m vllm.entrypoints.openai.api_server" \
  --args "--model Qwen/Qwen3-0.6B --host 0.0.0.0 --port 8000 --max-model-len 4096" \
  --platform gpu-l40s-a \
  --preset 1gpu-8vcpu-32gb \
  --disk-size 100Gi \
  --shm-size 16Gi \
  --subnet-id <subnet-id> \
  --preemptible \
  --container-port 8000 \
  --public \
  --auth token \
  --token "$NEBIUS_TOKEN"
```

Wait for both the Nebius endpoint state and the vLLM server startup logs before
testing routes. During model loading and CUDA graph warmup, the public tunnel can
temporarily return a plain-text `404` or an nginx `502` even though the VM is
running. A ready endpoint returns `200` from `/health`, JSON from `/v1/models`,
and OpenAI-compatible JSON from `/v1/chat/completions`.

The planned large-model evaluation is
`Qwen/Qwen3-235B-A22B-Thinking-2507`; the intended production model is
`NousResearch/Hermes-4-70B`. Do not use either model for endpoint plumbing tests.
A future Nebius Job will execute the finite weekly pipeline, while the Endpoint
continues to provide reusable model inference until that architecture changes.

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
