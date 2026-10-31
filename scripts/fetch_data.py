"""Download the organisers' Challenge #1 dataset (train_data.csv, test_data.csv) into dataset/.

Source: the Autonomous SG 2026 Google Drive folder "Challenge 1 Airbus", which holds the ESA Collision Avoidance
Challenge files (CC BY 4.0, Zenodo record 4463683).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FOLDER = "https://drive.google.com/drive/folders/14sDlmlyjWPHvGakadqK72GSDFUhuINvW"
OUT = Path(__file__).resolve().parents[1] / "dataset"
EXPECTED_BYTES = {"train_data.csv": 233_600_296, "test_data.csv": 35_303_060}


def main() -> int:
    if all((OUT / n).exists() and (OUT / n).stat().st_size == s for n, s in EXPECTED_BYTES.items()):
        print(f"dataset already present in {OUT}")
        return 0
    try:
        import gdown  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "gdown"], check=True)
    subprocess.run([sys.executable, "-m", "gdown", FOLDER, "-O", str(OUT)], check=True)
    for name, size in EXPECTED_BYTES.items():
        got = (OUT / name).stat().st_size
        if got != size:
            print(f"{name}: expected {size} bytes, got {got}", file=sys.stderr)
            return 1
    print(f"dataset ready in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
