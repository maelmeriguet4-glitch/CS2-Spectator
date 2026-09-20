# Phase 2 Summary: Advanced ML Detection

## Work Completed
- Validation de l'utilisation de `scikit-learn` pour le modèle ML.
- La classe `CheatClassifier` (`src/ml/classifier.py`) implémente un `RandomForestClassifier` combiné à une `IsolationForest` via un dataset synthétique calibré pour évaluer précisément des features biomécaniques poussées (aim_snap_max, wh_ratio_lock_strict, etc.).
- Les tests unitaires dans `test_ml.py` confirment que le ML attribue des scores probants, distinguant 0% pour un joueur légitime et 100% pour des comportements de triche.

## Next Steps
- L'infrastructure ML est opérationnelle, les scores sont remontés vers le dashboard en "verdicts humanisés" et le pipeline (`engine.py`) ingère tout correctement.
- Phase 3 (Dashboard & Explanations) sera la prochaine étape.
