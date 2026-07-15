# StackTwin

StackTwin turns a week of technical noise into a focused, source-backed learning
track. It uses a learner's digital twin, their goals, interests, and time
budget, to shape what appears next.

## Evaluator quick start

You need Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 20+, and npm.
No Nebius account, GPU, Object Storage bucket, or API key is required to review
the finished classroom experience.

1. Install dependencies and create local settings:

   ```bash
   uv sync --extra dev
   npm install --prefix src
   cp .env.example .env
   ```

2. Build the complete preview classroom:

   ```bash
   NEXT_PUBLIC_STACKTWIN_DEMO_MODE=true npm run build
   ```

3. Start the unified application:

   ```bash
   uv run uvicorn stacktwin.api.main:app --app-dir backend --reload
   ```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Use the password set in
`.env` (`change-this-before-deploy` in the example) and explore the Engineer,
Creator, Researcher, and New Twin paths.

## What to evaluate

- A finished weekly classroom: launch cards, source provenance, lesson player,
  completion state, progress, and archive.
- Separate, pre-populated Engineer, Creator, and Researcher twins, plus a New
  Twin flow for personalized setup.
- Clear preparation and generation states rather than an opaque pipeline
  dashboard.
- A serverless design where expensive work is finite, durable, and triggered
  only when needed.

## Live Nebius pipeline

The preview above is deliberately credential-free. The real pipeline uses
finite Nebius Serverless AI Jobs and Nebius Object Storage: one shared weekly
prefetch, followed by profile-specific ranking, digest creation, and reusable
lesson modules after a learner selects Generate.

For a fully reproducible live setup, including creating an isolated S3 bucket,
service-account access key, worker image, and required environment variables,
see [Nebius pipeline setup](docs/nebius-pipeline.md).

## Verify

```bash
npm run build
uv run pytest -q
```

## Repository layout

- `src/`: Next.js learning experience, exported to static assets.
- `backend/stacktwin/`: FastAPI API, profiles, ingestion, ranking, digest, and
  module generation.
- `backend/stacktwin/pipeline/Dockerfile`: finite GPU Job worker.
- `backend/stacktwin/api/Dockerfile`: CPU-only web application image.

## License

MIT. See [LICENSE](LICENSE).
