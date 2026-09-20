# 🛡️ CS2 Anti-Cheat Dashboard

> **Biomechanical Analysis & Artificial Intelligence** to detect cheaters in Counter-Strike 2.
> **Analyse biomécanique & Intelligence Artificielle** pour détecter les tricheurs dans CS2.
> 100% legal — No memory injection — Based on official replay files (.dem).

---

## 🎯 Features / Fonctionnalités

### 🔍 Automatic Detection / Détection Automatique
- **Auto CS2 discovery** : Finds your Counter-Strike 2 install across Steam libraries (`D:\SteamLibrary\.../csgo/replays`).
- **Real-time watcher** : Toggle "Armer la surveillance" to auto-analyze newly downloaded demos.
- **Manual browser** : Load any external `.dem` file (tournaments, faceit, etc.).
- **Détection auto CS2**, **surveillance temps réel**, **sélection manuelle** d'un `.dem`.

### 🧠 AI Analysis Engine / Moteur IA
- **Aimbot** : Instant angular snaps (°/tick), jerk, micro-corrections.
- **BunnyHop** : Tick-perfect 1-tick ground transitions, humanly impossible chains.
- **Wallhack / ESP** : 3D Source 2 eye-ray alignment vs occluded enemies, continuous tracking.
- **Machine Learning** : RandomForest (200 trees) + IsolationForest on pro-player calibrated dataset (15 features).

### 🎨 Modern Tactical GUI / Interface Tactique
- Dark cyber theme (`#0B0F19` / `#161E2E` / `#00F0FF`) — CustomTkinter.
- 10 rich player cards with suspicion gauge 0-100%, status badges (🟢 CLEAN / 🟡 SUSPECT / 🔴 CHEATER), violation pills.
- SteamID64 auto-extracted, links to Steam Community & FaceitFinder.

### ⚠️ Reporting Wizard / Signalement
- Interactive QCM (6 observations) + free commentary.
- Dual pre-formatted reports : **Steam Community** & **Faceit Support Ticket** with quantitative telemetry proof (tick, snap angles, lock duration).
- One-click clipboard copy + direct profile open.

---

## 📦 Installation

### Prérequis / Requirements
- Python 3.10+ (tested 3.14)
- Counter-Strike 2 installed (for auto replay discovery)

### Quick Start / Démarrage Rapide
```bash
git clone https://github.com/VOTRE_USERNAME/cs2-anticheat.git
cd cs2-anticheat
pip install -r requirements.txt
python main.py
```

### Build Standalone .exe (optionnel)
```bash
python build_exe.py
# Output -> dist/CS2AntiCheat/CS2AntiCheat.exe  (windowed, no console)
# Alternative: pyinstaller CS2AntiCheat.spec
```

---

## 🚀 Usage / Utilisation

1. **Launch** `python main.py` or `dist/CS2AntiCheat/CS2AntiCheat.exe`.
2. **Select a demo** from auto-detected list or click "Parcourir..." / "Browse".
3. **Wait for analysis** — progress bar + `PROGRESS` queue shows 0→100%.
4. **Review results** — players sorted by suspicion (cheaters first).
5. **Report** a suspect via "Générer Signalement" — pick QCM options, copy Steam/Faceit report.

---

## 🏗️ Project Structure

```
cs2_anticheat/
├── main.py
├── requirements.txt
├── build_exe.py / CS2AntiCheat.spec
├── cerveau_vac_custom.pkl  (RF 200 trees, 15 features)
├── src/
│   ├── core/  parser.py  scanner.py  watcher.py  engine.py  reporter.py  models.py
│   ├── analyzers/  aimbot.py  bhop.py  wallhack.py
│   ├── ml/  classifier.py
│   └── ui/  app.py  theme.py  components/{header,player_card,replays_panel,report_modal}.py
├── tests/  unit/  e2e/ (4 tiers)
└── demos/  test.dem (+ pro*.dem)
```

---

## ⚖️ Legality / Légalité

100% legal — No injection, no memory read, no overlay. Only parses official `.dem` files via `demoparser2`.
100% légal — Aucune injection, lecture mémoire ou hook. Analyse uniquement les replays officiels.

---

## 📄 License / Licence

MIT — See LICENSE file.

---

## 🌐 Documentation / Bilingual Guide

### Français
- **Installation** : `pip install -r requirements.txt` puis `python main.py`
- **Utilisation** : Sélectionnez une démo dans `D:\SteamLibrary\...` ou parcourez un `.dem` externe, lancez l'analyse, consultez les 10 cartes joueurs et générez un signalement via QCM.

### English
- **Overview** : Tactical CustomTkinter dashboard with hybrid Steam replay discovery, biomechanical telemetry (Aimbot/Bhop/Wallhack) and ML classification.
- **Prerequisites** : Python 3.10+, CS2 installed, 2GB RAM, Windows 10/11.
- **Installation & Usage** : see French section above.

### Requirements Coverage
- **R1** Hybrid CS2 Demo Detection & Replay Management (Scanner + Watcher)
- **R2** High-Precision Biomechanical Engine (Aimbot/Bhop/Wallhack + ML)
- **R3** Modern Tactical GUI & Rich Player Cards
- **R4** Steam & Faceit Reporting Wizard (QCM + Telemetry Proof)
- **R5** Standalone Packaging (build_exe.py + CS2AntiCheat.spec)

Key files: `main.py` (entry point with CLI), `build_exe.py` (PyInstaller `--noconsole`), `requirements.txt` (all deps).

---

## 🧪 Tests

```powershell
python -m unittest discover -s tests -v
python -m unittest tests.unit.test_ml tests.unit.test_scanner tests.unit.test_watcher tests.unit.test_ui -v
python tests/e2e/run_all_e2e.py
```
