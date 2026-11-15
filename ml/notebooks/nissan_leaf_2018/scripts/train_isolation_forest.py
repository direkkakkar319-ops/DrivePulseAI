"""Run the separately versioned battery Isolation Forest experimental baseline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from nissan_leaf_isolation.pipeline import main

if __name__ == "__main__":
    main()
