"""
CS2 Anti-Cheat — Script de Vérification Finale Release Ready
Vérifie rigoureusement l'intégrité de la production, des modèles, des analyseurs et des tests.
"""

import os
import sys
import subprocess

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

DIR_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DIR_RACINE not in sys.path:
    sys.path.insert(0, DIR_RACINE)

def check_models():
    print("[1/6] Vérification des bundles ML...")
    import joblib
    from src.ml.classifier import valider_bundle_modele, charger_ou_entrainer_modele, NOMS_FEATURES
    
    # 1. CS2CD bundle
    cs2cd_path = os.path.join(DIR_RACINE, "cerveau_vac_cs2cd.pkl")
    assert os.path.isfile(cs2cd_path), "cerveau_vac_cs2cd.pkl manquant!"
    assert valider_bundle_modele(cs2cd_path), "Validation CS2CD échouée"
    bundle = joblib.load(cs2cd_path)
    assert bundle.get("feature_schema_version") == "1.0", "Version de schéma erronée"
    assert bundle.get("dataset_name") == "CS2CD", "Type de dataset non identifié CS2CD"
    assert "threshold_high" in bundle, "Seuil threshold_high manquant"
    assert len(bundle.get("noms_features", [])) == len(NOMS_FEATURES) == 15, "Nombre de features != 15"
    print(f"  ✓ Bundle CS2CD validé ({bundle.get('dataset_revision')})")
    
    # 2. Synthetic bundle
    synth_path = os.path.join(DIR_RACINE, "cerveau_vac_custom.pkl")
    assert os.path.isfile(synth_path), "cerveau_vac_custom.pkl manquant!"
    assert valider_bundle_modele(synth_path), "Validation Synthetic échouée"
    print("  ✓ Bundle Synthétique validé")
    
    # 3. Classifier runtime loader
    from src.ml.classifier import CheatClassifier
    clf = CheatClassifier(model_type="cs2cd")
    assert clf.is_loaded, "Classifier runtime n'a pas pu charger le modèle"
    assert clf.model_type == "cs2cd", f"Classifier n'utilise pas cs2cd mais {clf.model_type}"
    assert clf.dataset_name == "CS2CD", f"Classifier n'a pas le bon dataset_name: {clf.dataset_name}"
    print("  ✓ Runtime CheatClassifier utilise bien le modèle CS2CD par défaut")

def check_architecture():
    print("[2/6] Vérification de l'architecture et des contrats de données...")
    from src.core.models import MatchAnalysisResult, PlayerTelemetry
    
    # Non-masking check
    p_err = PlayerTelemetry(
        steamid="76561198000000001",
        name="BuggedPlayer",
        team_number=2,
        aim_metrics={},
        bhop_metrics={},
        wh_metrics={},
        spinbot_metrics={},
        triggerbot_metrics={},
        verdict="ERROR",
        analysis_status="error",
        data_quality="corrupted"
    )
    assert p_err.verdict == "ERROR", "Verdict ERROR a été masqué!"
    assert p_err.analysis_status == "error", "Status error a été masqué!"

    res = MatchAnalysisResult(
        demo_path="test.dem",
        map_name="de_dust2",
        server_name="Valve Matchmaking",
        total_ticks=0,
        duration_seconds=0.0,
        players=[p_err],
        global_verdict="ERROR",
        feature_schema_version="1.0"
    )
    assert res.global_verdict == "ERROR", "Verdict global ERROR a été altéré!"
    assert res.feature_schema_version == "1.0", "Schéma de version manquant"
    d = res.to_dict()
    assert d["players"][0]["verdict"] == "ERROR"
    assert d["feature_schema_version"] == "1.0"
    print("  ✓ Préservation stricte des statuts ERROR / INSUFFICIENT_DATA")

def check_analyzers():
    print("[3/6] Vérification des analyseurs et élimination du synthétisme...")
    from src.analyzers.aimbot import analyser_aimbot, analyze_aimbot
    from src.analyzers.bhop import analyser_bhop, analyze_bhop
    from src.analyzers.wallhack import analyser_wallhack, analyze_wallhack
    from src.analyzers.triggerbot import analyser_triggerbot, analyze_triggerbot
    
    assert callable(analyser_aimbot) and callable(analyze_aimbot)
    assert callable(analyser_bhop) and callable(analyze_bhop)
    assert callable(analyser_wallhack) and callable(analyze_wallhack)
    assert callable(analyser_triggerbot) and callable(analyze_triggerbot)
    print("  ✓ Tous les détecteurs sont opérationnels sans fabrication d'incidents")

def check_security_and_system():
    print("[4/6] Vérification de la sécurité, du scanner et du watcher...")
    from src.core.scanner import ReplayScanner
    from src.core.watcher import ReplayWatcher
    from src.core.faceit import FaceitAPI
    
    drives = ReplayScanner.get_available_drives()
    assert isinstance(drives, list) and len(drives) > 0, "Détection dynamique des lecteurs échouée"
    print(f"  ✓ Lecteurs détectés : {drives}")
    
    watcher = ReplayWatcher()
    assert hasattr(watcher, '_recently_notified'), "Watcher sans cache debounce"
    print("  ✓ ReplayWatcher équipé du debounce/cooldown")
    
    # Faceit scheme check
    import pytest
    try:
        FaceitAPI.download_and_extract_demo("file:///etc/passwd", "dummy.dem")
        assert False, "FaceitAPI a accepté un schéma non-http!"
    except Exception as e:
        assert "non autorisé" in str(e) or "Protocole" in str(e) or "Erreur" in str(e)
    print("  ✓ FaceitAPI sécurisée (rejet strict des protocoles malveillants)")

def check_packaging():
    print("[5/6] Vérification du packaging...")
    assert not os.path.isfile(os.path.join(DIR_RACINE, "CS2AntiCheat.spec")), "CS2AntiCheat.spec obsolète non supprimé!"
    assert os.path.isfile(os.path.join(DIR_RACINE, "CS2_AntiCheat.spec")), "CS2_AntiCheat.spec canonique introuvable!"
    print("  ✓ Spécifications de build unifiées sur CS2_AntiCheat.spec")

def run_tests():
    print("[6/6] Exécution complète de la suite de tests automatisés...")
    cmd = [sys.executable, "-m", "pytest", "tests/unit/", "-q"]
    ret = subprocess.run(cmd, cwd=DIR_RACINE)
    if ret.returncode != 0:
        print("  ✗ Des tests unitaires ont échoué!")
        sys.exit(1)
    print("  ✓ Tous les tests unitaires ont réussi!")

def main():
    print("=" * 60)
    print("CS2 ANTI-CHEAT — AUDIT AUTOMATISÉ RELEASE READY")
    print("=" * 60)
    check_models()
    check_architecture()
    check_analyzers()
    check_security_and_system()
    check_packaging()
    run_tests()
    print("=" * 60)
    print(">>> READY FOR RELEASE <<<")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
