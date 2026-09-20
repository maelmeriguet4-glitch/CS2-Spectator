# Test Infrastructure Specification: CS2 Anti-Cheat Desktop Application

## 1. Overview & Objectives
This document defines the comprehensive, requirement-driven, opaque-box test infrastructure for the Counter-Strike 2 Anti-Cheat Desktop Application. The testing strategy enforces strict test integrity, zero facade testing, and realistic multi-tier verification covering requirements R1 through R5.

All tests are designed to execute strictly locally in Windows/PowerShell environments without any remote repository dependencies, conforming to the project's confidentiality and verification constraints.

---

## 2. Test Architecture: 4-Tier Methodology

The test suite is partitioned into four distinct tiers under `tests/e2e/`:

```
tests/
├── conftest.py
├── e2e/
│   ├── run_all_e2e.py                # Standalone test runner (exit 0 = pass, non-zero = fail)
│   ├── test_tier1_features.py        # Tier 1: Core Feature Coverage (>=5 tests per R1-R5)
│   ├── test_tier2_boundaries.py      # Tier 2: Boundary & Corner Cases (>=5 tests per feature)
│   ├── test_tier3_interactions.py    # Tier 3: Cross-Feature Pairwise Interactions
│   └── test_tier4_real_world.py       # Tier 4: Real-World Workload Scenarios (Live Demos)
└── unit/                             # Isolated module unit tests (owned by feature workers)
```

