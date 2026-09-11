# SPDX-License-Identifier: GPL-3.0-or-later
"""
Per-burst sync-burst nonces via gnuradio4/python/kgdss (path-isolated import).
"""

from __future__ import annotations

import unittest

import numpy as np

from _load_gr4 import load_gr4_kgdss_module

_skd = load_gr4_kgdss_module("session_key_derivation")
_sbu = load_gr4_kgdss_module("sync_burst_utils")

gdss_sync_burst_nonce = _skd.gdss_sync_burst_nonce
apply_keyed_gaussian_mask = _sbu.apply_keyed_gaussian_mask
derive_sync_pn_sequence = _sbu.derive_sync_pn_sequence


class TestGr4SyncBurstNonce(unittest.TestCase):
    """Two bursts in one session must not share a sync-burst keystream."""

    def test_gdss_sync_burst_nonce_diverges_by_burst_index(self):
        n0 = gdss_sync_burst_nonce(1, burst_index=0)
        n1 = gdss_sync_burst_nonce(1, burst_index=1)
        self.assertEqual(len(n0), 12)
        self.assertEqual(len(n1), 12)
        self.assertNotEqual(n0, n1)
        self.assertEqual(n0, gdss_sync_burst_nonce(1))

    def test_masked_bursts_diverge_by_burst_index(self):
        key = bytes(range(32))
        burst = np.ones(64, dtype=np.complex64)
        out0 = apply_keyed_gaussian_mask(
            burst, key, gdss_sync_burst_nonce(42, burst_index=0), variance=1.0
        )
        out1 = apply_keyed_gaussian_mask(
            burst, key, gdss_sync_burst_nonce(42, burst_index=1), variance=1.0
        )
        self.assertFalse(np.allclose(out0, out1))

    def test_sync_pn_diverges_by_burst_index(self):
        key = bytes(range(32, 64))
        pn0 = derive_sync_pn_sequence(key, 7, 128, burst_index=0)
        pn1 = derive_sync_pn_sequence(key, 7, 128, burst_index=1)
        self.assertFalse(np.array_equal(pn0, pn1))


if __name__ == "__main__":
    unittest.main()
