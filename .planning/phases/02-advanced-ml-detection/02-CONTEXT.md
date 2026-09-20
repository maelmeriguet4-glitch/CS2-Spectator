# Phase 2 Context: Advanced ML Detection

## Goal
Intégrer les modèles de détection avancés (wallhack/aimbot) et améliorer `CheatClassifier`.

## Requirements
- ML-01: Les modèles ML prédisent la probabilité d'aimbot avec des métriques humanisées.
- ML-02: Les modèles ML détectent les anomalies de vision (wallhacks subtils).

## Current Architecture
- `src.analyzers.aimbot`, `src.analyzers.wallhack` extract features from `demo_data`.
- `src.ml.classifier.CheatClassifier` consumes these features to predict verdicts ("CLEAN", "SUSPECT", "CHEATER") and flags.
- `PlayerTelemetry` stores `aim_metrics`, `wh_metrics`, `suspicion_score`, and `verdict`.

## Technical Focus
1. Update `CheatClassifier` to use an advanced algorithm (e.g. Isolation Forest, Random Forest) for better anomaly detection.
2. Refine `analyze_aimbot` to extract human-like metrics (time-to-target, overflick rate).
3. Refine `analyze_wallhack` to detect subtle vision anomalies (crosshair placement around corners without line of sight).
4. Ensure inference performance is fast enough for batch processing.
