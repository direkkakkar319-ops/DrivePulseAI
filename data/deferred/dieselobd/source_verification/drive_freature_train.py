import pandas as pd
import numpy as np
from scipy.stats import linregress

# =========================
# CONFIG
# =========================
INPUT_FILE = "E_Train_Raw_PIDs.csv"
WINDOW_SIZES = [4, 12, 20]
OUTPUT_PREFIX = "Trainset_window_"

# =========================
# LOAD DATA
# =========================
df = pd.read_csv(INPUT_FILE, low_memory=False)

# Remove unwanted columns
df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

# Identify label columns (P-codes + Mode)
pcode_cols = [col for col in df.columns if col.startswith("P")]
label_cols = pcode_cols + ["Mode"]

# Convert feature columns to numeric
feature_cols = [col for col in df.columns if col not in label_cols]
df[feature_cols] = df[feature_cols].apply(pd.to_numeric, errors="coerce")

# Optional: clean NaNs
df = df.dropna().reset_index(drop=True)

# =========================
# FEATURE FUNCTIONS
# =========================
def compute_features(window):
    features = {}

    for col in feature_cols:
        data = window[col].values

        if len(data) < 2:
            continue

        # Basic stats
        features[f"{col}_mean"] = np.mean(data)
        features[f"{col}_min"] = np.min(data)
        features[f"{col}_max"] = np.max(data)
        features[f"{col}_std"] = np.std(data)

        # Delta
        features[f"{col}_delta"] = data[-1] - data[0]

        # Slope
        x = np.arange(len(data))
        slope, _, _, _, _ = linregress(x, data)
        features[f"{col}_slope"] = slope

        # RMS
        features[f"{col}_rms"] = np.sqrt(np.mean(data**2))

        # Time to peak
        features[f"{col}_time_to_peak"] = np.argmax(data)

        # Zero Crossing Rate
        zero_crossings = np.where(np.diff(np.sign(data)))[0]
        features[f"{col}_zcr"] = len(zero_crossings) / len(data)

        # IQR
        q75, q25 = np.percentile(data, [75, 25])
        features[f"{col}_iqr"] = q75 - q25

    return features

# =========================
# MAIN PROCESS
# =========================
def process_window(df, window_size):
    rows = []

    for i in range(len(df) - window_size + 1):
        window = df.iloc[i:i+window_size]

        feats = compute_features(window)

        # =========================
        # Labels = last row in window
        # =========================
        last_row = window.iloc[-1]

        # Add all P-codes
        for col in pcode_cols:
            feats[col] = last_row[col]

        # Add Mode (not aggregated)
        feats["Mode"] = last_row["Mode"]

        rows.append(feats)

    return pd.DataFrame(rows)

# =========================
# MAIN
# =========================
def main():
    for w in WINDOW_SIZES:
        print(f"Processing window size = {w}")

        result = process_window(df, w)

        output_file = f"{OUTPUT_PREFIX}{w}.csv"
        result.to_csv(output_file, index=False)

        print(f"Saved: {output_file}")

if __name__ == "__main__":
    main()
