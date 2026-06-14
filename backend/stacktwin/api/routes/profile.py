import json
import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from stacktwin.profile.extractor import extract_text_from_string
from stacktwin.profile.schema import DeveloperProfile


router = APIRouter()

PROFILES_DIR = "profiles"


@router.post("/upload")
async def upload_profile(file: UploadFile = File(...)):
    """
    Accept a CV or resume as PDF or TXT.
    Extract text, build developer profile via Nebius LLM.
    Save profile to profiles/ directory.
    """
    if not file.filename.endswith((".pdf", ".txt")):
        raise HTTPException(status_code=400, detail="Only PDF and TXT files are supported")

    try:
        content = await file.read()

        # Save uploaded file temporarily
        temp_path = f"temp_{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(content)

        # Extract text based on file type
        if file.filename.endswith(".txt"):
            raw_text = content.decode("utf-8")
        else:
            from stacktwin.profile.extractor import extract_text_from_pdf
            raw_text = extract_text_from_pdf(temp_path)

        # Clean up temp file
        os.remove(temp_path)

        if not raw_text or len(raw_text.strip()) < 50:
            raise HTTPException(status_code=422, detail="Could not extract enough text from file")

        # Build profile via Nebius (or return stub if no key)
        api_key = os.getenv("NEBIUS_API_KEY", "")
        if api_key:
            from stacktwin.profile.builder import build_profile_from_text
            profile = build_profile_from_text(raw_text, source="cv")
        else:
            # Stub profile for development
            profile = DeveloperProfile(
                name="Developer",
                profile_source="cv",
                raw_text=raw_text[:500]
            )

        # Save profile to disk
        os.makedirs(PROFILES_DIR, exist_ok=True)
        profile_path = os.path.join(PROFILES_DIR, "profile.json")
        with open(profile_path, "w") as f:
            json.dump(profile.model_dump(), f, indent=2)

        return JSONResponse(content={
            "status": "ok",
            "profile": profile.model_dump(),
            "saved_to": profile_path
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/current")
def get_current_profile():
    """
    Return the current saved developer profile.
    """
    profile_path = os.path.join(PROFILES_DIR, "profile.json")
    if not os.path.exists(profile_path):
        raise HTTPException(status_code=404, detail="No profile found. Upload a CV first.")

    with open(profile_path) as f:
        data = json.load(f)

    return JSONResponse(content=data)


@router.post("/manual")
def create_manual_profile(profile: DeveloperProfile):
    """
    Create a profile manually without CV upload.
    Useful for onboarding form in the frontend.
    """
    os.makedirs(PROFILES_DIR, exist_ok=True)
    profile_path = os.path.join(PROFILES_DIR, "profile.json")

    with open(profile_path, "w") as f:
        json.dump(profile.model_dump(), f, indent=2)

    return JSONResponse(content={
        "status": "ok",
        "profile": profile.model_dump()
    })