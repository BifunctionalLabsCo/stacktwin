import os
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from stacktwin.profile.schema import DeveloperProfile
from stacktwin.storage.factory import get_storage
from stacktwin.profile.extractor import hash_cv_content


router = APIRouter()


@router.post("/upload")
async def upload_profile(
    file: UploadFile = File(...),
    user_id: str = Query(..., description="User email address")
):
    if not file.filename.endswith((".pdf", ".txt")):
        raise HTTPException(status_code=400, detail="Only PDF and TXT files supported")

    try:
        content = await file.read()
        cv_hash = hash_cv_content(content)

        storage = get_storage()

        # Check for an existing profile with the same CV hash
        existing_profile = storage.load_profile(user_id)
        if existing_profile and existing_profile.cv_hash == cv_hash:
            return JSONResponse(content={
                "status": "profile_cache_hit",
                "user_id": user_id,
                "profile": existing_profile.model_dump()
            })

        # New or changed CV — extract fresh
        temp_path = f"temp_{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(content)

        if file.filename.endswith(".txt"):
            raw_text = content.decode("utf-8")
        else:
            from stacktwin.profile.extractor import extract_text_from_pdf
            raw_text = extract_text_from_pdf(temp_path)

        os.remove(temp_path)

        if not raw_text or len(raw_text.strip()) < 50:
            raise HTTPException(status_code=422, detail="Could not extract enough text from file")

        api_key = os.getenv("NEBIUS_API_KEY", "")
        if api_key:
            from stacktwin.profile.builder import build_profile_from_text
            profile = build_profile_from_text(raw_text, source="cv")
        else:
            profile = DeveloperProfile(
                name=user_id.split("@")[0],
                profile_source="cv",
                raw_text=raw_text[:500]
            )

        profile.cv_hash = cv_hash
        storage.save_profile(user_id, profile)

        return JSONResponse(content={
            "status": "computed",
            "user_id": user_id,
            "profile": profile.model_dump()
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/current")
def get_current_profile(
    user_id: str = Query(..., description="User email address")
):
    storage = get_storage()
    profile = storage.load_profile(user_id)

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="No profile found. Upload a CV first."
        )

    return JSONResponse(content=profile.model_dump())


@router.post("/manual")
def create_manual_profile(
    profile: DeveloperProfile,
    user_id: str = Query(..., description="User email address")
):
    storage = get_storage()
    storage.save_profile(user_id, profile)

    return JSONResponse(content={
        "status": "ok",
        "user_id": user_id,
        "profile": profile.model_dump()
    })