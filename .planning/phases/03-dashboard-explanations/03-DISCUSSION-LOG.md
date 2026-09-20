# Phase 3 Discussion Log

## Initialisation
Le contexte de la phase a été généré. L'objectif est de mettre en place l'interface `customtkinter` permettant de lire la sortie du moteur (`MatchAnalysisResult`) et de rendre les preuves intelligibles pour l'humain.

## Questions Ouvertes
1. Structure UI : Le dashboard doit-il être un nouvel onglet principal dans `app.py` ou un panneau qui remplace la liste des replays après analyse ?
2. Vue détaillée : Lorsqu'on clique sur un joueur, préfère-t-on une fenêtre modale pop-up (`CTkToplevel`) ou un panneau latéral coulissant (ou s'étendant) dans la même fenêtre ?
3. Export : L'export des preuves (Phase 4) sera intégré plus tard, mais il faut prévoir la place pour le bouton "Exporter".
