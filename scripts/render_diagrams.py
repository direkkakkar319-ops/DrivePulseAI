"""
Render all .mmd Mermaid diagram files in docs/diagrams/ to SVG using mermaid.ink API.

Usage:
    python scripts/render_diagrams.py

Requires only the Python standard library (urllib, base64, json).
Outputs .svg files alongside the .mmd source files in docs/diagrams/.
"""

import base64
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Force UTF-8 stdout on Windows to avoid charmap encoding errors
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DIAGRAMS_DIR = Path(__file__).resolve().parent.parent / "docs" / "diagrams"
MERMAID_INK_BASE = "https://mermaid.ink/svg/"


def mmd_to_svg_url(mermaid_code: str) -> str:
    """Build the mermaid.ink URL for an SVG render of the given Mermaid code."""
    payload = json.dumps({"code": mermaid_code, "mermaid": {"theme": "dark"}})
    encoded = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")
    return f"{MERMAID_INK_BASE}{encoded}"


def render_file(mmd_path: Path) -> Path:
    """Fetch the SVG for a .mmd file and write it next to the source."""
    mermaid_code = mmd_path.read_text(encoding="utf-8").strip()
    url = mmd_to_svg_url(mermaid_code)
    svg_path = mmd_path.with_suffix(".svg")

    print(f"  Rendering {mmd_path.name} -> {svg_path.name} ...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DrivePulseAI/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            svg_data = resp.read()
        svg_path.write_bytes(svg_data)
        print(f"    OK {svg_path.name} ({len(svg_data):,} bytes)")
        return svg_path
    except urllib.error.HTTPError as e:
        print(f"    FAIL HTTP {e.code}: {e.reason}")
        raise
    except urllib.error.URLError as e:
        print(f"    FAIL Network error: {e.reason}")
        raise


def main() -> None:
    mmd_files = sorted(DIAGRAMS_DIR.glob("*.mmd"))
    if not mmd_files:
        print(f"No .mmd files found in {DIAGRAMS_DIR}")
        sys.exit(1)

    print(f"Found {len(mmd_files)} diagram(s) in {DIAGRAMS_DIR}\n")

    successes = []
    failures = []
    for mmd_path in mmd_files:
        try:
            svg_path = render_file(mmd_path)
            successes.append(svg_path)
        except Exception as e:
            failures.append((mmd_path, str(e)))

    print(f"\nDone: {len(successes)} rendered, {len(failures)} failed.")
    if failures:
        for path, err in failures:
            print(f"  FAILED: {path.name} — {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
