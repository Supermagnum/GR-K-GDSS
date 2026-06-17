# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for RX flywheel controller wiring."""

import sys
import unittest
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "python") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "python"))

from sync_burst_rx import SyncBurstRxController  # type: ignore
from sync_burst_utils import derive_sync_schedule  # type: ignore


def _keys():
    timing = bytes((i * 7 + 13) % 256 for i in range(32))
    pn = bytes((i * 11 + 29) % 256 for i in range(32))
    return timing, pn


class TestSyncBurstRxController(unittest.TestCase):
    def test_schedule_matches_derive_sync_schedule(self):
        timing, pn = _keys()
        ctrl = SyncBurstRxController(timing, pn, session_id=5, sample_rate_hz=500_000.0, n_bursts=6)
        expected = derive_sync_schedule(timing, 5, session_duration_s=900.0, n_bursts=6)
        self.assertEqual(ctrl.epochs_ms, expected)
        self.assertEqual(len(ctrl.amplitude_scales), len(expected))

    def test_tick_samples_closes_window_on_miss(self):
        timing, pn = _keys()
        ctrl = SyncBurstRxController(
            timing,
            pn,
            session_id=1,
            sample_rate_hz=1_000_000.0,
            n_bursts=3,
            mean_interval_s=1.0,
            min_interval_s=0.001,
        )
        first = ctrl.epochs_ms[0]
        half_ms = ctrl.current_target().search_window_half_width_s * 1000.0
        end_ms = first + half_ms
        samples_at_end = int(end_ms * 1000.0)
        ctrl.tick_samples(samples_at_end - 1)
        self.assertEqual(ctrl.flywheel.current_epoch_index, 0)
        ctrl.tick_samples(1)
        self.assertEqual(ctrl.flywheel.current_epoch_index, 1)

    def test_detection_advances_and_provides_pn(self):
        timing, pn = _keys()
        ctrl = SyncBurstRxController(
            timing,
            pn,
            session_id=2,
            sample_rate_hz=1000.0,
            n_bursts=2,
            mean_interval_s=1.0,
            min_interval_s=0.001,
        )
        epoch = ctrl.epochs_ms[0]
        ctrl.notify_burst_detected(timestamp_ms=epoch)
        self.assertEqual(ctrl.flywheel.current_epoch_index, 1)
        seq = ctrl.current_pn_sequence(chips=256)
        self.assertIsNotNone(seq)
        self.assertEqual(seq.shape[0], 256)

    def test_amplitude_scale_length_matches_schedule(self):
        timing, pn = _keys()
        ctrl = SyncBurstRxController(timing, pn, session_id=3, sample_rate_hz=1_000_000.0)
        self.assertEqual(len(ctrl.amplitude_scales), len(ctrl.epochs_ms))


if __name__ == "__main__":
    unittest.main()
