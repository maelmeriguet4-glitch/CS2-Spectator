# CS2 Anti-Cheat Dashboard

## What This Is

Un anti-cheat local et indirect pour Counter-Strike 2 qui analyse les fichiers de rediffusion (`.dem`) post-match. Il utilise le Machine Learning pour détecter la triche sans jamais interagir avec la mémoire du jeu en temps réel, garantissant qu'il n'y a aucun risque de ban VAC pour l'utilisateur. Il ambitionne d'être le meilleur de sa catégorie au monde.

## Core Value

Détecter la triche (aimbots humanisés, wallhacks subtils) avec la plus haute précision possible, exclusivement à partir de l'analyse des replays, de façon sécurisée et incontestable.

## Requirements

### Validated

- ✓ [Parsing local] — Extraction de données des fichiers `.dem` via `demoparser2`.
- ✓ [Pipeline ML] — Chargement de modèles et inférence via `scikit-learn` (modèles `.pkl`).
- ✓ [Interface multi-modale] — Disponibilité d'une interface graphique (`customtkinter`) et d'un mode console CLI.

### Active

- [ ] [Détection IA de pointe] — Améliorer les modèles ML pour détecter les comportements subtils (wallhacks, aimbots humanisés).
- [ ] [UI/UX enrichie] — Créer un dashboard interactif qui explique clairement les verdicts avec des statistiques détaillées.
- [ ] [Traitement par lots ultra-rapide] — Optimiser les performances pour analyser de nombreuses démos en arrière-plan sans bloquer l'utilisateur.
- [ ] [Génération de preuves] — Produire des rapports d'audit concrets et exportables prouvant la triche pour des signalements manuels.

### Out of Scope

- [Analyse mémoire en temps réel] — Raison : Entraîne un ban par Valve (VAC). L'outil doit rester 100% indirect.
- [Intervention réseau pendant le jeu] — Raison : Même risque de détection que la lecture mémoire.

## Context

- **Technique** : L'application est écrite en Python 3.9+. Elle utilise `demoparser2` pour la performance, `scikit-learn` pour le Machine Learning, et `customtkinter` pour l'interface.
- **État actuel (Brownfield)** : La base de code existante contient déjà le pipeline de base, mais présente de la dette technique (nombreuses erreurs `ruff`/`mypy`, gros fichiers `.pkl` dans le dépôt source).
- **Vision utilisateur** : Le projet doit devenir la référence mondiale de l'analyse anti-triche post-partie.

## Constraints

- **Sécurité (Anti-Ban)** : L'application ne doit jamais interagir avec le processus `cs2.exe` ou injecter de code.
- **Performance** : Le traitement de fichiers `.dem` (qui sont lourds) doit être hautement optimisé (ex: `multiprocessing`) pour permettre l'analyse en masse.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Analyse 100% Post-Match (fichiers `.dem`) | Seule méthode 100% sûre pour ne pas risquer de bans par Valve (VAC). | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-09-20 after initialization*
