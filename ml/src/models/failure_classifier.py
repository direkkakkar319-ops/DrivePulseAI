# XGBoost/RandomForest — train/predict/save/load interface
import sys

sys.path.append(r"E:\DrivePulseAI\ml\src\training")

from train_failure import FailureClassifier   # adjust import path as needed

clf = FailureClassifier.load(r"E:\DrivePulseAI\ml\src\models\logreg_model.joblib")