### Tier 1: Feature Coverage
Validates the primary happy path and functionality contract for each requirement:
- **R1: Replay Detection & Management**:
  - Windows registry / VDF multi-drive Steam library discovery.
  - Active CS2 replays directory discovery (`D:\SteamLibrary\...\csgo\replays\`).
  - Fallback discovery to local `demos/` and drive heuristics.
  - Replay cataloging (file size, timestamp sorting, map name extraction).
  - 3-step debounce watcher (size stability, lock check, `PBDEMS2` magic header).
- **R2: Biomechanical Engine & ML Scoring**:
  - `demoparser2` ingestion of player info, ticks, events, and SteamID64 extraction.
  - Aimbot telemetry (angle wrap modulo 360, angular velocity, combat window snap $[-5, +10]$, jerk).
  - BunnyHop telemetry (1-tick ground-air transitions $\le 1$, jump chains, ground delay variance).
  - Wallhack telemetry (3D eye-ray vector alignment $\mathbf{D} = \mathbf{P}_e - \mathbf{P}_j$ vs unspotted occluded enemies $200 \le d \le 2000$, lock tracking).
  - Machine learning classification using `cerveau_vac_custom.pkl` (15 features, `StandardScaler`, `RandomForestClassifier`, 3-tier verdict calibration).
- **R3: Modern Tactical GUI & Player Cards**:
  - Dark cyber theme palette constants and CustomTkinter configuration.
  - Match header widget with map, server, and integrity summary.
  - Rich player card rendering (suspicion gauge 0-100%, status badges, violation pills).
  - Monospace SteamID64 display and profile action links.
  - Asynchronous worker thread and message queue responsiveness.
- **R4: Steam & Faceit Reporting Wizard with Interactive QCM**:
  - Modal window instantiation and grab management.
  - Multi-select QCM checklist options (pre-aim smoke, aimbot snap, bhop script, etc.).
  - Automatic quantitative telemetry proof formatting.
  - Dual-tab report formatting: Steam In-Game/Community format vs Faceit Support Ticket format.
  - Clipboard integration (`pyperclip`) and browser profile URL generation.
- **R5: Standalone Packaging & Distribution**:
  - Modular directory layout verification (`src/core`, `src/analyzers`, `src/ml`, `src/ui`).
  - Production `requirements.txt` validation against active dependencies.
  - `build_exe.py` PyInstaller configuration (windowed `--noconsole`, `--collect-all`, `--add-data`).
  - Runtime resource resolver helper (`sys._MEIPASS` fallback).
  - Bilingual documentation presence and structure (`README.md` FR & EN).

### Tier 2: Boundary & Corner Cases
Ensures system robustness and failure resistance under adverse conditions:
- Empty replays directory or non-existent scan paths.
- Corrupt, empty, or truncated `.dem` files and invalid magic headers.
- Missing SteamID64 or bot IDs (`steamid == 0`, `steamid == ""`, `[BOT]`).
- Zero movement, zero shooting, or zero combat tick windows.
- Extreme view angles (Yaw: $-180^\circ$ to $+180^\circ$, Pitch: $-89^\circ$ to $+89^\circ$, wrap boundaries).
- Extreme Unicode player nicknames (emojis, Cyrillic, Chinese, control characters).
- Rapid repeated start/stop cycles of the replay watcher.
- Incomplete QCM selections or empty auditor notes in report generation.
- Scaler and classifier inference with NaN, infinite, or all-zero feature vectors.
- Large tick jumps or out-of-order tick sequences in demo streams.

### Tier 3: Cross-Feature Interactions
Validates pairwise data contracts and subsystem handoffs:
- **Scanner + Watcher + Engine**: Auto-discovered replay handed to watcher debounce and dispatched to analysis engine.
- **Demo Ingestion + Telemetry + Classifier**: Raw ticks processed through Aimbot, Bhop, and Wallhack analyzers, fed to 15-feature ML pipeline, yielding structured `PlayerTelemetry`.
- **Engine + Reporting Wizard + Clipboard**: Full `MatchAnalysisResult` feeding individual player data to `ReportGenerator`, formatted across Steam/Faceit tabs, and copied to system clipboard.
- **GUI Components + Background Threading**: Worker thread pushing progress and results through `queue.Queue` to CTk UI components without deadlocks or GUI freezes.
- **Scanner + Parser + URL Builders**: Demo metadata extraction providing SteamID64 seamlessly into Steam and Faceit URL openers.

### Tier 4: Real-World Workload Scenarios
Tests full end-to-end execution on authentic CS2 match data:
- Ingestion and full analysis of `demos/test.dem` (264.9 MB, `de_inferno`, 10 competitive players).
- Verification of all 10 extracted players: valid SteamID64s, non-empty nicknames, correct CT/T team assignments.
- Complete biomechanical profiling for all 10 players without memory leaks or uncaught exceptions.
- Model classification verification: probability ranges, calibrated verdicts (`CLEAN`, `SUSPECT`, `CHEATER`).
- End-to-end report generation for suspect/cheater players with full telemetry proofs and format validation.
- End-to-end replay watcher simulation with synthetic demo creation, stabilization, and automatic analysis triggering.

---

## 3. Environment & Prerequisites

- **Operating System**: Windows 10 / Windows 11 64-bit
- **Python Version**: Python 3.14.7 (AMD64)
- **Key Python Packages**:
  - `demoparser2>=0.41.4`: Valve Source 2 demo parser (Rust extension)
  - `customtkinter>=6.0.0`: Modern dark tactical GUI
  - `watchdog>=6.0.0`: Cross-platform filesystem observer
  - `scikit-learn>=1.3.0` & `joblib>=1.3.0`: ML model inference
  - `pandas>=2.0.0` & `numpy>=1.24.0`: Vectorized tick processing
  - `pyperclip>=1.11.0`: System clipboard copy/paste
  - `PyInstaller>=6.0.0`: Executable bundler
- **Test Framework**: Python standard library `unittest` (zero external test runner dependencies; 100% compatible with `pytest`).

---

## 4. Test Execution Instructions

### Complete E2E Suite Execution (Recommended)
Run the dedicated standalone test runner:
```powershell
python tests/e2e/run_all_e2e.py
```
*Exit code is `0` on 100% pass, non-zero on any failure.*

### Standard Unittest Runner Execution
```powershell
# Run all E2E tests
python -m unittest discover -s tests/e2e -p "test_*.py" -v

# Run individual tiers
python -m unittest tests/e2e/test_tier1_features.py -v
python -m unittest tests/e2e/test_tier2_boundaries.py -v
python -m unittest tests/e2e/test_tier3_interactions.py -v
python -m unittest tests/e2e/test_tier4_real_world.py -v
```

---

## 5. Test Integrity & Verification Standards

1. **No Mocking of Analyzed Outputs**: Real biomechanical calculations and model predictions are verified against real inputs or mathematical ground truth.
2. **Deterministic Validation**: Floating point values are compared using `assertAlmostEqual` or delta tolerances to accommodate platform floating point precision.
3. **Isolation & Cleanup**: Every test managing temporary files (watchers, test demos, configs) creates dedicated temp directories with `tempfile.TemporaryDirectory` and guarantees cleanup on teardown.
4. **Headless Execution**: CustomTkinter / Tkinter components are instantiated without blocking `mainloop()` and destroyed cleanly in teardown, allowing execution in headless CI or console sessions.
