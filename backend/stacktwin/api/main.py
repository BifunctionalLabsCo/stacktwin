from dotenv import load_dotenv
load_dotenv()
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from stacktwin.api.routes import profile, digest, track
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(
    title="StackTwin API",
    description="Personalised weekly learning intelligence for developers",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(profile.router, prefix="/api/profile", tags=["profile"])
app.include_router(digest.router, prefix="/api/digest", tags=["digest"])
app.include_router(track.router, prefix="/api/track", tags=["track"])


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


# Serve compiled Next.js frontend
# Built by: npm run build inside src/
FRONTEND_DIR = Path(__file__).parent.parent.parent.parent / "src" / "out"

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    @app.get("/")
    def root():
        return {"message": "StackTwin API running. Frontend not built yet — run npm run build inside src/"}