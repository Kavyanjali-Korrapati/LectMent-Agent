"""
LectMent — quick-start launcher.
Run this from the repo root:

    python start.py

This ensures Python's sys.path is correct regardless of where you call it from.
"""
import sys
import os
from pathlib import Path

# ── Guarantee the repo root is always on sys.path ─────────────────────────────
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Change CWD to repo root so relative paths (e.g. .env) resolve correctly ───
os.chdir(ROOT)

# ── Launch uvicorn ─────────────────────────────────────────────────────────────
import uvicorn

if __name__ == "__main__":
    print(f"Starting LectMent backend from: {ROOT}")
    print("API docs: http://localhost:8000/docs")
    print("Press Ctrl+C to stop.\n")
    uvicorn.run(
        "backend.main:app",
        host    = "127.0.0.1",
        port    = 8000,
        reload  = True,
        reload_dirs = [str(ROOT / "backend")],
    )
