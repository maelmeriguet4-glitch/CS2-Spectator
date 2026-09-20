# Phase 4 Validation Strategy

## Dimensions
1. **File System:** Le fichier texte se sauvegarde-t-il bien dans le dossier `reports` ? Les caractères spéciaux dans le nom du joueur empêchent-ils l'écriture (besoin d'assainir le nom du fichier) ?
2. **Content Formatting:** Le rapport est-il lisible par un humain (format Markdown ou TXT clair) ?

## Automated Tests
- Test unitaire sur `export_player_report()` pour vérifier que la chaîne retournée ou le fichier écrit est valide.

## Manual Tests
- Clic sur "Exporter" dans l'UI.
- Ouvrir le fichier TXT généré et s'assurer que toutes les preuves sont là.
