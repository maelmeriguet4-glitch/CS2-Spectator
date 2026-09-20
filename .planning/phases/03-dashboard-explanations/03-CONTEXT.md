# Phase 3 Context: Dashboard & Explanations

## Goal
Créer l'UI interactive affichant les résultats et les preuves (Dashboard & Explanations).

## Requirements
- UI-01, UI-02
- Afficher la liste des joueurs avec leurs scores globaux.
- Vue détaillée au clic (statistiques, anomalies).
- Les raisons du verdict sont explicitées en texte clair (ex: "Bhop script détecté: 85% de sauts parfaits", "Wallhack: 3 pre-fires sans ligne de vue").

## Current Architecture
- `src/ui/app.py` contient l'interface principale.
- `src/ui/components/replays_panel.py` permet déjà de charger les démos et lancer l'analyse par lot.
- Il reste à implémenter un composant pour afficher le tableau des résultats (ex: `results_panel.py` ou `dashboard_panel.py`) ainsi qu'une vue modale ou un volet latéral pour les détails d'un joueur.
