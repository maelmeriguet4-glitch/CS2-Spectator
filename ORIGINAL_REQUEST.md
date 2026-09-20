# Original User Request

## 2026-09-05T10:48:49Z

CS2 Anti-Cheat Desktop Application: A modern CustomTkinter tactical dashboard for Counter-Strike 2 replays with automatic game demo detection, Steam/Faceit profile integration, interactive reporting wizard with QCM, and standalone executable packaging.

Working directory: c:/Users/pc/Desktop/Cs2 anticheat/cs2_anticheat
Integrity mode: development

## Requirements

### R1. Hybrid CS2 Demo Detection & Replay Management
- Automatically locate the active Counter-Strike 2 installation across Steam libraries (specifically `D:\SteamLibrary\steamapps\common\Counter-Strike Global Offensive\game\csgo\replays\`).
- Provide an interactive replay selector listing recent downloaded matches with map name, timestamp, and size.
- Include a real-time folder watcher toggle ("Armer la surveillance") that listens for newly finished/downloaded `.dem` files and launches analysis automatically.
- Provide a manual file browser button allowing users to load any external or tournament `.dem` file.

### R2. High-Precision Biomechanical Cheat Detection Engine
- Refactor and integrate the telemetry engines:
  - **Aimbot**: measure angular velocity, instantaneous snap degrees/tick during shooting windows, angular jerk, and micro-adjustments.
  - **BunnyHop**: measure tick-perfect 1-tick ground airborne transitions and chained jump sequences.
  - **Wallhack / ESP**: compute 3D Source 2 eye-ray alignment vectors against unspotted (occluded) enemies and track duration.
- Extract player `steamid` (SteamID64) and nickname directly via `demoparser2`.
- Classify players using the pre-trained Machine Learning model (`cerveau_vac_custom.pkl`) into Clean, Suspect, or Confirmed Cheater with confidence percentage and detailed violation flags.

### R3. Modern Tactical GUI & Rich Player Cards
- Build a responsive CustomTkinter dark-themed interface with tactical CS2 cyber aesthetics.
- Match header displaying map, server, and overall integrity summary.
- 10 rich player cards featuring:
  - Global suspicion meter (0-100%) and color-coded status badge (🟢 Clean, 🟡 Suspect, 🔴 Tricheur Avéré).
  - Categorized violation pills (e.g., `[AIMBOT: Snap 32.4°/tick]`, `[WALLHACK: 14 Locks Mur]`, `[BHOP: Script 87%]`).
  - SteamID64 and direct links to Steam Community and Faceit profile / FaceitFinder.
  - Dedicated "Générer Signalement" button opening the reporting wizard.
- Asynchronous analysis running in background threads to guarantee smooth UI without freezing.

### R4. Steam & Faceit Reporting Wizard with Interactive QCM
- Interactive modal pop-up per player featuring:
  - Quick interactive QCM allowing the user to select specific in-game observations (e.g., pre-aiming through smokes, impossible reaction snaps, inhuman bunnyhop traversal).
  - Automatic compilation of objective telemetry proof (tick numbers, round context, snap angles, lock durations, SteamID64).
  - Dual pre-formatted tabs: one tailored for Steam In-Game / Community Reports and one for Faceit Support Tickets.
  - Direct action buttons: "Copier le signalement", "Ouvrir Profil Steam", and "Ouvrir Faceit / FaceitFinder".

### R5. Complete GitHub Distribution & Standalone Executable Packaging
- `build_exe.py` script configuring PyInstaller in windowed mode (no console window), bundling assets and AI models.
- Clean project modular structure separating `src/analyzers`, `src/core`, `src/ml`, `src/ui`.
- Comprehensive `requirements.txt` containing all dependencies.
- Polished `README.md` in French & English with features, installation steps, screenshots guide, and GitHub release instructions.

## Acceptance Criteria

### Execution & Verification
- [ ] CS2 replays from `D:\SteamLibrary\...\csgo\replays\` are discovered and listed automatically in the UI.
- [ ] Selecting a demo parses all players, extracts SteamID64, and calculates Aim/Bhop/Wallhack scores without crash.
- [ ] UI remains responsive with a progress bar / status indicator during parsing.
- [ ] Clicking "Générer Signalement" opens the QCM modal, personalizes the message, and copies formatted text to clipboard.
- [ ] Profil Steam and Faceit links open the exact player page in the browser or Steam.
- [ ] `build_exe.py` successfully produces a standalone executable in `dist/` or verifies executable bundling readiness.

## Follow-up — 2026-09-05T10:49:28Z

Instruction de l'utilisateur : Réalise tout le code et les tests correctement en local, mais NE POUSSE/NE PUBLIE PAS sur GitHub pour le moment. L'utilisateur testera l'application en local et confirmera quand il voudra la publier. Prépare les fichiers locaux (structure, GUI, .exe, README, tests) pour qu'il puisse tester directement sur son PC.
