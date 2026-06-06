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

## Performance Direction

Use fast, mature tooling by default: `uv`, `ruff`, `pydantic-core` through Pydantic, `orjson`, and `uvicorn[standard]`. Prefer Rust-backed or native-accelerated libraries when they fit the problem and keep the architecture simple.
