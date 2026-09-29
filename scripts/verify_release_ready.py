"""
CS2 Anti-Cheat – Script de Vérification Finale Release Ready
14-step strict release gate pipeline.

Chaque étape se conclut par un statut explicite (PASS / FAIL / WARN / SKIP) :
aucune étape n'est simulée et aucune erreur n'est avalée silencieusement.
Le script sort avec le code 1 dès qu'une étape bloquante échoue.

Usage :
    python scripts/verify_release_ready.py                # gate rapide (par défaut)
    python scripts/verify_release_ready.py --with-demo    # + analyse réelle de demos/test.dem
    python scripts/verify_release_ready.py --with-build   # + build PyInstaller complet
"""

import argparse
import os
import subprocess
import sys

DIR_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DIR_RACINE not in sys.path:
    sys.path.insert(0, DIR_RACINE)

NOMBRE_ETAPES = 14
RESULTATS = []

ICONES = {"PASS": "[OK]  ", "FAIL": "[FAIL]", "WARN": "[WARN]", "SKIP": "[SKIP]"}


def _enregistrer(numero: int, titre: str, statut: str, detail: str = "") -> None:
    """Mémorise et affiche le résultat d'une étape."""
    RESULTATS.append({"numero": numero, "titre": titre, "statut": statut, "detail": detail})
    ligne = f"  {ICONES[statut]} {titre}"
    if detail:
        ligne += f" — {detail}"
    print(ligne)
    sys.stdout.flush()


def _lancer(cmd: list) -> tuple:
    """Exécute une commande depuis la racine du dépôt et renvoie (code, sortie)."""
    proc = subprocess.run(cmd, cwd=DIR_RACINE, capture_output=True, text=True, errors="replace")
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _afficher_erreur(sortie: str, lignes: int = 20) -> None:
    """Affiche la fin de la sortie d'une commande en échec."""
    contenu = [ligne for ligne in sortie.splitlines() if ligne.strip()]
    for ligne in contenu[-lignes:]:
        print(f"        | {ligne}")


def _etape_commande(numero: int, titre: str, cmd: list, detail_ok: str = "") -> bool:
    """Étape bloquante basée sur une commande externe."""
    print(f"\n[{numero}/{NOMBRE_ETAPES}] {titre}...")
    code, sortie = _lancer(cmd)
    if code == 0:
        _enregistrer(numero, titre, "PASS", detail_ok)
        return True
    _enregistrer(numero, titre, "FAIL", f"code de sortie {code}")
    _afficher_erreur(sortie)
    return False


# ----------------------------------------------------------------------------
# Étapes
# ----------------------------------------------------------------------------
def step_syntax() -> bool:
    return _etape_commande(
        1,
        "Vérification de la syntaxe (py_compile)",
        [sys.executable, "-m", "compileall", "-q", "src/", "scripts/", "tests/", "main.py", "build_exe.py"],
    )


def step_ruff() -> bool:
    return _etape_commande(
        2,
        "Vérification Ruff (config projet)",
        [sys.executable, "-m", "ruff", "check", "src/", "scripts/", "tests/", "main.py", "build_exe.py"],
    )


def step_mypy() -> bool:
    """Type-check de l'ensemble du projet. Doit passer strictement."""
    print(f"\n[3/{NOMBRE_ETAPES}] Vérification Mypy...")
    code, sortie = _lancer([sys.executable, "-m", "mypy", "src/", "tests/", "scripts/", "main.py"])
    if code == 0:
        _enregistrer(3, "Vérification Mypy", "PASS", "Aucune erreur de typage")
        return True
    _enregistrer(3, "Vérification Mypy", "FAIL", "Erreurs de typage détectées")
    _afficher_erreur(sortie, lignes=10)
    return False


def step_unit() -> bool:
    return _etape_commande(
        4,
        "Tests Unitaires",
        [sys.executable, "-m", "pytest", "tests/unit/", "-q"],
    )


def step_e2e() -> bool:
    return _etape_commande(
        5,
        "Tests E2E",
        [sys.executable, "-m", "pytest", "tests/e2e/", "-q"],
    )


def step_mocks() -> bool:
    """Vérifie que le paquet ML expose l'API publique attendue par l'application."""
    print(f"\n[6/{NOMBRE_ETAPES}] Vérification des imports et de l'API ML...")
    attendus = ("CheatClassifier", "valider_bundle_modele", "NOMS_FEATURES", "FEATURE_SCHEMA_HASH")
    try:
        import src.ml.classifier as classifier
    except Exception as exc:  # noqa: BLE001 - on rapporte l'erreur telle quelle
        _enregistrer(6, "Vérification des imports et de l'API ML", "FAIL", f"import impossible : {exc}")
        return False
    manquants = [nom for nom in attendus if not hasattr(classifier, nom)]
    if manquants:
        _enregistrer(6, "Vérification des imports et de l'API ML", "FAIL", f"symboles manquants : {manquants}")
        return False
    _enregistrer(6, "Vérification des imports et de l'API ML", "PASS", f"{len(attendus)} symboles exposés")
    return True


