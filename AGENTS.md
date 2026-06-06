# Agent Guidelines

## Product Direction

StackTwin is a high-fidelity weekly learning interface backed by a serverless AI pipeline. Treat pipeline controls as supporting infrastructure. The primary product surface is the learner experience: weekly launch cards, a lesson player, progress tracking, source provenance, and reusable learning modules.

## Repository Shape

- `backend/stacktwin/` contains the FastAPI service, profile extraction, ingestion, scoring, digest generation, and Nebius integration code.
- `src/` contains the Next.js app that compiles to static assets.
- The compiled frontend is served by FastAPI from `src/out`.
- Generated weekly tracks should be modeled as reusable learning modules, not disposable digest rows.

## Build And Serve Contract

Always build the frontend first, then serve the unified app with Uvicorn:

```bash
npm run build
uv run uvicorn stacktwin.api.main:app --app-dir backend --reload
```

Use `npm run build` as the frontend verification command, even when working only on UI. Use Uvicorn as the service runner, because backend routes are mostly triggers for cloud pipelines and should be exercised through the same FastAPI boundary that serves the compiled UI.

## Tooling

- Prefer `uv` for Python dependency management, virtual environments, scripts, and reproducible local setup.
- Prefer Astral tools when available, especially `ruff` for linting and formatting.
- Keep the Python package importable from `backend/`.
- Keep Node tooling scoped to `src/`, with root scripts delegating to it.

## Performance Bias

Prefer mature Rust-backed or native-accelerated libraries when they fit the job and do not distort the architecture. Good defaults include:

- `uv` for dependency resolution and environment management
- `ruff` for linting and formatting
- `pydantic` with `pydantic-core` for validation
- `orjson` for JSON serialization in API responses and generated artifacts
- `uvicorn[standard]`, which brings fast event-loop and HTTP parser support where available

Do not add performance libraries as decoration. Use them when they simplify the system, improve measurable throughput, or reduce operational drag.

## Writing Style

- Use em dashes only when they are grammatically correct in prose.
- Never use em dashes as visual separators, list decoration, or a substitute for clear structure.
- Prefer a colon, semicolon, comma, or a new sentence when the dash is only doing formatting work.
- Keep README and UI language sharp, product-minded, and specific.
