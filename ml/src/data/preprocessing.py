import pandas as pd
import numpy as np

from pathlib import Path
from loaders import load_ai4i, load_cmapss, load_simulated

class PreProcessing:
    def clean(df: pd.DataFrame) -> pd.DataFrame:
        return df.drop_duplicates()

    # def scale(df, scaler=None)-> (pd.DataFrame, scaler):


    # def make_time_windows(df, window_size, step) -> np.ndarray:


    # def train_val_test_split(df, val_frac, test_frac, time_ordered=False):



PROJECT_ROOT = Path(__file__).resolve().parents[3]
ai4i_path = PROJECT_ROOT / "data" / "failure_classification" / "raw" / "predictive_maintenance.csv"
cmapss_path = PROJECT_ROOT / "data" / "RUL_score" / "raw"
simulated_path = PROJECT_ROOT / "data" / "anomly_detection" / "raw"