def step_real_demo(with_demo: bool) -> bool:
    """Analyse une vraie démo si elle est disponible (opt-in : --with-demo)."""
    demo = os.path.join(DIR_RACINE, "demos", "test.dem")
    print(f"\n[7/{NOMBRE_ETAPES}] Analyse d'une vraie démo...")
    if not with_demo:
        _enregistrer(7, "Analyse d'une vraie démo", "FAIL", "option --with-demo non activée (requise pour release)")
        return False
    if not os.path.isfile(demo):
        _enregistrer(7, "Analyse d'une vraie démo", "FAIL", "demos/test.dem absent (requis pour release)")
        return False
    try:
        from src.core.engine import AntiCheatEngine
        from src.core.models import MatchAnalysisResult
        resultat = AntiCheatEngine().analyze_demo(demo)
    except Exception as exc:  # noqa: BLE001 - on rapporte l'erreur telle quelle
        _enregistrer(7, "Analyse d'une vraie démo", "FAIL", f"exception : {exc}")
        return False
    if not isinstance(resultat, MatchAnalysisResult):
        _enregistrer(7, "Analyse d'une vraie démo", "FAIL", f"type inattendu : {type(resultat).__name__}")
        return False
    _enregistrer(
        7,
        "Analyse d'une vraie démo",
        "PASS",
        f"{resultat.map_name} — {len(resultat.players)} joueurs — verdict {resultat.global_verdict}",
    )
    return True


def step_cs2cd_fixtures() -> bool:
    """Vérifie le manifeste CS2CD local lorsqu'il est disponible."""
    print(f"\n[8/{NOMBRE_ETAPES}] Vérification des fixtures CS2CD...")
    chemin = os.path.join(DIR_RACINE, "data", "anti_cheat_dataset.csv")
    if not os.path.isfile(chemin):
        _enregistrer(8, "Vérification des fixtures CS2CD", "SKIP", "manifeste local absent (facultatif)")
        return True
    try:
        import pandas as pd
        df = pd.read_csv(chemin)
    except Exception as exc:  # noqa: BLE001 - on rapporte l'erreur telle quelle
        _enregistrer(8, "Vérification des fixtures CS2CD", "FAIL", f"lecture impossible : {exc}")
        return False
    colonnes = {"match_id", "label", "usable_for_training", "split"}
    manquantes = sorted(colonnes - set(df.columns))
    if manquantes or df.empty:
        _enregistrer(8, "Vérification des fixtures CS2CD", "FAIL", f"colonnes manquantes : {manquantes}")
        return False
    _enregistrer(8, "Vérification des fixtures CS2CD", "PASS", f"{len(df)} matchs indexés")
    return True


def step_ml_validation() -> bool:
    """Valide les bundles .pkl livrés avec l'application."""
    print(f"\n[9/{NOMBRE_ETAPES}] ML Validation (bundles .pkl)...")
    from src.ml.classifier import valider_bundle_modele

    bundles = ["cerveau_vac_cs2cd.pkl", "cerveau_vac_custom.pkl"]
    for nom in bundles:
        chemin = os.path.join(DIR_RACINE, nom)
        if not os.path.isfile(chemin):
            _enregistrer(9, "ML Validation (bundles .pkl)", "FAIL", f"{nom} absent")
            return False
        try:
            valider_bundle_modele(chemin)
        except Exception as exc:  # noqa: BLE001 - on rapporte l'erreur telle quelle
            _enregistrer(9, "ML Validation (bundles .pkl)", "FAIL", f"{nom} : {exc}")
            return False
    _enregistrer(9, "ML Validation (bundles .pkl)", "PASS", f"{len(bundles)} bundles valides")
    return True


def step_schema_hash() -> bool:
    """Vérifie la cohérence du schéma de features et des seuils du bundle de production."""
    print(f"\n[10/{NOMBRE_ETAPES}] Validation Schema Hash et seuils...")
    import joblib

    from src.ml.classifier import FEATURE_SCHEMA_HASH, NOMS_FEATURES

    bundle = joblib.load(os.path.join(DIR_RACINE, "cerveau_vac_cs2cd.pkl"))
    if bundle.get("feature_schema_hash") != FEATURE_SCHEMA_HASH:
        _enregistrer(10, "Validation Schema Hash et seuils", "FAIL", "hash de schéma obsolète")
        return False
    if bundle.get("noms_features") != list(NOMS_FEATURES):
        _enregistrer(10, "Validation Schema Hash et seuils", "FAIL", "schéma de features désaligné")
        return False
    seuil_haut = float(bundle.get("threshold_high", bundle.get("threshold", 0.0)))
    seuil_suspect = float(bundle.get("threshold_suspect", 0.0))
    if not 0.0 < seuil_suspect < seuil_haut <= 1.0:
        _enregistrer(10, "Validation Schema Hash et seuils", "FAIL", f"seuils incohérents {seuil_suspect}/{seuil_haut}")
        return False
    _enregistrer(10, "Validation Schema Hash et seuils", "PASS", f"seuils {seuil_suspect}/{seuil_haut}")
    return True


