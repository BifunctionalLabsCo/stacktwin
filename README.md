# StackTwin

StackTwin turns a week's worth of technical noise into a focused learning
track. It starts with a digital twin of a learner's interests and goals, then
presents source-backed lessons, progress, and an archive of reusable modules.

## Run it locally

You only need Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 20+, and
npm. A fresh checkout runs with a complete preview classroom: no cloud account,
API key, or GPU is required.

1. Install the dependencies and create local settings:

   ```bash
   uv sync --extra dev
   npm install --prefix src
   cp .env.example .env
   ```

2. Build the frontend:

   ```bash
   npm run build
   ```

3. Start StackTwin:

   ```bash
   uv run uvicorn stacktwin.api.main:app --app-dir backend --reload
   ```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) and sign in with the local
password from `.env` (`stacktwin-local` by default). The Engineer, Creator, and
Researcher twins are ready to explore immediately. Create a New Twin to inspect
the personalization flow.

## What the evaluator sees

The local build intentionally opens the complete preview classroom. It includes
launch cards, the lesson player, source provenance, progress states, the twin
switcher, and onboarding without depending on a pre-existing weekly run.

To inspect real local or Object Storage-backed tracks instead, build with:

```bash
NEXT_PUBLIC_STACKTWIN_DEMO_MODE=false npm run build
```

## Verify

```bash
npm run build
uv run pytest -q
```

## Project layout

- `src/`: Next.js learning experience, exported as static assets.
- `backend/stacktwin/`: FastAPI API and learning pipeline.
- `backend/stacktwin/api/Dockerfile`: CPU-only web image for the complete app.
- `backend/stacktwin/pipeline/Dockerfile`: finite GPU worker image.

## Optional Nebius pipeline

Nebius is optional for local evaluation. When configured, StackTwin runs one
finite Qwen Job to refresh shared weekly content, then creates profile-specific
ranking, digests, and lesson modules only after the learner selects Generate.
Artifacts are stored in Nebius Object Storage and each Job exits when finished.

See [the optional Nebius setup](docs/nebius-pipeline.md) when you want to run
the live pipeline or deploy the web app.
