# Phase 1 Research: Batch Processing Core

## Goal
Permettre l'analyse en arrière-plan de plusieurs démos.

## Codebase Discoveries
- Le projet utilise `customtkinter` pour son UI.
- L'analyse de fichier `.dem` se fait probablement via une boucle qui utilise `demoparser2` (la librairie choisie). L'appel à `demoparser2` bloque le thread principal si non asynchrone ou sans multiprocessing.
- Python `concurrent.futures.ProcessPoolExecutor` ou `multiprocessing.Pool` est requis pour répartir le travail de parsing intensif sans freeze l'UI, car le Global Interpreter Lock (GIL) de Python empêche les threads simples de bien gérer les charges CPU.

## Constraints
- **customtkinter / Tkinter** ne sont pas thread-safe. Toutes les mises à jour de l'UI (ex: barre de progression) doivent être faites depuis le thread principal (en utilisant la méthode `after()` de Tkinter).

## Recommended Approach
1. Créer une classe `BatchProcessor` ou utiliser un orchestrateur.
2. Utiliser `concurrent.futures.ProcessPoolExecutor` pour traiter chaque fichier `.dem` dans un processus séparé.
3. Utiliser un mécanisme de file (Queue) ou les Callbacks asynchrones pour envoyer les événements de progression (ex: "Fichier X terminé, succès") au thread principal.
4. Mettre à jour la barre de progression UI via `app.after()`.

## Validation Architecture
Voir `01-VALIDATION.md` pour l'architecture de test et validation.
