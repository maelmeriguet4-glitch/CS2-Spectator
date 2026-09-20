# Requirements

## v1 Requirements

### Machine Learning
- [ ] **ML-01**: Le système doit détecter les aimbots humanisés à partir des données de rediffusion.
- [ ] **ML-02**: Le système doit identifier l'utilisation de wallhacks subtils.

### Interface Utilisateur (UI/UX)
- [ ] **UI-01**: L'interface doit proposer un tableau de bord interactif pour consulter les résultats.
- [ ] **UI-02**: Le système doit fournir une explication claire et détaillée des raisons d'un verdict de triche.

### Infrastructure & Performance
- [ ] **PERF-01**: Le système doit pouvoir analyser des lots de plusieurs fichiers `.dem` en arrière-plan sans bloquer l'interface.
- [ ] **PERF-02**: Le système doit générer et exporter des rapports d'audit concrets (preuves) pour le signalement manuel.

## v2 Requirements
- [ ] Analyse automatique de compétitions complètes (mode ligue).

## Out of Scope
- [Analyse de la RAM / Injection] — Raison : Strictement interdit pour éviter les bans VAC.

## Traceability

- **ML-01** → Phase 2
- **ML-02** → Phase 2
- **UI-01** → Phase 3
- **UI-02** → Phase 3
- **PERF-01** → Phase 1
- **PERF-02** → Phase 4
