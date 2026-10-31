"""Build the web app if needed, then serve API + console on http://localhost:8000."""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def main() -> None:
    if not (WEB / "dist").exists():
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
