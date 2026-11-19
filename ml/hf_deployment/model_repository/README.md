# Nissan Leaf anomaly artifact

`nissan_leaf_anomaly.joblib` contains a fitted scikit-learn Isolation Forest,
the exact feature order (`HV_Bat_Voltage`, `Pack_1_C_Temp`, `SOC`,
`HV_Bat_Current_2`, `Pack_2_C_Temp`, `Pack_4_C_Temp`), and a
training-only 0.5th-percentile novelty threshold. It was trained on
publisher-preprocessed 2018 Nissan Leaf telemetry using a chronological
70/15/15 split.

The source has no verified fault labels. The artifact provides an exploratory
novelty score; it does not produce a fault probability or diagnosis. The
dataset represents one vehicle, so generalization to other vehicles is not
established.

This is a trusted joblib/pickle artifact. Load it only with the matching
scikit-learn runtime in the service; never load artifacts from untrusted
sources. The source dataset is not copied into the deployment image.
