# Phase 1 Context

## Domain
This phase delivers: **Batch Processing Core** — Permettre l'analyse de plusieurs démos en arrière-plan sans bloquer l'UI.

## Decisions

### Feedback UI & Progression
- **Type de retour utilisateur** : Barre de progression détaillée avec décompte (ex: "5/20 démos analysées") et estimation du temps restant.
- **Gestion des erreurs (fichiers corrompus)** : Afficher l'erreur immédiatement dans l'interface utilisateur, mais continuer automatiquement le traitement des fichiers restants dans le lot.

## Canonical Refs
- Pas de document de référence externe pour le moment.

## Code Context
- L'application utilise `customtkinter` (UI) et `multiprocessing` (Arrière-plan) d'après le `STACK.md`. L'intégration devra lier les processus `multiprocessing` à la barre de progression UI.
