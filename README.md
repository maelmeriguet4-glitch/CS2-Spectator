<div align="center">
  <img src="./logo.png" alt="CS2 Spectator Logo" width="180">

  <h1>CS2 Spectator</h1>

  <p><strong>L'outil ultime d'analyse biomécanique et d'intelligence artificielle pour débusquer les tricheurs sur Counter-Strike 2.</strong></p>

  <p>Analysez les replays, repérez des comportements inhabituels et rassemblez des éléments concrets avant tout signalement.</p>

  <p>
    <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white" alt="Python 3.9+">
    <img src="https://img.shields.io/badge/Licence-MIT-2ea44f" alt="Licence MIT">
    <img src="https://img.shields.io/badge/Version-2.4.0-blue" alt="Version 2.4.0">
    <img src="https://img.shields.io/badge/Plateformes-Windows%20%7C%20Linux-informational" alt="Windows et Linux">
  </p>

  <p><code>#games</code> <code>#anticheat</code> <code>#counter-strike-2</code> <code>#replay-analysis</code></p>
</div>

---

## 📚 Table des matières

- [🎯 À propos](#-à-propos)
- [✨ Fonctionnalités](#-fonctionnalités)
- [🆕 Nouveautés de la version 2.4.0](#-nouveautés-de-la-version-240)
- [🚀 Installation et utilisation](#-installation-et-utilisation)
  - [Pour les joueurs](#-pour-les-joueurs--installation-simple)
  - [Pour les développeurs](#-pour-les-développeurs--depuis-les-sources)
- [🧪 Outils de développement CS2CD](#-outils-de-développement-cs2cd)
- [🧭 Parcours d'analyse](#-parcours-danalyse)
- [🐛 Signaler un problème](#-signaler-un-problème)
- [🛡️ Confidentialité et limites](#️-confidentialité-et-limites)
- [🗺️ Feuille de route](#️-feuille-de-route)
- [🤝 Contribuer](#-contribuer)
- [📄 Licence](#-licence)

## 🎯 À propos

**CS2 Spectator** s'adresse aux joueurs qui, après une partie de Counter-Strike 2, souhaitent examiner le replay d'un joueur suspect avant d'effectuer un signalement. L'application analyse les données d'une démo `.dem` et présente des indicateurs destinés à faciliter une vérification humaine.

L'analyse biomécanique et les modèles de machine learning signalent des motifs potentiellement anormaux. Ils ne déterminent pas à eux seuls qu'un joueur triche : les résultats doivent être interprétés dans le contexte du match et vérifiés par une personne.

## ✨ Fonctionnalités

- **Analyse biomécanique et machine learning** — recherche de snaps et à-coups de visée, réactions anormalement rapides, mouvements de type spinbot et enchaînements de bunnyhop inhabituels. Les indicateurs d'alignement sur des adversaires non visibles sont des signaux d'information, pas la preuve d'un wallhack.
- **Interface graphique sombre** — tableau de bord construit avec CustomTkinter, cartes de joueurs, progression de l'analyse, sélection des démos et filtres d'équipe.
- **Gestion des replays** — détection des démos CS2 locales, sélection manuelle de fichiers `.dem`, surveillance du dossier de replays et analyse par lots.
- **Import Faceit** — consultation de matchs et téléchargement/extraction de démos depuis Faceit via l'API, avec téléchargement par blocs, délais réseau et limite d'extraction de 500 Mo. Une clé API Faceit est nécessaire.
- **Aide au signalement** — rapports textuels structurés pour Steam et Faceit, avec métriques et événements de replay pertinents. **L'export PDF n'est pas encore disponible.**
- **Modèle CS2CD** — classification par modèle pré-entraîné distribué avec l'application, enrichie par l'intégration du dataset CS2CD.
- **Analyse plus légère** — réduction de la mémoire utilisée par les traitements de démos et réutilisation du modèle chargé pendant l'analyse.

> Les détections sont des indicateurs statistiques, pas des verdicts ni une preuve infaillible. Une anomalie peut avoir une explication légitime.

## 🆕 Nouveautés de la version 2.4.0

- Nouveau modèle pré-entraîné `cerveau_vac_cs2cd.pkl`, utilisé par défaut.
- Adaptateur CS2CD pour lire les données Parquet et les événements JSON, plus deux scripts facultatifs pour indexer un dataset local et entraîner un modèle.
- Mise à jour de plusieurs composants d'analyse, du cache, du traitement par lots et de l'import Faceit.
- Modèle et code applicatif inclus dans les paquets Windows et Linux de la Release.

Les données brutes CS2CD ne sont pas fournies dans le dépôt. Les outils d'indexation et d'entraînement sont destinés aux développeurs disposant légalement de ce dataset.

## 🚀 Installation et utilisation

### 🎮 Pour les joueurs — installation simple

1. Ouvrez la page des [dernières versions (Releases)](https://github.com/maelmeriguet4-glitch/CS2-Spectator/releases).
2. Téléchargez le paquet correspondant à votre système : l'exécutable `.exe` pour Windows ou l'archive `.zip`/`.tar` pour Linux, lorsqu'un paquet est publié.
3. Extrayez l'archive si nécessaire, puis lancez l'application.
4. Choisissez une démo locale, parcourez un fichier `.dem` ou importez un replay Faceit.

Chaque Release publiée inclut un exécutable Windows `.exe` et son archive `.zip`, ainsi qu'une archive Linux `.zip` et `.tar.gz`. Les paquets sont construits automatiquement depuis les sources à la publication d'une version. Si aucun paquet n'est encore proposé, utilisez l'installation depuis les sources ci-dessous.

### 🧑‍💻 Pour les développeurs — depuis les sources

**Prérequis :** Python 3.9 ou supérieur.

```bash
git clone https://github.com/maelmeriguet4-glitch/CS2-Spectator.git
cd CS2-Spectator
python -m pip install -r requirements.txt
python main.py
```

Sous Linux, vérifiez que Tkinter est installé pour votre version de Python si l'interface ne démarre pas.

### 🧪 Outils de développement CS2CD

Le modèle pré-entraîné est inclus dans l'application ; le dataset brut est requis uniquement pour réindexer les matchs ou entraîner un nouveau modèle. Les fichiers sources du dataset doivent être organisés en dossiers `with_cheater_present` et `no_cheater_present`, contenant des paires `.parquet` et `.json`.

```bash
python scripts/index_cs2cd.py --dataset-root chemin/vers/CS2CD
python scripts/train_cs2cd.py --manifest data/anti_cheat_dataset.csv
```

L'indexeur génère `data/anti_cheat_dataset.csv`. L'entraînement réutilise par défaut l'extraction de caractéristiques en cache, compare au modèle synthétique existant et écrit le nouveau modèle dans `cerveau_vac_cs2cd.pkl`. Les options `--output` de l'indexeur et `--features-cache`, `--model-output` ou `--baseline-model` de l'entraîneur permettent de personnaliser les chemins. Les chemins des fichiers restent locaux et ne doivent pas être publiés avec le manifeste.

## 🧭 Parcours d'analyse

1. **Sélectionnez** un replay depuis la liste détectée, avec le bouton de parcours de fichiers, ou via l'import Faceit.
2. **Lancez l'analyse** et laissez le traitement se terminer.
3. **Examinez les résultats** par joueur : score de suspicion, signaux détectés et métriques de replay.
4. **Vérifiez les séquences dans leur contexte**, puis, si cela vous semble justifié, préparez un signalement à partir des informations observées.

## 🐛 Signaler un problème

Vous avez rencontré un bug ou quelque chose ne fonctionne pas comme prévu ? [Ouvrez un signalement](https://github.com/maelmeriguet4-glitch/CS2-Spectator/issues/new?template=bug_report.yml) : le formulaire vous guidera pour décrire le problème et les étapes permettant de le reproduire. Merci de ne pas joindre de clé API, de données personnelles ni de démo contenant des informations privées.

## 🛡️ Confidentialité et limites

- CS2 Spectator lit et analyse des fichiers de replay `.dem` ; il **n'interagit jamais avec la mémoire du jeu**.
- Ce logiciel n'est pas un cheat : il ne modifie pas le jeu et ne fournit aucun avantage en partie.
- Il ne remplace pas VAC, les systèmes de modération de Valve ou ceux de Faceit. Il s'agit d'un outil d'aide à l'examen personnel des replays, et non d'un système anti-cheat officiel.
- L'import Faceit communique avec l'API Faceit lorsque cette fonctionnalité est utilisée. Il nécessite une clé API valide.
- Les résultats ne garantissent ni la présence ni l'absence de triche. Ne signalez pas un joueur sur la seule base d'un score automatisé.

## 🗺️ Feuille de route

- Associer l'outil à des bases de données de sites communautaires anti-cheat à l'échelle internationale.
- Étudier l'ajout de l'export des rapports au format PDF.

Les contributions et retours d'expérience sont les bienvenus pour faire évoluer ces pistes.

## 🤝 Contribuer

Merci de votre intérêt pour CS2 Spectator ! Les contributions sont les bienvenues, qu'il s'agisse de rapports de bogues, de documentation, de tests ou d'améliorations du code.

1. Ouvrez une issue pour décrire un problème ou proposer une évolution.
2. Pour une contribution de code, créez un fork et une branche dédiée.
3. Ajoutez ou mettez à jour les tests concernés, puis ouvrez une pull request avec une description claire du changement.

Restez bienveillant dans les échanges, fournissez des étapes de reproduction pour les bogues et évitez de publier des données personnelles ou des clés API dans les issues.

## 📄 Licence

Ce projet est distribué sous licence [MIT](LICENSE).

**Sujets GitHub :** `games` · `anticheat` · `counter-strike-2` · `replay-analysis` · `machine-learning` · `python`
