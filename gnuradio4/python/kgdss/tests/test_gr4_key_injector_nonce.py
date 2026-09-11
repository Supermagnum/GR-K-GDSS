# SPDX-License-Identifier: GPL-3.0-or-later
"""
GR4 KeyInjector nonce policy — exercises gnuradio4/python/kgdss/key_injector.py
(diverged from top-level python/key_injector.py).
"""

from __future__ import annotations

import os
import tempfile
import unittest

from _load_gr4 import load_gr4_kgdss_module

_skd = load_gr4_kgdss_module("session_key_derivation")
_ki = load_gr4_kgdss_module("key_injector")

KeyInjector = _ki.KeyInjector
allocate_gdss_nonce_counters = _skd.allocate_gdss_nonce_counters
derive_session_keys = _skd.derive_session_keys
gdss_nonce = _skd.gdss_nonce
reserve_gdss_nonce_counters = _skd.reserve_gdss_nonce_counters


class TestGr4KeyInjectorNoncePolicy(unittest.TestCase):
    """GR4 KeyInjector must allocate persisted counters and refuse tx_seq=0."""

    def test_rejects_tx_seq_zero_without_ack(self):
        secret = bytes(range(32, 64))
        with self.assertRaises(ValueError) as ctx:
            KeyInjector(shared_secret=secret, session_id=1, tx_seq=0)
        self.assertIn("allow_static_nonce", str(ctx.exception))

    def test_auto_allocate_diverges_across_constructors(self):
        secret = bytes(range(64, 96))
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "nonce_counters.json")
            a = KeyInjector(
                shared_secret=secret, session_id=1, nonce_state_path=state
            )
            b = KeyInjector(
                shared_secret=secret, session_id=1, nonce_state_path=state
            )
            self.assertTrue(a.ready and b.ready)
            self.assertNotEqual(
                (a._session_id, a._tx_seq), (b._session_id, b._tx_seq)
            )
            self.assertNotEqual(a.to_dict()["nonce"], b.to_dict()["nonce"])

    def test_allocate_helper_advances_and_diverges(self):
        secret = bytes(range(32))
        masking = derive_session_keys(secret)["gdss_masking"]
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "nonce_counters.json")
            sid_a, tx_a = allocate_gdss_nonce_counters(masking, state_path=state)
            sid_b, tx_b = allocate_gdss_nonce_counters(masking, state_path=state)
            self.assertNotEqual((sid_a, tx_a), (sid_b, tx_b))
            self.assertNotEqual(gdss_nonce(sid_a, tx_a), gdss_nonce(sid_b, tx_b))

    def test_reserve_refuses_reuse(self):
        secret = os.urandom(32)
        masking = derive_session_keys(secret)["gdss_masking"]
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "nonce_counters.json")
            reserve_gdss_nonce_counters(masking, 7, 3, state_path=state)
            with self.assertRaises(ValueError):
                reserve_gdss_nonce_counters(masking, 7, 3, state_path=state)


if __name__ == "__main__":
    unittest.main()
