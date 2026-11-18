"""Run the reusable Nissan Leaf preparation package from the repository checkout."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "ml/src"))
from nissan_leaf_preparation.pipeline import main

if __name__ == "__main__":
    main()
