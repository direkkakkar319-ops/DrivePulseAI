# Exploratory analysis of the AI4I dataset — distributions, correlations, missing data

import sys
from pathlib import Path
sys.path.append(r"E:\DrivePulseAI\ml\src\data")
sys.path.append(r"DrivePulseAI\data\failure_classification\raw")
from loaders import load_ai4i, load_cmapss, load_simulated
import pandas
df = pd.read_csv()