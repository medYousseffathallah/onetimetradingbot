---
name: bvmt-model-validation
description: "Design or review leakage-safe stock-ranking features, labels, walk-forward folds, model tuning, and promotion tests for the BVMT project. Use when adding LightGBM or comparing any predictive strategy. Inputs are point-in-time data and registered hypotheses; outputs are reproducible out-of-sample comparisons with disclosed trial counts."
---

# BVMT Model Validation

Work from the BVMT repository root. If the repository is unavailable, request its
path or files; do not invent project state or claim commands were executed.


1. Read the experiment template and verify the baseline and execution engine exist first.
2. Define decision-time features and session-based labels including executable timing.
3. Split chronologically across all instruments; purge overlapping label windows.
4. Fit normalization, selection, imputation and tuning only inside the training process.
5. Reserve a final holdout and predeclare metric, tuning budget and promotion rule.
6. Test future-data mutation invariance and instrument/universe leakage.
7. Register every result, including failures; compare after identical costs and constraints.
Reject or defer the model when evidence is insufficient. Do not optimize to a target return.
