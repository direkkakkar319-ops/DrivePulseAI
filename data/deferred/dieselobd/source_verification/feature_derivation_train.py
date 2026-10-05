import pandas as pd
import numpy as np

df = pd.read_csv("MASTER_TRAIN.csv")
df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

eps = 1e-9  # numerical safety

# ----------------------------
# Identify label columns (P-codes + Mode)
# ----------------------------
label_cols = [col for col in df.columns if col.startswith("P")]
if "Mode" in df.columns:
    label_cols.append("Mode")

# Keep labels aside (do NOT use in feature engineering)
labels = df[label_cols].copy() if label_cols else pd.DataFrame()

# ----------------------------
# Feature base (exclude labels)
# ----------------------------
feature_df = df.drop(columns=label_cols)

# ----------------------------
# Core pressure features
# ----------------------------
feature_df["MAP_minus_BARO"] = feature_df["MAP"] - feature_df["BARO"]

feature_df["MAP_minus_BARO_per_IAT"] = feature_df["MAP_minus_BARO"] / (feature_df["IAT"] + eps)

feature_df["MAP_minus_BARO_per_LOAD"] = feature_df["MAP_minus_BARO"] / (feature_df["LOAD_PCT"] + eps)

feature_df["MAP_per_IAT"] = feature_df["MAP"] / (feature_df["IAT"] + eps)

feature_df["MAP_per_RPM"] = feature_df["MAP"] / (feature_df["RPM"] + eps)

# ----------------------------
# MAF features
# ----------------------------
feature_df["MAF_per_MAP"] = feature_df["MAF"] / (feature_df["MAP"] + eps)

feature_df["MAF_per_MAP_RPM"] = feature_df["MAF"] / ((feature_df["MAP"] * feature_df["RPM"]) + eps)

feature_df["MAF_per_LOAD"] = feature_df["MAF"] / (feature_df["LOAD_PCT"] + eps)

feature_df["MAF_per_RPM"] = feature_df["MAF"] / (feature_df["RPM"] + eps)

# ----------------------------
# LOAD features
# ----------------------------
feature_df["LOAD_PCT_per_VSS"] = feature_df["LOAD_PCT"] / (feature_df["VSS"] + eps)

feature_df["LOAD_per_RPM"] = feature_df["LOAD_PCT"] / (feature_df["RPM"] + eps)

feature_df["LOAD_per_MAP"] = feature_df["LOAD_PCT"] / (feature_df["MAP"] + eps)

feature_df["MAP_minus_BARO_per_LOAD"] = feature_df["MAP_minus_BARO"] / (feature_df["LOAD_PCT"] + eps)

# ----------------------------
# Fuel system
# ----------------------------
feature_df["FRP_per_MAF"] = feature_df["FRP"] / (feature_df["MAF"] + eps)

feature_df["FRP_per_LOAD"] = feature_df["FRP"] / (feature_df["LOAD_PCT"] + eps)

# ----------------------------
# Electrical
# ----------------------------
feature_df["VPWR_per_RPM"] = feature_df["VPWR"] / (feature_df["RPM"] + eps)

feature_df["Voltage_Change"] = feature_df["VPWR"].diff().fillna(0)

# ----------------------------
# Thermal
# ----------------------------
feature_df["ECT_minus_IAT"] = feature_df["ECT"] - feature_df["IAT"]

feature_df["ECT_minus_AAT"] = feature_df["ECT"] - feature_df["AAT"]

feature_df["IAT_minus_AAT"] = feature_df["IAT"] - feature_df["AAT"]

# ----------------------------
# Dynamics
# ----------------------------
feature_df["RPM_per_VSS"] = feature_df["RPM"] / (feature_df["VSS"] + eps)

# ----------------------------
# Round everything (features only)
# ----------------------------
feature_df = feature_df.round(10)

# ----------------------------
# Reattach labels (unchanged)
# ----------------------------
final_df = pd.concat([feature_df, labels], axis=1)

# ----------------------------
# Save output
# ----------------------------
final_df.to_csv("E_Train_Raw_PIDs.csv", index=False)

print("Done: E_Raw_PIDs.csv saved with features + preserved P-code labels + Mode")