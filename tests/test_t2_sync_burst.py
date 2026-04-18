# SPDX-License-Identifier: GPL-3.0-or-later
"""
T2 - Sync burst (Python) tests: PN sequence, timing schedule, Gaussian envelope.
"""

import unittest
import os

import numpy as np

try:
    from gnuradio.kgdss import (
        derive_sync_schedule as _derive_sync_schedule,
        derive_sync_pn_sequence as _derive_sync_pn_sequence,
        gaussian_envelope as _gaussian_envelope,
        apply_keyed_gaussian_mask as _apply_keyed_gaussian_mask,
        gdss_sync_burst_nonce as _gdss_sync_burst_nonce,
    )

    # In development environments, the installed module may lag behind the source tree.
    # If the installed API does not support the multi-burst schedule and per-burst PN
    # parameters, fall back to importing directly from the repository `python/` tree.
    import inspect
    import sys
    from pathlib import Path

    _have_new_pn = "burst_index" in inspect.signature(_derive_sync_pn_sequence).parameters
    _have_new_schedule = "session_duration_s" in inspect.signature(_derive_sync_schedule).parameters

    if not (_have_new_pn and _have_new_schedule):
        repo_root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(repo_root / "python"))
        from sync_burst_utils import (  # type: ignore
            derive_sync_schedule as _derive_sync_schedule,
            derive_sync_pn_sequence as _derive_sync_pn_sequence,
            gaussian_envelope as _gaussian_envelope,
            apply_keyed_gaussian_mask as _apply_keyed_gaussian_mask,
        )
        try:
            from session_key_derivation import gdss_sync_burst_nonce as _gdss_sync_burst_nonce  # type: ignore
        except Exception:
            _gdss_sync_burst_nonce = None

    derive_sync_schedule = _derive_sync_schedule
    derive_sync_pn_sequence = _derive_sync_pn_sequence
    gaussian_envelope = _gaussian_envelope
    apply_keyed_gaussian_mask = _apply_keyed_gaussian_mask
    gdss_sync_burst_nonce = _gdss_sync_burst_nonce

    T2_AVAILABLE = derive_sync_schedule is not None and derive_sync_pn_sequence is not None and gaussian_envelope is not None
    T2_MASK_AVAILABLE = T2_AVAILABLE and apply_keyed_gaussian_mask is not None and gdss_sync_burst_nonce is not None
except ImportError:
    T2_AVAILABLE = False
    T2_MASK_AVAILABLE = False


@unittest.skipUnless(T2_AVAILABLE, "gnuradio.kgdss sync_burst_utils not available")
class TestT2PNDeterminism(unittest.TestCase):
    """derive_sync_pn_sequence twice with same inputs -> identical arrays."""

    def test_pn_determinism(self):
        key = os.urandom(32)
        session_id = 1
        chips = 5000
        a = derive_sync_pn_sequence(key, session_id, chips, burst_index=0)
        b = derive_sync_pn_sequence(key, session_id, chips, burst_index=0)
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
    """derive_sync_schedule twice, same key/session_id -> same schedule."""

    def test_timing_determinism(self):
        key = os.urandom(32)
        session_id = 42
        a = derive_sync_schedule(key, session_id, session_duration_s=300.0, n_bursts=10)
        b = derive_sync_schedule(key, session_id, session_duration_s=300.0, n_bursts=10)
        self.assertEqual(a, b)


@unittest.skipUnless(T2_AVAILABLE, "sync_burst_utils not available")
class TestT2TimingScheduleRange(unittest.TestCase):
    """All burst epochs are within [0, session_duration)."""

    def test_schedule_range(self):
        key = os.urandom(32)
        duration_s = 120.0
        epochs = derive_sync_schedule(key, 1, session_duration_s=duration_s, n_bursts=20)
        for t in epochs:
            self.assertGreater(t, 0)
            self.assertLess(t, int(duration_s * 1000))


