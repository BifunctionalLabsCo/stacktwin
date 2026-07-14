import hashlib
import hmac
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from stacktwin.api.routes import digest, profile, track

load_dotenv()


app = FastAPI(
    title="StackTwin API",
    description="Personalised weekly learning intelligence for developers",
    version="0.1.0"
)

# Register routes
app.include_router(profile.router, prefix="/api/profile", tags=["profile"])
app.include_router(digest.router, prefix="/api/digest", tags=["digest"])
app.include_router(track.router, prefix="/api/track", tags=["track"])

AUTH_COOKIE = "stacktwin_session"


def _session_value(password: str) -> str:
    return hmac.new(password.encode(), b"stacktwin-session", hashlib.sha256).hexdigest()


@app.middleware("http")
async def password_gate(request: Request, call_next):
    password = os.getenv("STACKTWIN_APP_PASSWORD")
    # The prefetch route authenticates machine callers with its own schedule
    # token. It must reach that route so the token can be verified there.
    public_paths = {"/login", "/api/health", "/api/digest/prefetch"}
    if (
        not password
        or request.url.path in public_paths
        or request.url.path.startswith("/api/auth/")
    ):
        return await call_next(request)
    valid = request.cookies.get(AUTH_COOKIE)
    if valid and hmac.compare_digest(valid, _session_value(password)):
        return await call_next(request)
    if request.url.path.startswith("/api/"):
        return HTMLResponse('{"detail":"Sign in required."}', status_code=401)
    return RedirectResponse(url="/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_form():
    return """<main style='max-width:24rem;margin:10vh auto;font-family:system-ui'>
    <h1>StackTwin</h1><p>Enter the shared access password.</p>
    <form method='post' action='/api/auth/login'>
    <input name='password' type='password' autofocus required>
    <button type='submit'>Continue</button></form></main>"""


@app.post("/api/auth/login")
def login(password: str = Form(...)):
    expected = os.getenv("STACKTWIN_APP_PASSWORD")
    if not expected or not hmac.compare_digest(password, expected):
        return HTMLResponse("Invalid password.", status_code=401)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        AUTH_COOKIE,
        _session_value(expected),
        httponly=True,
        samesite="lax",
        secure=os.getenv("STACKTWIN_COOKIE_SECURE", "false").lower() == "true",
    )
    return response


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
        return {
            "message": "StackTwin API running. Frontend not built yet. "
            "Run npm run build inside src/."
        }
