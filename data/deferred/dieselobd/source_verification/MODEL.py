import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from xgboost import XGBClassifier
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="xgboost")

# =========================
# CONFIG
# =========================
TRAIN_FILES = {4: "./trainset_window_4.csv", 12: "./trainset_window_12.csv", 20: "./trainset_window_20.csv"}
TEST_FILES = {4: "./testset_window_4.csv", 12: "./testset_window_12.csv", 20: "./testset_window_20.csv"}

LABELS = ["P0000", "P0562", "P0113", "P0102", "P0403", "P0404", "P2562", "P2015", "P2009", "P0107", "P0069", "P0089", "P0234", "P0406"]

# --- TUNING SECTION ---
# Standard threshold is 0.3. 
# We raise it for the 'noisy' models to 0.5 or 0.6 to reduce false positives.
THRESHOLDS = {
    "DEFAULT": 0.33
}

RANDOM_STATE = 42

# =========================
# DATA UTILITIES
# =========================

def process_dataframe(path):
    df = pd.read_csv(path)  
    y_list = []
    for l in LABELS:
        # Convert label column to binary (1 if code exists, 0 otherwise)
        col_bin = (df[l].fillna(0).values > 0).astype(int) if l in df.columns else np.zeros(len(df), dtype=int)
        y_list.append(col_bin)
    y = np.column_stack(y_list)
    
    # Define features to ignore (Targets and metadata)
    ignore = LABELS 
    X = df.drop(columns=[c for c in ignore if c in df.columns], errors='ignore')
    X = X.loc[:, ~X.columns.str.contains("^Unnamed")]
    X = X.apply(pd.to_numeric, errors='coerce').fillna(0)
    return X, y

def train_model(X_train, y_train_label):
    # Handle class imbalance automatically
    ratio = (np.sum(y_train_label == 0) / np.sum(y_train_label == 1)) if np.sum(y_train_label == 1) > 0 else 1
    
    
    
    model = XGBClassifier(
        objective="binary:logistic",
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        tree_method="hist",
        scale_pos_weight=ratio,
        random_state=RANDOM_STATE
    )
    model.fit(X_train, (y_train_label > 0).astype(int))
    return model

# =========================
# MAIN EXPORT PIPELINE
# =========================

def main():
    for window in [4, 12, 20]:
        print(f"\n" + "="*70)
        print(f"🌀 WINDOW SIZE: {window}")
        print("="*70)
        
        X_train, y_train = process_dataframe(TRAIN_FILES[window])
        X_test, y_test = process_dataframe(TEST_FILES[window])
        X_test = X_test.reindex(columns=X_train.columns, fill_value=0)

        preds_list = []
        for i, label in enumerate(LABELS):
            y_tr_col = y_train[:, i]
            
            if len(np.unique(y_tr_col)) < 2:
                preds_list.append(np.full(len(X_test), y_tr_col[0]))
                continue

            print(f"🚀 Training Specialist: {label}")
            model = train_model(X_train, y_tr_col)
            ts_proba = model.predict_proba(X_test)[:, 1]
            
            # Apply custom threshold for this specific label
            thresh = THRESHOLDS.get(label, THRESHOLDS["DEFAULT"])
            preds_list.append((ts_proba > thresh).astype(int))

        y_test_pred = np.column_stack(preds_list)

  

        print(f"\n{'P-Code':<8} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10} | {'Support':<8}")
        print("-" * 60)
        
        f1_list = []
        for i, label in enumerate(LABELS):
            y_true, y_pred = y_test[:, i], y_test_pred[:, i]
            p = precision_score(y_true, y_pred, zero_division=0)
            r = recall_score(y_true, y_pred, zero_division=0)
            f1 = f1_score(y_true, y_pred, zero_division=0)
            f1_list.append(f1)
            print(f"{label:<8} | {p:<10.4f} | {r:<10.4f} | {f1:<10.4f} | {int(np.sum(y_true)):<8}")

        subset_acc = np.mean(np.all(y_test == y_test_pred, axis=1))
        print("-" * 60)
        print(f"📊 Mean F1: {np.mean(f1_list):.4f}  |  🎯 Exact Match: {subset_acc:.4f}")

if __name__ == "__main__":
    main()
