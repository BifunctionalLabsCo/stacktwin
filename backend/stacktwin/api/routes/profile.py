import hashlib
import os
import tempfile
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from stacktwin.profile.schema import DeveloperProfile
from stacktwin.storage.factory import get_storage

router = APIRouter()


@router.post("/upload")
async def upload_profile(
    file: Annotated[UploadFile, File()],
    user_id: Annotated[str, Query(description="User email address")],
):
    filename = file.filename or "profile.txt"
    if not filename.lower().endswith((".pdf", ".txt")):
        raise HTTPException(status_code=400, detail="Only PDF and TXT files supported")

    try:
        content = await file.read()
        source_hash = hashlib.sha256(content).hexdigest()
        storage = get_storage()
        existing_profile = storage.load_profile(user_id)
        existing_hash = storage.load_profile_source_hash(user_id)

        if existing_profile and existing_hash == source_hash:
            return JSONResponse(
                content={
                    "status": "profile-cache-hit",
                    "user_id": user_id,
                    "source_hash": source_hash,
                    "profile": existing_profile.model_dump(mode="json"),
                }
            )

        if filename.lower().endswith(".txt"):
            raw_text = content.decode("utf-8")
        else:
            from stacktwin.profile.extractor import extract_text_from_pdf

            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
                    temp_file.write(content)
                    temp_path = temp_file.name
                raw_text = extract_text_from_pdf(temp_path)
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)

        if not raw_text or len(raw_text.strip()) < 50:
            raise HTTPException(status_code=422, detail="Could not extract enough text from file")

        api_key = os.getenv("NEBIUS_TOKEN") or os.getenv("NEBIUS_API_KEY", "")
        if api_key:
            from stacktwin.profile.builder import build_profile_from_text

            profile = build_profile_from_text(raw_text, source="cv")
        else:
            profile = DeveloperProfile(
                name=user_id.split("@")[0], profile_source="cv", raw_text=raw_text[:500]
            )

        storage.save_profile(user_id, profile, source_hash=source_hash)

        return JSONResponse(
            content={
                "status": "computed",
                "user_id": user_id,
                "source_hash": source_hash,
                "profile": profile.model_dump(mode="json"),
            }
        )

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.get("/current")
def get_current_profile(user_id: str = Query(..., description="User email address")):
    storage = get_storage()
    profile = storage.load_profile(user_id)

    if not profile:
        raise HTTPException(status_code=404, detail="No profile found. Upload a CV first.")

    return JSONResponse(content=profile.model_dump())


@router.post("/manual")
def create_manual_profile(
    profile: DeveloperProfile, user_id: str = Query(..., description="User email address")
):
    storage = get_storage()
    storage.save_profile(user_id, profile)

    return JSONResponse(
        content={"status": "ok", "user_id": user_id, "profile": profile.model_dump()}
    )
