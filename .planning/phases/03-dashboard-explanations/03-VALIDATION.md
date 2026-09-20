# Phase 3 Validation Strategy

## Dimensions
1. **Rendering:** Le système d'accordéon (déroulement dynamique de hauteur) fonctionne-t-il bien dans `customtkinter` (souvent capricieux sur la gestion dynamique de la taille) ?
2. **Data Binding:** Les "pills" et scores (ML) sont-ils bien extraits de `PlayerTelemetry` / `MatchAnalysisResult` vers l'UI ?
3. **Ergonomie:** L'affichage des tricheurs ("CHEATER") est-il mis en valeur (couleurs d'alerte, rouge) comparé aux joueurs légitimes (vert) ?

## Automated Tests
- Mettre à jour `test_ui.py` ou ajouter `test_dashboard.py` pour valider l'instanciation de `DashboardPanel` avec des résultats simulés.

## Manual Tests
1. Lancer l'application (`python src/ui/app.py`).
2. Cliquer sur "Analyser tout" sur un mock (ou modifier temporairement le backend pour renvoyer des résultats rapides).
3. Observer l'apparition du Dashboard.
4. Cliquer sur la ligne d'un "CHEATER" et vérifier que le panneau accordéon dévoile les `violation_flags` sans glitch d'affichage.