def step_packaging() -> bool:
    """Vérifie la présence des artefacts de build (le .spec est obligatoire, le dist est optionnel)."""
    print(f"\n[11/{NOMBRE_ETAPES}] Vérification du Packaging (.spec / dist)...")
    spec = os.path.join(DIR_RACINE, "CS2_AntiCheat.spec")
    if not os.path.isfile(spec):
        _enregistrer(11, "Vérification du Packaging (.spec / dist)", "FAIL", "CS2_AntiCheat.spec manquant")
        return False
    dists = [d for d in ("CS2_AntiCheat", "CS2AntiCheat") if os.path.isdir(os.path.join(DIR_RACINE, "dist", d))]
    if not dists:
        _enregistrer(11, "Vérification du Packaging (.spec / dist)", "FAIL", "spec présente, aucun dist/ (lancer un build au préalable)")
        return False
    manquants = [
        nom
        for dist in dists
        for nom in ("cerveau_vac_cs2cd.pkl", "cerveau_vac_custom.pkl")
        if not os.path.isfile(os.path.join(DIR_RACINE, "dist", dist, nom))
    ]
    if manquants:
        _enregistrer(11, "Vérification du Packaging (.spec / dist)", "FAIL", f"bundles absents du dist : {manquants}")
        return False
    _enregistrer(11, "Vérification du Packaging (.spec / dist)", "PASS", f"{len(dists)} dossier(s) dist validé(s)")
    return True


def step_smoke_test() -> bool:
    """Vérifie que la CLI répond (version et aide)."""
    print(f"\n[12/{NOMBRE_ETAPES}] Smoke Test CLI...")
    for argument in ("--version", "--help"):
        code, sortie = _lancer([sys.executable, "main.py", argument])
        if code != 0:
            _enregistrer(12, "Smoke Test CLI", "FAIL", f"main.py {argument} a échoué (code {code})")
            _afficher_erreur(sortie, lignes=10)
            return False
    _enregistrer(12, "Smoke Test CLI", "PASS", "--version et --help répondent")
    return True


def step_build(with_build: bool) -> bool:
    """Vérifie l'environnement de build ; le build complet n'est lancé qu'avec --with-build."""
    if not with_build:
        return _etape_commande(
            13,
            "Environnement de build (build_exe.py --verify-only)",
            [sys.executable, "build_exe.py", "--verify-only"],
        )
    return _etape_commande(
        13,
        "Build PyInstaller complet (build_exe.py)",
        [sys.executable, "build_exe.py"],
    )


# ----------------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="Gate de release CS2 Anti-Cheat.")
    parser.add_argument("--with-demo", action="store_true", help="Analyse réellement demos/test.dem")
    parser.add_argument("--with-build", action="store_true", help="Lance le build PyInstaller complet")
    args = parser.parse_args()

    print("=" * 60)
    print("CS2 ANTI-CHEAT – AUDIT AUTOMATISÉ RELEASE READY")
    print("=" * 60)

    bloquants = [
        step_syntax(),
        step_ruff(),
        step_mypy(),
    ]
    bloquants.extend([step_unit(), step_e2e(), step_mocks(), step_real_demo(args.with_demo)])
    bloquants.extend([step_cs2cd_fixtures(), step_ml_validation(), step_schema_hash(), step_packaging()])
    bloquants.extend([step_smoke_test(), step_build(args.with_build)])

    print(f"\n[{NOMBRE_ETAPES}/{NOMBRE_ETAPES}] Récapitulatif...")
    for statut in ("PASS", "WARN", "SKIP", "FAIL"):
        numeros = [str(r["numero"]) for r in RESULTATS if r["statut"] == statut]
        if numeros:
            print(f"  {ICONES[statut]} {statut} : étapes {', '.join(numeros)}")

    print("=" * 60)
    if all(bloquants):
        print(">>> READY FOR RELEASE <<<")
        print("=" * 60)
        return 0
    print(">>> RELEASE BLOQUÉE : corriger les étapes en FAIL ci-dessus <<<")
    print("=" * 60)
    return 1


if __name__ == "__main__":
    sys.exit(main())
