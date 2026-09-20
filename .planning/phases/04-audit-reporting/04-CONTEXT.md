# Phase 4 Context: Audit Reporting

## Goal
Générer des rapports exportables pour le signalement des tricheurs (Audit Reporting).

## Requirements
- Exporter les preuves d'un joueur suspect.
- Générer un fichier TXT (ou PDF/Markdown) formaté avec toutes les métriques et flags de triche pour qu'un modérateur humain puisse prendre une décision de ban.

## Current Architecture
- Le composant `DashboardPanel` permet de voir ces preuves via l'accordéon.
- Nous devons ajouter un bouton "Exporter Rapport" dans l'UI du Dashboard et coder la logique d'écriture d'un fichier texte avec les données du joueur (`PlayerTelemetry`).
