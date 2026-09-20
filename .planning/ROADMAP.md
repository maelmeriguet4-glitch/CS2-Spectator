# Roadmap

## Proposed Roadmap

**4 phases** | **6 requirements mapped** | All v1 requirements covered ✓

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 1 | Batch Processing Core | Permettre l'analyse en arrière-plan de plusieurs démos | PERF-01 | 2 |
| 2 | Advanced ML Detection | Intégrer les modèles de détection avancés (wallhack/aimbot) | ML-01, ML-02 | 3 |
| 3 | Dashboard & Explanations | Créer l'UI interactive affichant les résultats et les preuves | UI-01, UI-02 | 3 |
| 4 | Audit Reporting | Générer des rapports exportables pour le signalement | PERF-02 | 2 |

### Phase Details

**Phase 1: Batch Processing Core**
Goal: Permettre l'analyse en arrière-plan de plusieurs démos
**Mode:** mvp
Requirements: PERF-01
Success criteria:
1. L'utilisateur peut sélectionner un dossier contenant plusieurs fichiers `.dem`.
2. L'application parse les démos en arrière-plan (multiprocessing) sans bloquer l'interface.

**Phase 2: Advanced ML Detection**
Goal: Intégrer les modèles de détection avancés (wallhack/aimbot)
**Mode:** mvp
Requirements: ML-01, ML-02
Success criteria:
1. Les modèles ML prédisent la probabilité d'aimbot avec des métriques humanisées.
2. Les modèles ML détectent les anomalies de vision (wallhacks subtils).
3. Les verdicts sont correctement retournés par le moteur central.

**Phase 3: Dashboard & Explanations**
Goal: Créer l'UI interactive affichant les résultats et les preuves
**Mode:** mvp
Requirements: UI-01, UI-02
Success criteria:
1. L'interface affiche une liste des joueurs avec leurs scores de suspicion globaux.
2. Un clic sur un joueur ouvre une vue détaillée (statistiques, anomalies).
3. Les raisons du verdict sont explicitées en texte clair.

**Phase 4: Audit Reporting**
Goal: Générer des rapports exportables pour le signalement
**Mode:** mvp
Requirements: PERF-02
Success criteria:
1. L'utilisateur peut cliquer sur "Exporter Rapport" pour un joueur suspect.
2. Un fichier PDF ou TXT est généré avec les preuves et les timestamps des actions suspectes.
