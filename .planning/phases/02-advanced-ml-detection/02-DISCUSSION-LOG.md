# Phase 2 Discussion Log

## Initialisation
Le contexte de la phase 2 a été généré.
Nous devons affiner l'implémentation de `CheatClassifier` (potentiellement avec scikit-learn si cela est toléré, ou des règles expertes lourdes si on évite des dépendances supplémentaires) et améliorer l'extraction de métriques.

## Questions de design :
1. Devons-nous utiliser une librairie comme `scikit-learn` pour le ML, ou conserver une approche heuristique / algorithmique légère "expert rules" ?
2. L'objectif est d'avoir "le meilleur anticheat". Une détection par forêt d'isolation (Isolation Forest) ou réseau de neurones serait l'idéal.
3. Pour la détection de wallhack, il faudrait calculer la distance angulaire entre le viseur et les ennemis au travers des murs (crosshair placement sur X-Ray).

## Action
Nous allons planifier la mise à jour de `src/ml/classifier.py` et `src/analyzers/aimbot.py` / `src/analyzers/wallhack.py` pour produire de vraies métriques biomécaniques et utiliser un score probabiliste agrégé.
