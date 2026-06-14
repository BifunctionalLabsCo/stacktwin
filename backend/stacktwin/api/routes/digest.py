import json
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse


router = APIRouter()

OUTPUTS_DIR = "outputs"
PROFILES_DIR = "profiles"


def _load_latest_digest() -> dict:
    """Find and load the most recent digest JSON file."""
    if not os.path.exists(OUTPUTS_DIR):
        raise HTTPException(status_code=404, detail="No digests found yet")

    digest_files = sorted([
        f for f in os.listdir(OUTPUTS_DIR)
        if f.startswith("digest_") and f.endswith(".json")
    ], reverse=True)

    if not digest_files:
        raise HTTPException(status_code=404, detail="No digest found. Run the pipeline first.")

    with open(os.path.join(OUTPUTS_DIR, digest_files[0])) as f:
        return json.load(f)


@router.get("/latest")
def get_latest_digest():
    """
    Return the most recent weekly digest.
    This is the primary endpoint the frontend calls.
    """
    return JSONResponse(content=_load_latest_digest())


@router.post("/run")
def run_pipeline():
    """
    Trigger the full ingestion + scoring + digest pipeline manually.
    In production this is triggered by a Nebius Job on a schedule.
    For development, call this endpoint to generate a fresh digest.
    """
    try:
        profile_path = os.path.join(PROFILES_DIR, "profile.json")
        if not os.path.exists(profile_path):
            raise HTTPException(status_code=404, detail="No profile found. Upload a CV first.")

        with open(profile_path) as f:
            profile_data = json.load(f)

        from stacktwin.profile.schema import DeveloperProfile
        from stacktwin.pipeline.ingest import fetch_all
        from stacktwin.pipeline.score import score_articles
        from stacktwin.pipeline.digest import build_digest, save_digest

        profile = DeveloperProfile(**profile_data)

        print("[pipeline] starting ingestion...")
        articles = fetch_all(limit_per_source=30)

        print("[pipeline] scoring articles...")
        scored = score_articles(articles, profile)

        print("[pipeline] building digest...")
        digest = build_digest(scored, profile, top_n=10)
        path = save_digest(digest)

        return JSONResponse(content={
            "status": "ok",
            "digest_path": path,
            "items": len(digest.items),
            "total_processed": digest.total_items_processed
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export")
def export_digest(format: str = "markdown"):
    """
    Export the latest digest in a portable format.
    Supports: markdown
    More formats coming: notion, github-course
    """
    digest = _load_latest_digest()

    if format == "markdown":
        lines = [
            f"# StackTwin Weekly Digest",
            f"**Week:** {digest.get('week_start', 'unknown')}",
            f"**Developer:** {digest.get('profile_name', 'Developer')}",
            f"**Articles processed:** {digest.get('total_items_processed', 0)}",
            "",
            "---",
            ""
        ]

        for i, item in enumerate(digest.get("items", []), 1):
            lines += [
                f"## {i}. {item['title']}",
                f"**Source:** {item['source']} | "
                f"**Reading time:** {item.get('estimated_reading_minutes', 5)} min | "
                f"**Score:** {item['score']['overall']:.2f}",
                f"**Link:** {item['url']}",
                "",
                item.get('summary', ''),
                "",
                f"> **Why this matters:** {item['score']['why_this_matters']}",
                "",
            ]

            if item.get("quiz"):
                lines.append("**Quiz:**")
                for q in item["quiz"]:
                    lines.append(f"- {q['question']}")
                lines.append("")

            lines.append("---")
            lines.append("")

        return PlainTextResponse(
            content="\n".join(lines),
            media_type="text/markdown",
            headers={"Content-Disposition": "attachment; filename=stacktwin-digest.md"}
        )

    raise HTTPException(status_code=400, detail=f"Unsupported format: {format}. Supported: markdown")