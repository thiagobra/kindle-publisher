#!/usr/bin/env python3
"""kindle-publisher mobile launcher for PyDroid 3.

How to use on your Android phone:
    1. Install PyDroid 3 from the Play Store.
    2. Open Pip in PyDroid 3 and install:  reportlab, ebooklib
    3. Copy this project folder to your phone
       (e.g. /storage/emulated/0/kindle-publisher/).
    4. Edit the settings below to point to your input file.
    5. Tap Run.

Credentials for --kindle:
    Create a file called kindle.cfg next to this script (or in
    /storage/emulated/0/) with this content:

        [kindle]
        KINDLE_EMAIL = you@kindle.com
        SENDER_EMAIL = you@gmx.com
        SENDER_PASS  = yourpassword
"""

from __future__ import annotations

import os
import sys

# ---------------------------------------------------------------------------
# SETTINGS — edit these before tapping Run
# ---------------------------------------------------------------------------

# Path to your input file (JSON or Markdown).
# On Android, files are usually under /storage/emulated/0/
INPUT_FILE = "/storage/emulated/0/kindle-publisher/sample.json"

# What to generate: set True / False
GENERATE_PDF = True
GENERATE_EPUB = True
SEND_TO_KINDLE = False

# Output directory (None = same folder as input file)
OUTPUT_DIR = None

# ---------------------------------------------------------------------------
# Runner — no need to edit below this line
# ---------------------------------------------------------------------------


def _ensure_project_on_path() -> None:
    """Make sure the project root is importable regardless of cwd."""
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    os.chdir(project_root)


def main() -> None:
    _ensure_project_on_path()

    from publish import run  # noqa: local import after path setup

    if not os.path.isfile(INPUT_FILE):
        print(f"[ERROR] Input file not found: {INPUT_FILE}")
        print("Edit INPUT_FILE at the top of mobile_publish.py")
        return

    if not (GENERATE_PDF or GENERATE_EPUB or SEND_TO_KINDLE):
        print("[ERROR] Enable at least one of: GENERATE_PDF, GENERATE_EPUB, SEND_TO_KINDLE")
        return

    print(f"Input:  {INPUT_FILE}")
    print(f"PDF={GENERATE_PDF}  EPUB={GENERATE_EPUB}  Kindle={SEND_TO_KINDLE}")
    print("-" * 40)

    try:
        result = run(
            input_path=INPUT_FILE,
            pdf=GENERATE_PDF,
            epub=GENERATE_EPUB,
            kindle=SEND_TO_KINDLE,
            output_dir=OUTPUT_DIR,
        )
        print("-" * 40)
        print("Done!")
        if result.get("pdf"):
            print(f"  PDF:   {result['pdf']}")
        if result.get("epub"):
            print(f"  EPUB:  {result['epub']}")
        if result.get("sent"):
            print(f"  Kindle: sent!")
    except Exception as exc:
        print(f"\n[ERROR] {exc}")


if __name__ == "__main__":
    main()
