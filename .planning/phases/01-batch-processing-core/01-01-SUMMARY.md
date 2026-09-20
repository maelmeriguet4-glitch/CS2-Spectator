# Phase 1 Summary: Batch Processing Core

## Travail Accomplis
- Création du module `src/core/batch_processor.py` contenant la classe `BatchProcessor` qui gère l'exécution asynchrone d'une liste de fichiers `.dem`.
- Mise en place d'une architecture multi-processus séquentielle optimisée pour ne pas saturer la RAM (analyse gourmande de fichiers CS2), en utilisant `multiprocessing.Process` et un thread gestionnaire (`_run_batch_manager`).
- Ajout du bouton "Analyser tout (Batch)" dans `src/ui/components/replays_panel.py`.
- Intégration du `BatchProcessor` dans `src/ui/app.py`.
- Mise à jour de la méthode `_check_queue` dans `app.py` pour écouter les messages envoyés par le processeur par lots et mettre à jour l'interface graphique via la boucle principale sans la bloquer (`CTkProgressBar`, statuts textuels).

## Remarques
- Les fichiers sont traités un par un par un worker d'arrière-plan, afin d'éviter une surcharge de ressources système tout en permettant à l'utilisateur de continuer à utiliser l'application fluidement.
- L'interface affiche en temps réel l'avancée de l'analyse et signale les éventuelles erreurs d'analyse sans planter l'ensemble du lot.
