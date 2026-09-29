<div align="center">
  <img src="./logo.png" alt="Logo CS2 Spectator" width="180">

  <h1>CS2 Spectator</h1>
  <p><strong>Analyse biomécanique et apprentissage automatique des replays Counter-Strike 2.</strong></p>
  <p>Des indicateurs à examiner, pas des verdicts automatiques.</p>

  <p>
    <a href="https://github.com/maelmeriguet4-glitch/CS2-Spectator/releases/latest"><img src="https://img.shields.io/badge/version-2.5.2-4263EB?style=for-the-badge" alt="Version 2.5.2"></a>
    <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.9+">
    <a href="LICENSE"><img src="https://img.shields.io/badge/licence-MIT-2DA44E?style=for-the-badge" alt="Licence MIT"></a>
    <img src="https://img.shields.io/badge/Windows-Linux-informational?style=for-the-badge" alt="Windows et Linux">
  </p>

  <p>
    <a href="https://github.com/maelmeriguet4-glitch/CS2-Spectator/issues/new?template=bug_report.yml">Signaler un problème</a>
    ·
    <a href="https://github.com/maelmeriguet4-glitch/CS2-Spectator/releases">Télécharger</a>
  </p>
</div>

---

## Sommaire

- [Présentation](#présentation)
- [Fonctionnalités](#fonctionnalités)
- [Qualité et préparation des releases](#qualité-et-préparation-des-releases)
- [Pipeline de données CS2CD](#pipeline-de-données-cs2cd)
- [Étiquetage et protocole d'évaluation](#étiquetage-et-protocole-dévaluation)
- [Modèles et interprétation des scores](#modèles-et-interprétation-des-scores)
- [Installation et utilisation](#installation-et-utilisation)
- [Indexation et entraînement CS2CD](#indexation-et-entraînement-cs2cd)
- [Tests](#tests)
- [Confidentialité et limites](#confidentialité-et-limites)
- [Signaler un problème et contribuer](#signaler-un-problème-et-contribuer)
- [Licence](#licence)

## Présentation

**CS2 Spectator** est une application de bureau destinée à l'examen après-match des démos `.dem` de Counter-Strike 2. Elle calcule des signaux biomécaniques et statistiques afin d'aider les joueurs à examiner un replay et à décider, en connaissance du contexte, si un signalement humain est justifié.

L'analyse peut mettre en évidence des snaps et à-coups de visée, des enchaînements de bunnyhop, des rotations atypiques, des réactions inhabituelles ou un alignement prolongé avec des adversaires non visibles. Ces observations sont des pistes d'investigation : elles ne prouvent pas qu'un joueur triche.

## Fonctionnalités

- **Analyse de replays** : traitement de fichiers `.dem`, rapports de signaux par joueur et indicateurs biomécaniques.
- **Interface graphique** : tableau de bord sombre, cartes de joueurs, progression et filtres d'équipe.
- **Gestion des démos** : recherche locale, sélection manuelle, surveillance des nouveaux replays et analyse par lots.
- **Import Faceit** : consultation de matchs et téléchargement sécurisé des démos depuis l'API Faceit ; seuls les schémas HTTP(S) sont autorisés.
- **Aide au signalement** : rapports textuels structurés pour accompagner un examen humain.
- **Recherche reproductible** : outils d'indexation, d'extraction de caractéristiques et d'entraînement avec CS2CD, y compris des sources Parquet et CSV compressées.
- **Exécution plus robuste** : détection des lecteurs disponibles, limitation des notifications répétées de démos, gestion du cycle de vie des analyses par lots et écritures atomiques du cache.
- **Intégrité des analyses** : les états `ERROR` et `INSUFFICIENT_DATA` sont préservés ; une analyse incomplète reste signalée même si d'autres joueurs ont des signaux, et le moteur n'invente pas de violations quand les données ne permettent pas de conclure.
- **Analyse d'occlusion prudente** : le suivi de cibles non visibles s'appuie sur un proxy géométrique, pas sur un ray-cast du moteur Source 2 ; il ne constitue pas une preuve de wallhack.

## Qualité et préparation des releases

La version applicative reste **2.5.2**. Les changements qui ont suivi cette release sont correctifs : nettoyage Ruff, correction d'une assertion de télémétrie et ajout de tests de régression P0. Ils ne constituent pas, à eux seuls, une nouvelle version fonctionnelle.

Le contrôle `scripts/verify_release_ready.py` vérifie notamment la syntaxe, Ruff, les suites unitaires et E2E, les bundles ML, leur schéma, la CLI et le prérequis de build. La suite P0 regroupe des scénarios de robustesse et de validation des bundles ; elle ne constitue ni une certification ni une preuve que tous les cas réels sont couverts. La mention « release ready » décrit le résultat de ces contrôles automatisés, pas un audit indépendant ni une garantie d'absence d'anomalies. Les contrôles qui nécessitent une démo ou un build restent conditionnels. Le manifeste CS2CD local est facultatif : il n'est pas distribué avec le dépôt et son absence est signalée comme ignorée par le gate.

Le workflow de release actuel construit sous Windows un exécutable PyInstaller **monofichier** `CS2_AntiCheat.exe` et ne publie que cet artefact. Le build embarque les bundles de modèles et le code applicatif ; il n'ajoute pas les rapports d'audit, journaux d'entraînement, scripts temporaires, manifestes locaux ni données brutes CS2CD. Les archives de la release v2.5.2 ont été produites par le workflow précédent en mode `onedir` : pour ces archives, extrayez et conservez le dossier complet, sans déplacer l'exécutable seul. La disposition des assets dépend donc de la release téléchargée.

## Pipeline de données CS2CD

Le pipeline prend en charge le jeu de données de recherche réel **CS2CD** : **795 matchs, environ 52,6 Go de données brutes**. Ces fichiers restent dans le répertoire local du dataset. L'indexeur écrit un manifeste avec leurs chemins et **ne copie ni ne duplique les fichiers Parquet et JSON**.

`CS2CDAdapter` adapte les enregistrements CS2CD à l'interface des analyseurs et prend en charge les sources Parquet et CSV compressées. Pour les ticks Parquet, il inspecte le schéma et ne lit que les colonnes nécessaires au moyen de PyArrow / `pandas.read_parquet(columns=...)`. Cette projection évite de charger inutilement toutes les colonnes des fichiers et réduit fortement la pression mémoire ; la mémoire disponible dépend néanmoins de la taille des fichiers et de la machine.

Le dépôt fournit [`data/anti_cheat_dataset.example.csv`](data/anti_cheat_dataset.example.csv), un exemple public et anonymisé de manifeste. Il illustre les colonnes et chemins relatifs sans inclure les données brutes CS2CD.

## Étiquetage et protocole d'évaluation

Les catégories d'un match ne permettent pas d'attribuer automatiquement une vérité terrain à chaque joueur. La politique du pipeline est donc conservatrice :

| Étiquette joueur | Attribution | Entraînement supervisé |
|---|---|---|
| `cheater` | Joueur explicitement annoté dans la liste des tricheurs d'un match `with_cheater_present` | Inclus, classe positive |
| `unknown` | Joueur non annoté dans un match où un tricheur est présent | **Exclu** de l'entraînement binaire |
| `probable_non_cheater` | Joueur d'un match `no_cheater_present` | Inclus comme classe négative, avec confiance moyenne (97,2 % selon la documentation CS2CD) |

En particulier, **un joueur non annoté dans un match avec tricheur n'est pas réputé légitime**. Les annotations indirectes de CS2CD peuvent être erronées — le projet documente un taux d'erreur de **44,4 % lié au Trust Factor** pour cette population. Le pipeline conserve donc ces observations avec l'étiquette `unknown` au lieu de les convertir en exemples négatifs.

L'indexeur répartit les matchs entre **Train (70 %), Validation (15 %) et Test (15 %)**. Le vérificateur de fuite forme des clés `match_id:player_id` puis contrôle que leurs ensembles sont disjoints entre les trois partitions. Le seuil du classifieur est sélectionné sur la validation ; le jeu de test reste réservé à l'évaluation finale. Avec l'anonymisation CS2CD, `player_id` désigne l'identifiant disponible dans le match ; cette vérification ne prétend pas relier une même personne anonymisée entre plusieurs matchs.

## Modèles et interprétation des scores

Le dépôt distingue deux modèles. **L'application utilise désormais le bundle CS2CD par défaut** ; le modèle synthétique peut être sélectionné explicitement pour comparaison ou compatibilité.

- **`cerveau_vac_custom.pkl`** : modèle physique synthétique de référence, entraîné sur des profils générés selon des plages biomécaniques définies par le projet. Il sert de baseline et n'est pas un modèle entraîné sur les matchs CS2CD.
- **`cerveau_vac_cs2cd.pkl`** : modèle entraîné sur les données CS2CD étiquetées. Son bundle auto-descriptif contient le classifieur et le scaler, le nom/révision du dataset, la version et l'empreinte du schéma de caractéristiques, les métadonnées d'entraînement, les métriques et les seuils calibrés.

Les bundles sont validés avant utilisation (structure, caractéristiques et seuils) ; un bundle invalide n'est pas remplacé silencieusement par un autre modèle. La sélection du modèle est disponible via `--model-type cs2cd|synthetic|custom` et le chemin d'un modèle personnalisé via `--model`.

Le bundle CS2CD transporte les seuils `threshold_high` et `threshold_suspect`, calculés à partir de la validation et appliqués à l'exécution. En l'absence de ces métadonnées facultatives, les seuils de configuration s'appliquent.

Le champ `suspicion_score` et la propriété `suspicion_scores` expriment des **scores combinés d'anomalie comportementale**, pas des probabilités calibrées. L'ancien nom de propriété `probabilities` est conservé comme alias de compatibilité, mais ses valeurs ne sont pas des probabilités. Un score, une étiquette `SUSPECT` ou une **suspicion élevée** doit toujours être confronté aux séquences du replay et à d'autres éléments.

La terminologie des résultats vise la prudence : **anomalie biomécanique**, **suspicion élevée** et **INFO-ESP** décrivent les signaux détectés, sans attribuer à eux seuls une intention ou une culpabilité. Un alignement sur une cible non visible n'est pas, à lui seul, la preuve d'un wallhack.

## Installation et utilisation

### Pour les joueurs

1. Ouvrez la page des [dernières Releases](https://github.com/maelmeriguet4-glitch/CS2-Spectator/releases).
2. Choisissez un asset correspondant à votre système et à la release. Les archives `onedir` doivent être extraites intégralement et conservées dans leur dossier ; ne déplacez pas leur exécutable seul. Un exécutable monofichier peut être lancé directement.
3. Sélectionnez une démo `.dem` locale ou importez un replay Faceit.

### Pour les développeurs

**Prérequis :** Python 3.9 ou supérieur. Sous Linux, installez également Tkinter pour votre version de Python si nécessaire.

```bash
git clone https://github.com/maelmeriguet4-glitch/CS2-Spectator.git
cd CS2-Spectator
python -m pip install -r requirements.txt
python main.py
```

Pour analyser une démo en mode console ou choisir explicitement un modèle :

```bash
python main.py --demo "CHEMIN\VERS\match.dem" --model-type cs2cd
python main.py --version
```

## Indexation et entraînement CS2CD

Le dataset brut n'est pas distribué avec le dépôt. Obtenez-le séparément et placez les fichiers dans les dossiers `with_cheater_present` et `no_cheater_present`, avec les paires de fichiers Parquet et JSON attendues.

Depuis la racine du dépôt, sur Windows :

```powershell
python scripts/index_cs2cd.py --dataset-root "CHEMIN\VERS\CS2CD" --sample-size 50
python scripts/train_cs2cd.py --manifest data/anti_cheat_dataset.csv
```

L'indexation produit le manifeste local `data/anti_cheat_dataset.csv` et l'exemple public `data/anti_cheat_dataset.example.csv`. L'entraînement extrait les caractéristiques, exclut les étiquettes `unknown`, vérifie l'étanchéité des splits, ajuste le seuil sur Validation, puis évalue le modèle sur Test.

N'ajoutez pas au dépôt le dataset brut, les manifestes contenant vos chemins locaux, le cache de caractéristiques ou d'autres données privées.

## Tests

Le contrôle de préparation de release vérifie la syntaxe, Ruff, les suites unitaires et E2E, les bundles ML, le schéma de caractéristiques, le packaging et la CLI. Exécutez-le depuis la racine du dépôt :

```bash
python scripts/verify_release_ready.py
```

Les tests peuvent aussi être lancés séparément :

```bash
python -m pytest tests/unit/ -q
python -m pytest tests/e2e/ -q
```

Certaines vérifications réelles sont conditionnelles à des ressources locales non distribuées — démo de test ou build dans `dist/`. Le manifeste CS2CD local est facultatif et n'est pas requis par défaut. Pour ajouter l'analyse d'une démo et un build PyInstaller au gate, utilisez `python scripts/verify_release_ready.py --with-demo --with-build`. Un test ignoré ou une ressource absente ne constitue pas une validation de release.

## Confidentialité et limites

- L'application analyse les fichiers de replay ; elle ne lit pas la mémoire du jeu et ne modifie pas Counter-Strike 2.
- CS2 Spectator n'est pas un cheat et ne remplace ni VAC, ni la modération de Valve ou de Faceit.
- Une analyse automatique peut générer de faux positifs ou manquer des comportements. Ne signalez pas un joueur sur la base du seul score ou d'une seule détection.
- L'import Faceit communique avec l'API Faceit et requiert une clé API valide. Ne publiez jamais cette clé.

## Signaler un problème et contribuer

Un bug ou une difficulté d'installation ? [Ouvrez un signalement](https://github.com/maelmeriguet4-glitch/CS2-Spectator/issues/new?template=bug_report.yml). Le formulaire demande les étapes de reproduction, la version et le système utilisé. N'y joignez ni clé API, ni données personnelles, ni démo privée.

Les contributions sont les bienvenues : ouvrez d'abord une issue pour discuter d'une évolution importante, puis proposez une pull request concise accompagnée des tests pertinents.

## Licence

CS2 Spectator est distribué sous licence [MIT](LICENSE).
