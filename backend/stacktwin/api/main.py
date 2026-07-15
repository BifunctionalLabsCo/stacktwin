# ruff: noqa: E501

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

LOGIN_PAGE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>StackTwin | Your learning, in motion</title>
    <style>
      :root { color-scheme: dark; }
      * { box-sizing: border-box; }
      body {
        min-height: 100vh; margin: 0; display: grid; place-items: center;
        padding: 24px; color: #e8faf4;
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: radial-gradient(circle at 15% 15%, rgb(64 255 181 / .16), transparent 28rem),
          radial-gradient(circle at 85% 86%, rgb(255 79 129 / .20), transparent 30rem), #061f17;
      }
      main { width: min(100%, 66rem); display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(18rem, .8fr); overflow: hidden; border: 1px solid #1a4035; border-radius: 20px; background: #0a2e23; box-shadow: 0 24px 80px rgb(0 0 0 / .38); }
      section { padding: clamp(2rem, 6vw, 5rem); }
      .intro { border-right: 1px solid #1a4035; }
      .mark { display: grid; width: 2.6rem; height: 2.6rem; place-items: center; border-radius: 9px; color: #032b22; background: linear-gradient(135deg, #ff4f81, #40ffb5); font-size: .75rem; font-weight: 900; letter-spacing: .06em; }
      .eyebrow { margin: 2.5rem 0 1rem; color: #40ffb5; font-size: .75rem; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; }
      h1 { max-width: 13ch; margin: 0 0 1.25rem; font-size: clamp(2.35rem, 5vw, 4.4rem); line-height: .98; letter-spacing: -.06em; }
      p { max-width: 56ch; margin: 0 0 1rem; color: #a7d7c7; font-size: 1rem; line-height: 1.65; }
      .promise { color: #e8faf4; font-weight: 650; }
      .gate { display: grid; align-content: center; background: rgb(3 43 34 / .48); }
      .gate h2 { margin: 0 0 .75rem; font-size: 1.55rem; letter-spacing: -.03em; }
      .gate p { font-size: .92rem; }
      form { display: grid; gap: 12px; margin-top: 2rem; }
      label { color: #a7d7c7; font-size: .8rem; font-weight: 750; }
      input { min-height: 48px; width: 100%; padding: 0 14px; border: 1px solid #326454; border-radius: 8px; outline: none; color: #e8faf4; background: #061f17; font: inherit; }
      input:focus { border-color: #40ffb5; box-shadow: 0 0 0 3px rgb(64 255 181 / .16); }
      button { min-height: 48px; border: 0; border-radius: 8px; color: #032b22; background: #40ffb5; cursor: pointer; font: inherit; font-weight: 850; transition: transform .16s ease, filter .16s ease; }
      button:hover { filter: brightness(1.06); transform: translateY(-1px); }
      .fine { margin-top: 1.2rem; color: #7ab8a0; font-size: .78rem; }
      @media (max-width: 720px) { main { grid-template-columns: 1fr; } .intro { border-right: 0; border-bottom: 1px solid #1a4035; } section { padding: 2.25rem; } .eyebrow { margin-top: 1.75rem; } }
    </style>
  </head>
  <body>
    <main>
      <section class="intro">
        <div class="mark" aria-hidden="true">ST</div>
        <p class="eyebrow">A learning twin for people who build</p>
        <h1>Keep learning, without chasing what to learn.</h1>
        <p>Continuous learning is hard: finding current, relevant material takes time, and choosing the next useful thing can feel like work itself.</p>
        <p>StackTwin creates a lightweight digital twin of your interests, goals, and working stack. It brings together fresh signals, turns them into focused learning digests, and helps you move forward with the right lessons.</p>
        <p class="promise">Set your direction once. Let your StackTwin handle what comes next.</p>
      </section>
      <section class="gate">
        <h2>Welcome back</h2>
        <p>Enter the shared access password to open your learning workspace.</p>
        <form method="post" action="/api/auth/login">
          <label for="password">Access password</label>
          <input id="password" name="password" type="password" autocomplete="current-password" autofocus required>
          <button type="submit">Open StackTwin</button>
        </form>
        <p class="fine">Your profile shapes the feed. You stay in control.</p>
      </section>
    </main>
  </body>
</html>"""


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
    return LOGIN_PAGE


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
