# Phase 2 Validation Strategy

## Dimensions
1. **Unittest:** Les algorithmes ML (Isolation Forest, règles) prédisent-ils de manière consistante des probabilités sans crasher ?
2. **Features Extraction:** `aimbot.py` et `wallhack.py` renvoient-ils des métriques au bon format pour le pipeline ?
3. **Integration:** Le pipeline complet (`engine.py`) peut-il consommer les prédictions scikit-learn ?

## Automated Tests
- `pytest tests/unit/test_ml.py` : Vérifier que le classifieur attribue un score élevé (CHEATER) aux métriques aberrantes, et bas (CLEAN) aux données normales.

## Manual Tests
1. Mettre une démo au sein de l'anticheat.
2. Analyser via le batch processor ou manuellement.
3. Vérifier la sortie globale (verdict) pour s'assurer que l'intégration scikit-learn fonctionne sans `ModuleNotFoundError` ni crash d'incompatibilité numpy/pandas.