@unittest.skipUnless(T2_AVAILABLE, "sync_burst_utils not available")
class TestT2TimingScheduleProperties(unittest.TestCase):
    """Schedule is ordered, unique, and non-degenerate."""

    def test_schedule_properties(self):
        # The schedule API is "best-effort": with a heavy-tailed Pareto cadence,
        # rare keys produce early large intervals that exhaust the session
        # budget before n_bursts are placed. Use parameters whose expected
        # cumulative time fits well inside session_duration_s so the structural
        # checks below see enough epochs across all keys, and sample several
        # independent keys so the test does not depend on a single draw.
        rng = np.random.default_rng(0xC0FFEE)
        for _ in range(16):
            key = bytes(rng.integers(0, 256, size=32, dtype=np.uint8).tolist())
            epochs = derive_sync_schedule(
                key,
                1,
                session_duration_s=600.0,
                n_bursts=10,
                mean_interval_s=20.0,
            )
            self.assertGreaterEqual(len(epochs), 3, "schedule should contain bursts")
            self.assertEqual(sorted(epochs), epochs, "epochs must be ordered")
            self.assertEqual(len(set(epochs)), len(epochs), "no collisions")
            # Heavy-tailed cadence should have some variability (not constant).
            intervals = np.diff(np.array(epochs, dtype=np.int64))
            self.assertGreater(
                np.max(intervals), np.min(intervals), "non-uniform intervals expected"
            )


@unittest.skipUnless(T2_AVAILABLE, "sync_burst_utils not available")
class TestT2PerBurstPNUniqueness(unittest.TestCase):
    """Per-burst PN changes with burst_index; burst_index=0 matches legacy call."""

    def test_pn_uniqueness(self):
        key = os.urandom(32)
        session_id = 7
        chips = 4096
        pn0 = derive_sync_pn_sequence(key, session_id, chips, burst_index=0)
        pn1 = derive_sync_pn_sequence(key, session_id, chips, burst_index=1)
        self.assertFalse(np.array_equal(pn0, pn1))

    def test_pn_backward_compatible_default(self):
        key = os.urandom(32)
        session_id = 7
        chips = 2048
        pn_default = derive_sync_pn_sequence(key, session_id, chips)
        pn0 = derive_sync_pn_sequence(key, session_id, chips, burst_index=0)
        np.testing.assert_array_equal(pn_default, pn0)


@unittest.skipUnless(T2_AVAILABLE, "sync_burst_utils not available")
class TestT2GaussianEnvelope(unittest.TestCase):
    """Constant-amplitude burst: first/last near zero, centre near original, monotonic."""

    def test_gaussian_envelope_shape(self):
        n = 100
        rise_frac = 0.15
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


@unittest.skipUnless(T2_MASK_AVAILABLE, "apply_keyed_gaussian_mask / gdss_sync_burst_nonce not available")
class TestT2KeyedGaussianMask(unittest.TestCase):
    """apply_keyed_gaussian_mask: same key/nonce/burst -> identical output; shape preserved."""

    def test_mask_determinism(self):
        key = os.urandom(32)
        nonce = os.urandom(12)
        burst = (np.random.randn(200) + 1j * np.random.randn(200)).astype(np.complex64)
        a = apply_keyed_gaussian_mask(burst, key, nonce)
        b = apply_keyed_gaussian_mask(burst, key, nonce)
        np.testing.assert_array_almost_equal(a, b)

    def test_mask_shape(self):
        key = os.urandom(32)
        nonce = gdss_sync_burst_nonce(1)
        burst = (np.ones(100) + 0.5j * np.ones(100)).astype(np.complex64)
        out = apply_keyed_gaussian_mask(burst, key, nonce)
        self.assertEqual(out.shape, burst.shape)
        self.assertEqual(out.dtype, np.complex64)

    def test_mask_different_nonce_different_output(self):
        key = os.urandom(32)
        burst = (np.ones(50) + 1j * np.ones(50)).astype(np.complex64)
        out1 = apply_keyed_gaussian_mask(burst, key, gdss_sync_burst_nonce(1))
        out2 = apply_keyed_gaussian_mask(burst, key, gdss_sync_burst_nonce(2))
        self.assertFalse(np.allclose(out1, out2))


@unittest.skipUnless(T2_MASK_AVAILABLE, "gdss_sync_burst_nonce not available")
class TestT2SyncBurstNonce(unittest.TestCase):
    """gdss_sync_burst_nonce returns 12 bytes; different session_id -> different nonce."""

    def test_sync_burst_nonce_length(self):
        n = gdss_sync_burst_nonce(1)
        self.assertEqual(len(n), 12)

    def test_sync_burst_nonce_per_session(self):
        n1 = gdss_sync_burst_nonce(1)
        n2 = gdss_sync_burst_nonce(2)
        self.assertNotEqual(n1, n2)
