"""Serve the API (and, for local use, the console) on http://localhost:8000.

With FRONTEND_URL set (e.g. in .env), only the API is served and / redirects to that URL.
"""

import os

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def main() -> None:
    from ca_triage.env import load_env

    load_env()
    if not os.environ.get("FRONTEND_URL") and not (WEB / "dist").exists():
        npm = shutil.which("npm")
        if npm is None:
            print("npm not found; serving API only", file=sys.stderr)
        else:
            subprocess.run([npm, "install"], cwd=WEB, check=True)
            subprocess.run([npm, "run", "build"], cwd=WEB, check=True)
    import uvicorn

    uvicorn.run("ca_triage.api:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()
