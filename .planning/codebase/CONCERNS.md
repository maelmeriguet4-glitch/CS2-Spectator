# Concerns

**Analysis Date:** 2026-09-20

## Tech Debt
- High amount of ruff errors logged (`ruff_errors.json` has ~400KB, `ruff_errors_filtered.json` has ~235KB).
- `mypy_errors.txt` present, suggesting some type checking inconsistencies.
- Large binary artifacts (`.pkl` models over 2MB) stored in the repo root; should ideally be managed with DVC or a similar tool.

## Vulnerabilities / Security
- Unvalidated `.pkl` loading: Loading pickle files from arbitrary sources can be insecure due to arbitrary code execution risks. 

## Architectural Concerns
- Hardcoded GUI fallback mechanism in `main.py` (trying `src.ui.app.CS2AntiCheatApp` then falling back to `AntiCheatApp` upon *any* exception). This can swallow syntax errors or missing dependencies, leading to confusing debugging sessions.

---

*Concerns analysis: 2026-09-20*
