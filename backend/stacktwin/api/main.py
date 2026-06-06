from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from stacktwin.pipeline.ingest import fetch_all


ROOT_DIR = Path(__file__).resolve().parents[3]
FRONTEND_OUT_DIR = ROOT_DIR / "src" / "out"


class IngestionSummary(BaseModel):
    total: int
    by_source: dict[str, int]


app = FastAPI(
    title="StackTwin",
    description="Weekly developer learning modules powered by serverless AI.",
    version="0.1.0",
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/ingest", response_model=IngestionSummary)
def run_ingestion(limit_per_source: int = 30) -> IngestionSummary:
    articles = fetch_all(limit_per_source=limit_per_source)
    by_source: dict[str, int] = {}

    for article in articles:
        by_source[article.source] = by_source.get(article.source, 0) + 1

    return IngestionSummary(total=len(articles), by_source=by_source)


if FRONTEND_OUT_DIR.exists():
    next_static_dir = FRONTEND_OUT_DIR / "_next"
    assets_dir = FRONTEND_OUT_DIR / "assets"

    if next_static_dir.exists():
        app.mount("/_next", StaticFiles(directory=next_static_dir), name="next-static")

    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/{path:path}", response_model=None)
def serve_frontend(path: str) -> FileResponse | dict[str, str]:
    requested = FRONTEND_OUT_DIR / path

    if requested.is_file():
        return FileResponse(requested)

    index = FRONTEND_OUT_DIR / "index.html"
    if index.exists():
        return FileResponse(index)

    return {
        "status": "frontend-not-built",
        "detail": "Run npm run build, then serve with uvicorn stacktwin.api.main:app.",
    }
