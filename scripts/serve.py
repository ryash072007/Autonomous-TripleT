"""Serve the OrbitGuard API on http://localhost:8000 (API only by default).

`--with-web` also builds (if needed) and serves the console at the same address, for local use.
With FRONTEND_URL set in .env, / redirects to the hosted console.
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
    if "--with-web" in sys.argv[1:]:
        os.environ["SERVE_WEB"] = "1"
    if os.environ.get("SERVE_WEB") == "1" and not (WEB / "dist").exists():
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
