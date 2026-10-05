# Failure-classification training output (Scania APS)

Logreg (standardized) / RF / XGB (raw levels) on 170 signals plus engineered n_missing and per-group sum/mean/max, median-imputed with train-fit stats. Thresholds tuned on a stratified 15% validation slice for recall >= 0.90; official test evaluated once. pos = APS failure, neg = other-component failure.

[data] train=(60000, 192) pos=1000 | test=(16000, 192) pos=375

==================================================
Running logreg_model...
==================================================
[logreg] threshold=0.473
  accuracy: 0.9741
  precision: 0.4733
  recall: 0.9200
  f2_score: 0.7739
  tp: 345
  fp: 384
  fn: 30
  tn: 15241
[OK] logreg_model finished in 33.11s
    accuracy: 0.9741
    precision: 0.4733
    recall: 0.9200
    f2_score: 0.7739
    tp: 345
    fp: 384
    fn: 30
    tn: 15241

==================================================
Running rf_model...
==================================================
[rf] threshold=0.170
  accuracy: 0.9893
  precision: 0.7189
  recall: 0.8933
  f2_score: 0.8520
  tp: 335
  fp: 131
  fn: 40
  tn: 15494
[OK] rf_model finished in 114.71s
    accuracy: 0.9893
    precision: 0.7189
    recall: 0.8933
    f2_score: 0.8520
    tp: 335
    fp: 131
    fn: 40
    tn: 15494

==================================================
Running xgb_model...
==================================================
[xgb] threshold=0.048
  accuracy: 0.9826
  precision: 0.5805
  recall: 0.9227
  f2_score: 0.8254
  tp: 346
  fp: 250
  fn: 29
  tn: 15375
[OK] xgb_model finished in 1059.36s
    accuracy: 0.9826
    precision: 0.5805
    recall: 0.9227
    f2_score: 0.8254
    tp: 346
    fp: 250
    fn: 29
    tn: 15375
