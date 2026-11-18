import sys
from pathlib import Path

# Ensure repo root and ml directory are in sys.path regardless of execution directory
REPO_ROOT = Path(__file__).resolve().parents[2]
ML_ROOT = Path(__file__).resolve().parents[1]

for path_dir in (REPO_ROOT, ML_ROOT):
    path_str = str(path_dir)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
