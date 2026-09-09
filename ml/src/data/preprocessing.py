from pathlib import Path

from loaders import load_ai4i, load_cmapss, load_simulated

def clean(df):
    df = df.drop_duplicates()

PROJECT_ROOT = Path(__file__).resolve().parents[3]

ai4i_path = PROJECT_ROOT / "data" / "failure_classification" / "raw" / "predictive_maintenance.csv"
df = load_ai4i(ai4i_path)
