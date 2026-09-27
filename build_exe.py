"""
CS2 Anti-Cheat — Script de compilation en exécutable (.exe)
Utilise PyInstaller pour créer un exécutable Windows standalone.
"""

import subprocess
import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


def get_pyinstaller_args(target_script="main.py", app_name="CS2AntiCheat", model_file="cerveau_vac_custom.pkl", onefile=False):
    """Construit la liste d'arguments PyInstaller attendue par les tests."""
    args = []
    if onefile:
        args.append("--onefile")
    else:
        args.append("--onedir")
    args.extend([
        "--noconsole",
        "--noconfirm",
        "--clean",
        "--name", app_name,
        "--collect-all=customtkinter",
        "--collect-all=demoparser2",
    ])
    # hidden imports
    for hi in ["watchdog", "pyperclip", "sklearn", "joblib", "pandas", "numpy", "PIL", "darkdetect", "reportlab"]:
        args.append(f"--hidden-import={hi}")
    # model files
    sep = ";" if os.name == "nt" else ":"
    if model_file:
        args.extend(["--add-data", f"{model_file}{sep}."])
    if os.path.exists("cerveau_vac_cs2cd.pkl") and model_file != "cerveau_vac_cs2cd.pkl":
        args.extend(["--add-data", f"cerveau_vac_cs2cd.pkl{sep}."])
    # target script at end
    if target_script:
        args.append(target_script)
    return args


def verify_build_environment():
    """Vérifie que l'environnement permet la compilation."""
    repo = os.path.dirname(os.path.abspath(__file__))
    target_exists = os.path.isfile(os.path.join(repo, "main.py"))
    model_exists = os.path.isfile(os.path.join(repo, "cerveau_vac_cs2cd.pkl")) or os.path.isfile(os.path.join(repo, "cerveau_vac_custom.pkl"))
    try:
        import PyInstaller
        pyinstaller_installed = True
        print("PyInstaller installé           : [OK]")
    except ImportError:
        pyinstaller_installed = False
        print("PyInstaller installé           : [MANQUANT]")

    for dep in ["customtkinter   ", "demoparser2     "]:
        mod = dep.strip()
        try:
            __import__(mod)
            print(f"Dépendance '{dep}' : [OK]")
        except ImportError:
            print(f"Dépendance '{dep}' : [MANQUANT]")

    all_passed = target_exists and model_exists and pyinstaller_installed
    return {
        "target_exists": target_exists,
        "model_exists": model_exists,
        "pyinstaller_installed": pyinstaller_installed,
        "all_passed": all_passed,
    }


def build(verify_only=False, **kwargs):
    """Lance la compilation PyInstaller. Si verify_only True, dry-run."""
    if verify_only:
        checks = verify_build_environment()
        if checks["all_passed"]:
            print("[VÉRIFICATION RÉUSSIE] Environnement prêt pour la compilation.")
            return 0
        else:
            print("[ÉCHEC] Environnement incomplet.")
            return 1
    try:
        import PyInstaller
    except ImportError:
        print("[!] PyInstaller non trouvé. Veuillez l'installer via vos dépendances (pyproject.toml).")
        sys.exit(1)

    repo = os.path.dirname(os.path.abspath(__file__))
    script = "main.py"
    modele = "cerveau_vac_cs2cd.pkl"

    py_args = get_pyinstaller_args(target_script=script, app_name="CS2_AntiCheat", model_file=modele if os.path.exists(modele) else None, onefile=kwargs.get("onefile", False))
    # Extra handling for src add-data and icon
    if os.path.isdir(os.path.join(repo, "src")):
        sep2 = ";" if os.name == "nt" else ":"
        py_args.extend(["--add-data", f"src{sep2}src"])

    full_cmd = [sys.executable, "-m", "PyInstaller"] + py_args

    print("=" * 60)
    print("[BUILD] CS2 Anti-Cheat -- Compilation en .exe")
    print("=" * 60)
    try:
        print(f"Script : {script}")
        print(f"Modele IA : {modele if os.path.exists(modele) else 'Non trouve'}")
        print(f"Args: {' '.join(py_args)}")
    except UnicodeEncodeError:
        pass
    print()

    # Ensure UTF-8 for subprocess on Windows cp1252
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    subprocess.run(full_cmd, check=True, env=env)

    print()
    print("=" * 60)
    print("[OK] Compilation terminee !")
    print("   Executable dans dist/CS2_AntiCheat/")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--verify-only", action="store_true")
    args = p.parse_args()
    sys.exit(build(verify_only=args.verify_only))
