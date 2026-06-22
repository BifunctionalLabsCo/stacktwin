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

## Classroom Experience

The compiled app opens on the current weekly track. It includes lesson launch cards, a lesson player, progress scoped to the generated track, source provenance, and a compact explanation of which profile signals influenced the week. The archive at `/archive/` lists earlier tracks and opens their source-backed learning material inline.

Set `NEXT_PUBLIC_STACKTWIN_USER_ID` before `npm run build` to choose the learner whose profile and archive the static app requests. The default is `demo@stacktwin.dev`.

## Storage And Idempotency

Local development uses JSON files by default. Production can use Nebius Object Storage through the same `StorageBackend` contract:

1. Copy `.env.example` to `.env` and create a Nebius Object Storage bucket plus a service-account access key.
2. Populate the `NEBIUS_S3_*` values.
3. Set `STORAGE_BACKEND=nebius`.
4. Build and serve the unified app with the commands in the Development section.

Profiles and weekly tracks retain identical API behavior in either backend. Uploaded CV bytes are SHA-256 hashed; an identical re-upload returns the stored profile without another model extraction. Digest generation checks the user and Monday week key first; retries return the completed track instead of running ingestion, scoring, and generation again.

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
