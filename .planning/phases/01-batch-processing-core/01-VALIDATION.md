# Phase 1 Validation Strategy

## Dimensions
1. **Unittest:** La logique du pool de processus peut-elle être testée isolément de l'UI ?
2. **Integration:** Est-ce que la barre de progression se remplit bien lors de l'exécution ?
3. **Erreurs:** Le traitement survit-il si un `.dem` est corrompu ?

## Automated Tests
- Test unitaire pour `BatchProcessor` avec des faux fichiers ou fonctions de simulation pour garantir que la Queue renvoie bien les messages de progression.

## Manual Tests
1. Sélectionner un dossier contenant 1 fichier valide, 1 fichier corrompu.
2. Lancer l'analyse.
3. Vérifier que l'UI ne gèle pas.
4. Vérifier que la barre indique `2/2` à la fin, avec une erreur affichée pour le corrompu.
