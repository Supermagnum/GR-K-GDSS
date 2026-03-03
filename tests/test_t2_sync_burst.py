# SPDX-License-Identifier: GPL-3.0-or-later
"""
T2 - Sync burst (Python) tests: PN sequence, timing schedule, Gaussian envelope.
"""

import unittest
import os

import numpy as np

try:
    from gnuradio.kgdss import (
        derive_sync_schedule,
        derive_sync_pn_sequence,
        gaussian_envelope,
    )
    T2_AVAILABLE = (
        derive_sync_schedule is not None
        and derive_sync_pn_sequence is not None
        and gaussian_envelope is not None
    )
except ImportError:
    T2_AVAILABLE = False


@unittest.skipUnless(T2_AVAILABLE, "gnuradio.kgdss sync_burst_utils not available")
class TestT2PNDeterminism(unittest.TestCase):
    """derive_sync_pn_sequence twice with same inputs -> identical arrays."""

    def test_pn_determinism(self):
        key = os.urandom(32)
        session_id = 1
        chips = 5000
        a = derive_sync_pn_sequence(key, session_id, chips)
        b = derive_sync_pn_sequence(key, session_id, chips)
        np.testing.assert_array_equal(a, b)


@unittest.skipUnless(T2_AVAILABLE, "sync_burst_utils not available")
class TestT2PNKeySensitivity(unittest.TestCase):
    """Different master key -> different PN sequence."""

    def test_pn_key_sensitivity(self):
        key_a = os.urandom(32)
        key_b = os.urandom(32)
        a = derive_sync_pn_sequence(key_a, 1, 1000)
        b = derive_sync_pn_sequence(key_b, 1, 1000)
        self.assertFalse(np.array_equal(a, b))


@unittest.skipUnless(T2_AVAILABLE, "sync_burst_utils not available")
class TestT2PNBalance(unittest.TestCase):
    """PN sequence has roughly equal +1 and -1 (within statistical tolerance)."""

    def test_pn_balance(self):
        key = os.urandom(32)
        seq = derive_sync_pn_sequence(key, 1, chips=10000)
        n_pos = np.sum(seq > 0)
        n_neg = np.sum(seq < 0)
        self.assertGreaterEqual(n_pos, 4500, "roughly half +1")
        self.assertGreaterEqual(n_neg, 4500, "roughly half -1")


@unittest.skipUnless(T2_AVAILABLE, "sync_burst_utils not available")
class TestT2TimingOffsetDeterminism(unittest.TestCase):
    """derive_sync_schedule twice, same key/session_id -> same offset for same epoch."""

    def test_timing_determinism(self):
        key = os.urandom(32)
        session_id = 42
        get_offset_a = derive_sync_schedule(key, session_id, window_ms=50)
        get_offset_b = derive_sync_schedule(key, session_id, window_ms=50)
        for epoch in [0, 100, 1000]:
            self.assertEqual(get_offset_a(epoch), get_offset_b(epoch))


@unittest.skipUnless(T2_AVAILABLE, "sync_burst_utils not available")
class TestT2TimingOffsetRange(unittest.TestCase):
    """For window_ms=50, all offsets in [-50, +50]."""

    def test_timing_offset_range(self):
        key = os.urandom(32)
        get_offset = derive_sync_schedule(key, 1, window_ms=50)
        for _ in range(200):
            offset = get_offset(np.random.randint(0, 1000000))
            self.assertGreaterEqual(offset, -50)
            self.assertLessEqual(offset, 50)


@unittest.skipUnless(T2_AVAILABLE, "sync_burst_utils not available")
class TestT2TimingOffsetDistribution(unittest.TestCase):
    """1000 offsets across epochs roughly uniform over the window."""

    def test_timing_offset_distribution(self):
        key = os.urandom(32)
        get_offset = derive_sync_schedule(key, 1, window_ms=50)
        offsets = [get_offset(epoch) for epoch in range(1000)]
        hist, _ = np.histogram(offsets, bins=11, range=(-50, 51))
        min_bin = np.min(hist)
        self.assertGreater(min_bin, 20, "no large gap in distribution")


@unittest.skipUnless(T2_AVAILABLE, "sync_burst_utils not available")
class TestT2GaussianEnvelope(unittest.TestCase):
    """Constant-amplitude burst: first/last near zero, centre near original, monotonic."""

    def test_gaussian_envelope_shape(self):
        n = 100
        rise_frac = 0.1
        burst = np.ones(n, dtype=np.float32) * 2.0
        out = gaussian_envelope(burst, rise_fraction=rise_frac)
        flank = int(n * rise_frac)
        self.assertAlmostEqual(out[0], 0.0, delta=0.1)
        self.assertAlmostEqual(out[-1], 0.0, delta=0.1)
        self.assertGreater(out[flank], 1.5)
        self.assertGreater(out[n - 1 - flank], 1.5)
        for i in range(1, flank):
            self.assertGreaterEqual(out[i], out[i - 1])
        # Right flank: envelope falls from centre to end (descending)
        for i in range(n - flank, n - 1):
            self.assertGreaterEqual(out[i], out[i + 1])
