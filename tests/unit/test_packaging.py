"""
Unit tests for Milestone 5: Standalone Packaging, CLI, and Distribution Manifests.
Tests main.py argument parsing, resource_path resolution, build_exe.py configuration,
requirements.txt integrity, and README.md documentation completeness.
"""

import os
import sys
import unittest
from unittest.mock import patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import build_exe
import main


class TestPackagingUnit(unittest.TestCase):
    """Unit tests for packaging, CLI entry points, and build verification."""

    def test_main_resource_path_dev_mode(self):
        """Verify resource_path resolves relative to repo root in development mode."""
        path = main.resource_path("cerveau_vac_custom.pkl")
        expected = os.path.normpath(os.path.join(REPO_ROOT, "cerveau_vac_custom.pkl"))
        self.assertEqual(path, expected)
        self.assertTrue(os.path.isfile(path), "Resolved model file must exist on disk")

    def test_main_resource_path_frozen_mode(self):
        """Verify resource_path resolves relative to sys._MEIPASS when frozen by PyInstaller."""
        mock_meipass = r"C:\Temp\_MEI123456"
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "_MEIPASS", mock_meipass, create=True):
            resolved = main.resource_path("cerveau_vac_custom.pkl")
            expected = os.path.normpath(os.path.join(mock_meipass, "cerveau_vac_custom.pkl"))
            self.assertEqual(resolved, expected)

    def test_main_cli_argument_parser_demo(self):
        """Verify create_parser parses --demo argument correctly."""
        parser = main.create_parser()
        args = parser.parse_args(["--demo", "demos/test.dem"])
        self.assertEqual(args.demo, "demos/test.dem")
        self.assertIsNone(args.model)

    def test_main_cli_argument_parser_model(self):
        """Verify create_parser parses --model argument correctly."""
        parser = main.create_parser()
        args = parser.parse_args(["--model", "custom_model.pkl"])
        self.assertEqual(args.model, "custom_model.pkl")
        self.assertIsNone(args.demo)

    def test_main_cli_version_flag(self):
        """Verify create_parser handles --version flag via SystemExit."""
        parser = main.create_parser()
        with self.assertRaises(SystemExit) as cm:
            parser.parse_args(["--version"])
        self.assertEqual(cm.exception.code, 0)

    def test_main_console_analysis_missing_file(self):
        """Verify run_console_analysis returns error code 1 for missing demo file."""
        code = main.run_console_analysis("non_existent_file_12345.dem")
        self.assertEqual(code, 1)

    def test_build_exe_argument_construction(self):
        """Verify build_exe.get_pyinstaller_args generates all required flags."""
        args = build_exe.get_pyinstaller_args(
            target_script="main.py",
            app_name="CS2AntiCheat",
            model_file="cerveau_vac_custom.pkl",
            onefile=False,
        )

        self.assertIn("--noconsole", args)
        self.assertIn("--noconfirm", args)
        self.assertIn("--clean", args)
        self.assertIn("--onedir", args)
        self.assertIn("--collect-all=customtkinter", args)
        self.assertIn("--collect-all=demoparser2", args)
        self.assertIn("cerveau_vac_custom.pkl", " ".join(args))

        for hi in ["watchdog", "pyperclip", "sklearn", "joblib"]:
            self.assertIn(f"--hidden-import={hi}", args)

    def test_build_exe_argument_construction_onefile(self):
        """Verify build_exe.get_pyinstaller_args supports --onefile flag."""
        args = build_exe.get_pyinstaller_args(onefile=True)
        self.assertIn("--onefile", args)
        self.assertNotIn("--onedir", args)

    def test_build_exe_environment_verification(self):
        """Verify build_exe.verify_build_environment checks pass on current environment."""
        checks = build_exe.verify_build_environment()
        self.assertTrue(checks["target_exists"], "main.py must exist")
        self.assertTrue(checks["model_exists"], "cerveau_vac_custom.pkl must exist")
        self.assertTrue(checks["pyinstaller_installed"], "PyInstaller must be installed")
        self.assertTrue(checks["all_passed"], "All environment checks must pass")

    def test_build_exe_verify_only_execution(self):
        """Verify build(verify_only=True) executes dry-run without error."""
        code = build_exe.build(verify_only=True)
        self.assertEqual(code, 0)

    def test_requirements_file_validity(self):
        """Verify requirements.txt is present, has no duplicate entries, and includes key packages."""
        req_path = os.path.join(REPO_ROOT, "requirements.txt")
        self.assertTrue(os.path.isfile(req_path), "requirements.txt must exist")

        with open(req_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]

        # Check no duplicates
        package_names = [line.split(">=")[0].split("==")[0].lower() for line in lines]
        duplicates = [p for p in set(package_names) if package_names.count(p) > 1]
        self.assertEqual(len(duplicates), 0, f"Duplicate packages found: {duplicates}")

        # Check required packages are included
        required = [
            "customtkinter",
            "demoparser2",
            "watchdog",
            "pyperclip",
            "scikit-learn",
            "joblib",
            "pandas",
            "pyarrow",
            "pyinstaller",
        ]
        for pkg in required:
            self.assertIn(pkg, package_names, f"Package '{pkg}' missing from requirements.txt")

    def test_readme_documents_cs2cd_pipeline_and_release(self):
        """Verify README documents the CS2CD workflow, cautious scores, and releases."""
        readme_path = os.path.join(REPO_ROOT, "README.md")
        self.assertTrue(os.path.isfile(readme_path), "README.md must exist")

        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()

        required_content = [
            "795 matchs",
            "52,6 Go",
            "CS2CDAdapter",
            "PyArrow",
            "data/anti_cheat_dataset.example.csv",
            "`unknown`",
            "`probable_non_cheater`",
            "44,4 %",
            "match_id:player_id",
            "Train (70 %)",
            "`suspicion_score`",
            "`suspicion_scores`",
            "`threshold_high`",
            "`threshold_suspect`",
            "cerveau_vac_custom.pkl",
            "cerveau_vac_cs2cd.pkl",
            "`--model-type cs2cd|synthetic|custom`",
            "scripts/index_cs2cd.py",
            "scripts/train_cs2cd.py",
            "scripts/verify_release_ready.py",
            "python -m pytest tests/unit/ -q",
            "Qualité et préparation des releases",
            "monofichier",
            "onedir",
            "tests de régression P0",
            "CS2_AntiCheat.exe",
            "2.5.2",
            "Signaler un problème",
        ]
        for item in required_content:
            self.assertIn(item, content, f"README must document '{item}'")

        self.assertTrue(os.path.isfile(os.path.join(REPO_ROOT, "logo.png")))
        self.assertTrue(
            os.path.isfile(os.path.join(REPO_ROOT, ".github", "workflows", "release.yml"))
        )
        self.assertTrue(
            os.path.isfile(os.path.join(REPO_ROOT, ".github", "ISSUE_TEMPLATE", "bug_report.yml"))
        )

        with open(os.path.join(REPO_ROOT, "CS2_AntiCheat.spec"), "r", encoding="utf-8") as f:
            spec = f.read()
        self.assertIn("cerveau_vac_cs2cd.pkl", spec)
        self.assertIn("cerveau_vac_custom.pkl", spec)
        self.assertIn("('src', 'src')", spec)

        with open(os.path.join(REPO_ROOT, ".github", "workflows", "release.yml"), "r", encoding="utf-8") as f:
            workflow = f.read()
        self.assertIn("python build_exe.py --onefile", workflow)
        self.assertIn("dist/CS2_AntiCheat.exe", workflow)
        self.assertIn("actions/upload-artifact@v4", workflow)
        self.assertIn("actions/download-artifact@v4", workflow)
        self.assertIn("softprops/action-gh-release@v2", workflow)
        self.assertNotIn("audit_results.txt", workflow)
        self.assertNotIn("train_log.txt", workflow)
        self.assertNotIn("apply_audit_fixes.py", workflow)
        self.assertNotIn("*.parquet", workflow)
        self.assertIn("name='CS2_AntiCheat'", spec)
        self.assertNotIn("COLLECT(", spec)

    def test_release_gate_skips_missing_local_cs2cd_manifest(self):
        """The release gate must not require a private, untracked CS2CD manifest."""
        from scripts import verify_release_ready

        with patch("scripts.verify_release_ready.os.path.isfile", return_value=False):
            with patch.object(verify_release_ready, "_enregistrer") as register:
                self.assertTrue(verify_release_ready.step_cs2cd_fixtures())

        register.assert_called_once()
        self.assertEqual(register.call_args.args[2], "SKIP")


if __name__ == "__main__":
    unittest.main(verbosity=2)
