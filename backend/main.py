"""
LectMent — FastAPI application entry point.

CORRECT way to start (run from the repo ROOT, not from backend/):
    uvicorn backend.main:app --reload --port 8000
    -- OR --
    python start.py
"""
import sys
import os
import logging
import traceback
from pathlib import Path

# ── Self-healing sys.path ──────────────────────────────────────────────────────
# Ensures `import backend.xxx` works even if someone runs uvicorn from backend/
_ROOT = Path(__file__).resolve().parent.parent   # backend/main.py -> LectureAgent/
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
os.chdir(_ROOT)   # makes .env / relative paths resolve correctly

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.routers.analyze import router as analyze_router, limiter

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt= "%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("lectment.main")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title       = "LectMent",
    description = "AI-powered lecture notes assistant built on IBM watsonx.ai",
    version     = "1.0.0",
)

# Rate limiter state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — allow React dev-server + any deployed frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["*"],
    allow_methods  = ["GET", "POST"],
    allow_headers  = ["*"],
)

app.include_router(analyze_router, prefix="/api")


# ── Global catch-all: always return JSON, never plain-text HTML ───────────────
@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception):
    """
    Ensures ALL unhandled exceptions return {"detail": "..."} JSON
    instead of a plain-text "Internal Server Error" that breaks res.json().
    """
    log.error("Unhandled exception on %s %s: %s", request.method, request.url.path,
              traceback.format_exc())
    return JSONResponse(
        status_code = 500,
        content     = {"detail": f"Server error: {type(exc).__name__}: {exc}"},
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "LectMent"}
