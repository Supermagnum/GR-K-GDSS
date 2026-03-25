# SPDX-License-Identifier: GPL-3.0-or-later
"""
P.372 receiver profile integration tests.
"""

import unittest
import numpy as np

try:
    from gnuradio.kgdss import (
        load_p372_params,
        p372_expected_psd_profile_dbm_per_hz,
        calibrate_p372_profile_to_measured_psd,
    )
except ImportError:
    load_p372_params = None
    p372_expected_psd_profile_dbm_per_hz = None
    calibrate_p372_profile_to_measured_psd = None

if load_p372_params is None:
    # Source-tree fallback for development environments with older installed package.
    import sys
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "python"))
    from p372_baseline import load_p372_params  # type: ignore
    from p372_receiver_profile import (  # type: ignore
        p372_expected_psd_profile_dbm_per_hz,
        calibrate_p372_profile_to_measured_psd,
    )


@unittest.skipUnless(load_p372_params is not None, "P.372 helpers not available")
class TestP372BaselineLoader(unittest.TestCase):
    def test_load_is_deterministic(self):
        a = load_p372_params()
        b = load_p372_params()
        self.assertEqual(a, b)
        self.assertAlmostEqual(a.rise_fraction, 0.15, places=6)


@unittest.skipUnless(p372_expected_psd_profile_dbm_per_hz is not None, "P.372 receiver profile not available")
class TestP372ExpectedProfile(unittest.TestCase):
    def test_expected_profile_shape(self):
        bins = np.linspace(14_099_500, 14_100_500, 1024)
        prof = p372_expected_psd_profile_dbm_per_hz(
            bins,
            center_freq_hz=14_100_000,
            nominal_floor_dbm_per_hz=-150.0,
        )
        self.assertEqual(prof.shape, bins.shape)
        # finite and sane
        self.assertTrue(np.isfinite(prof).all())


@unittest.skipUnless(calibrate_p372_profile_to_measured_psd is not None, "P.372 calibration not available")
class TestP372Calibration(unittest.TestCase):
    def test_median_offset_calibration(self):
        bins = np.linspace(7_099_000, 7_101_000, 2048)
        expected = p372_expected_psd_profile_dbm_per_hz(
            bins,
            center_freq_hz=7_100_000,
            nominal_floor_dbm_per_hz=-160.0,
        )
        measured = expected + 6.5
        out = calibrate_p372_profile_to_measured_psd(
            bins,
            measured,
            center_freq_hz=7_100_000,
            nominal_floor_dbm_per_hz=-160.0,
        )
        self.assertAlmostEqual(out.calibration_offset_db, 6.5, places=3)
        self.assertAlmostEqual(out.median_residual_db, 0.0, places=3)

