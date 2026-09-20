"""
Unit tests for ReplayWatcher and 3-step debounce verification.
"""

import os
import shutil
import tempfile
import threading
import time
import unittest

from src.core.models import ReplayInfo
from src.core.watcher import ReplayWatcher, is_demo_write_complete


class TestReplayWatcher(unittest.TestCase):
    """Tests for ReplayWatcher lifecycle, debouncing, and event handling."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="cs2_watcher_test_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_is_demo_write_complete_valid_header(self):
        valid_demo = os.path.join(self.temp_dir, "valid.dem")
        with open(valid_demo, "wb") as f:
            f.write(b"PBDEMS2\x00" + b"\x00" * 256)

        self.assertTrue(
            is_demo_write_complete(
                valid_demo,
                poll_interval=0.05,
                stability_checks=2,
                timeout=2.0,
                min_size=8,
            )
        )

    def test_is_demo_write_complete_invalid_header(self):
        bad_demo = os.path.join(self.temp_dir, "corrupt.dem")
        with open(bad_demo, "wb") as f:
            f.write(b"BADMAGIC" + b"\x00" * 256)

        self.assertFalse(
            is_demo_write_complete(
                bad_demo,
                poll_interval=0.05,
                stability_checks=2,
                timeout=0.3,
                min_size=8,
            )
        )

    def test_is_demo_write_complete_nonexistent(self):
        missing = os.path.join(self.temp_dir, "missing.dem")
        self.assertFalse(
            is_demo_write_complete(missing, poll_interval=0.05, timeout=0.2)
        )

    def test_is_demo_write_complete_incremental_growth(self):
        growth_file = os.path.join(self.temp_dir, "growth.dem")

        # Initial partial write
        with open(growth_file, "wb") as f:
            f.write(b"PBDEMS2\x00")

        def append_data():
            for _ in range(3):
                time.sleep(0.08)
                try:
                    with open(growth_file, "ab") as f:
                        f.write(b"\x00" * 64)
                except OSError:
                    pass

        writer_thread = threading.Thread(target=append_data, daemon=True)
        writer_thread.start()

        # Should wait through growing file size and complete once stable
        result = is_demo_write_complete(
            growth_file,
            poll_interval=0.05,
            stability_checks=2,
            timeout=3.0,
            min_size=8,
        )
        writer_thread.join()
        self.assertTrue(result)

    def test_watcher_lifecycle_start_stop(self):
        received = []
        watcher = ReplayWatcher(
            target_dir=self.temp_dir,
            on_new_replay_callback=received.append,
            debounce_interval=0.05,
            stability_checks=2,
            timeout=1.0,
        )

        self.assertFalse(watcher.is_running())

        watcher.start()
        self.assertTrue(watcher.is_running())

        # Idempotent start call
        watcher.start()
        self.assertTrue(watcher.is_running())

        watcher.stop()
        self.assertFalse(watcher.is_running())

        # Idempotent stop call
        watcher.stop()
        self.assertFalse(watcher.is_running())

    def test_watcher_detects_new_replay(self):
        received = []
        event_trigger = threading.Event()

        def on_replay(info: ReplayInfo):
            received.append(info)
            event_trigger.set()

        watcher = ReplayWatcher(
            target_dir=self.temp_dir,
            on_new_replay_callback=on_replay,
            debounce_interval=0.05,
            stability_checks=2,
            timeout=2.0,
        )
        watcher.start()

        try:
            # Write a demo matching CS2 naming convention
            demo_name = "match730_de_ancient.dem"
            demo_path = os.path.join(self.temp_dir, demo_name)

            with open(demo_path, "wb") as f:
                f.write(b"PBDEMS2\x00" + b"\x00" * 512)

            # Wait for watcher notification
            signaled = event_trigger.wait(timeout=4.0)
            self.assertTrue(signaled, "Watcher did not signal new replay within timeout")
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0].file_name, demo_name)
            self.assertEqual(received[0].map_name, "de_ancient")
            self.assertGreater(received[0].file_size_bytes, 8)
        finally:
            watcher.stop()

    def test_watcher_ignores_non_dem_files(self):
        received = []
        watcher = ReplayWatcher(
            target_dir=self.temp_dir,
            on_new_replay_callback=received.append,
            debounce_interval=0.05,
            stability_checks=2,
            timeout=1.0,
        )
        watcher.start()

        try:
            # Create non-dem files
            with open(os.path.join(self.temp_dir, "match.dem.info"), "wb") as f:
                f.write(b"metadata")
            with open(os.path.join(self.temp_dir, "log.txt"), "w") as f:
                f.write("text log")

            time.sleep(0.5)
            self.assertEqual(len(received), 0)
        finally:
            watcher.stop()

    def test_watcher_callback_exception_handling(self):
        call_count = [0]
        second_called = threading.Event()

        def faulty_callback(info: ReplayInfo):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Consumer error should not crash watcher")
            else:
                second_called.set()

        watcher = ReplayWatcher(
            target_dir=self.temp_dir,
            on_new_replay_callback=faulty_callback,
            debounce_interval=0.05,
            stability_checks=2,
            timeout=2.0,
        )
        watcher.start()

        try:
            # First file causes callback to raise
            demo1 = os.path.join(self.temp_dir, "first.dem")
            with open(demo1, "wb") as f:
                f.write(b"PBDEMS2\x00" + b"\x00" * 128)

            time.sleep(0.4)
            self.assertTrue(watcher.is_running())

            # Second file should still be processed
            demo2 = os.path.join(self.temp_dir, "second.dem")
            with open(demo2, "wb") as f:
                f.write(b"PBDEMS2\x00" + b"\x00" * 128)

            signaled = second_called.wait(timeout=3.0)
            self.assertTrue(signaled)
            self.assertEqual(call_count[0], 2)
        finally:
            watcher.stop()


if __name__ == "__main__":
    unittest.main()
