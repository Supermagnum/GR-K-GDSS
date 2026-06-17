# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit tests for silent sync burst flywheel tracking.
"""

import io
import os
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "python") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "python"))

from sync_flywheel import FlywheelTarget, SyncBurstFlywheel  # type: ignore


def _make_flywheel(
    epochs_ms,
    *,
    search_window_initial_s=0.05,
    window_widen_factor=1.5,
    window_max_s=2.0,
    max_consecutive_misses=5,
) -> SyncBurstFlywheel:
    return SyncBurstFlywheel(
        epochs_ms,
        search_window_initial_s=search_window_initial_s,
        window_widen_factor=window_widen_factor,
        window_max_s=window_max_s,
        max_consecutive_misses=max_consecutive_misses,
    )


class TestSyncFlywheelAllDetected(unittest.TestCase):
    def test_index_advances_and_window_stays_initial(self):
        epochs = [1000, 2000, 3000]
        fw = _make_flywheel(epochs, search_window_initial_s=0.05)
        self.assertEqual(fw.current_target().predicted_epoch_ms, 1000)
        self.assertAlmostEqual(fw.current_target().search_window_half_width_s, 0.05)

        fw.on_burst_detected(1000)
        self.assertEqual(fw.current_epoch_index, 1)
        self.assertEqual(fw.consecutive_misses, 0)
        self.assertAlmostEqual(fw.current_target().search_window_half_width_s, 0.05)

        fw.on_burst_detected(2000)
        fw.on_burst_detected(3000)
        self.assertEqual(fw.current_epoch_index, 3)
        self.assertIsNone(fw.current_target())


class TestSyncFlywheelConsecutiveMisses(unittest.TestCase):
    def test_window_widens_and_index_advances(self):
        epochs = [1000, 2000, 3000]
        fw = _make_flywheel(epochs, search_window_initial_s=0.05, window_widen_factor=2.0)

        t0 = fw.current_target()
        self.assertEqual(t0.epoch_index, 0)
        self.assertAlmostEqual(t0.search_window_half_width_s, 0.05)

        # Window for epoch 0 ends at 1000 + 50 = 1050 ms
        nxt = fw.on_epoch_elapsed(1050)
        self.assertEqual(fw.current_epoch_index, 1)
        self.assertEqual(fw.consecutive_misses, 1)
        self.assertAlmostEqual(fw.current_target().search_window_half_width_s, 0.10)

        # Miss epoch 1 as well (epoch 1 window half is 0.10 -> ends at 2100 ms)
        fw.on_epoch_elapsed(2101)
        self.assertEqual(fw.current_epoch_index, 2)
        self.assertEqual(fw.consecutive_misses, 2)
        self.assertAlmostEqual(fw.current_target().search_window_half_width_s, 0.20)


class TestSyncFlywheelDetectAfterMisses(unittest.TestCase):
    def test_miss_counter_resets_and_window_narrows(self):
        epochs = [1000, 2000, 3000]
        fw = _make_flywheel(epochs, search_window_initial_s=0.05, window_widen_factor=2.0)

        fw.on_epoch_elapsed(1050)
        self.assertEqual(fw.consecutive_misses, 1)
        self.assertAlmostEqual(fw.current_target().search_window_half_width_s, 0.10)

        fw.on_burst_detected(2000)
        self.assertEqual(fw.consecutive_misses, 0)
        self.assertEqual(fw.current_epoch_index, 2)
        self.assertAlmostEqual(fw.current_target().search_window_half_width_s, 0.05)


class TestSyncFlywheelColdStartReset(unittest.TestCase):
    def test_max_consecutive_misses_resets_without_exception(self):
        epochs = [1000, 2000, 3000, 4000]
        fw = _make_flywheel(
            epochs,
            search_window_initial_s=0.05,
            window_widen_factor=1.5,
            max_consecutive_misses=3,
        )

        fw.on_epoch_elapsed(1051)
        fw.on_epoch_elapsed(2076)
        fw.on_epoch_elapsed(3113)
        self.assertTrue(fw.in_cold_start)
        self.assertEqual(fw.consecutive_misses, 0)
        self.assertAlmostEqual(fw.current_target().search_window_half_width_s, 0.05)
        self.assertEqual(fw.current_epoch_index, 3)
        self.assertEqual(fw.current_target().predicted_epoch_ms, 4000)

    def test_no_diag_output_by_default(self):
        epochs = [1000, 2000]
        fw = _make_flywheel(epochs, max_consecutive_misses=1)
        buf = io.StringIO()
        with redirect_stderr(buf):
            fw.on_epoch_elapsed(1050)
            fw.on_epoch_elapsed(2050)
        self.assertEqual(buf.getvalue(), "")

    def test_diag_output_when_enabled(self):
        epochs = [1000, 2000]
        fw = _make_flywheel(epochs)
        old = os.environ.get("KGDSS_DIAG")
        os.environ["KGDSS_DIAG"] = "1"
        try:
            buf = io.StringIO()
            with redirect_stderr(buf):
                fw.on_epoch_elapsed(1050)
            out = buf.getvalue()
            self.assertIn("[kgdss-flywheel]", out)
            self.assertIn("missed epoch", out)
        finally:
            if old is None:
                os.environ.pop("KGDSS_DIAG", None)
            else:
                os.environ["KGDSS_DIAG"] = old


class TestSyncFlywheelEpochElapsedIdempotent(unittest.TestCase):
    def test_calling_before_window_end_does_not_advance(self):
        epochs = [1000]
        fw = _make_flywheel(epochs)
        before = fw.on_epoch_elapsed(500)
        self.assertEqual(before.epoch_index, 0)
        self.assertEqual(fw.current_epoch_index, 0)


if __name__ == "__main__":
    unittest.main()
