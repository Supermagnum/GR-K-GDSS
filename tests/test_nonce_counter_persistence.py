# SPDX-License-Identifier: GPL-3.0-or-later
"""
Regression: persisted GDSS nonce counters must not silently collide for the
same masking key across sessions / process restarts.
"""

from __future__ import annotations

import os
import tempfile
import unittest

try:
    from gnuradio.kgdss import (
        allocate_gdss_nonce_counters,
        derive_session_keys,
        gdss_nonce,
        key_injector,
        reserve_gdss_nonce_counters,
    )

    _HELPERS_OK = (
        allocate_gdss_nonce_counters is not None
        and derive_session_keys is not None
        and gdss_nonce is not None
        and reserve_gdss_nonce_counters is not None
    )
except ImportError:
    _HELPERS_OK = False
    allocate_gdss_nonce_counters = None
    derive_session_keys = None
    gdss_nonce = None
    key_injector = None
    reserve_gdss_nonce_counters = None


@unittest.skipUnless(_HELPERS_OK, "session_key_derivation nonce helpers not available")
class TestNonceCounterPersistence(unittest.TestCase):
    """Two sessions with the same shared secret must not reuse a nonce."""

    def test_allocate_advances_and_diverges(self):
        secret = bytes(range(32))
        masking = derive_session_keys(secret)["gdss_masking"]
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "nonce_counters.json")
            sid_a, tx_a = allocate_gdss_nonce_counters(masking, state_path=state)
            sid_b, tx_b = allocate_gdss_nonce_counters(masking, state_path=state)
            self.assertNotEqual((sid_a, tx_a), (sid_b, tx_b))
            nonce_a = gdss_nonce(sid_a, tx_a)
            nonce_b = gdss_nonce(sid_b, tx_b)
            self.assertNotEqual(nonce_a, nonce_b)
            self.assertEqual(len(nonce_a), 12)
            self.assertEqual(len(nonce_b), 12)

    def test_reserve_refuses_reuse(self):
        secret = os.urandom(32)
        masking = derive_session_keys(secret)["gdss_masking"]
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "nonce_counters.json")
            reserve_gdss_nonce_counters(masking, 7, 3, state_path=state)
            with self.assertRaises(ValueError):
                reserve_gdss_nonce_counters(masking, 7, 3, state_path=state)
            with self.assertRaises(ValueError):
                reserve_gdss_nonce_counters(masking, 7, 2, state_path=state)


@unittest.skipUnless(
    _HELPERS_OK and key_injector is not None,
    "key_injector / nonce helpers not available",
)
class TestKeyInjectorNoncePolicy(unittest.TestCase):
    """key_injector must not silently accept the unsafe tx_seq=0 default."""

    def test_rejects_tx_seq_zero_without_ack(self):
        secret = bytes(range(32, 64))
        with self.assertRaises(ValueError) as ctx:
            key_injector(shared_secret=secret, session_id=1, tx_seq=0)
        self.assertIn("allow_static_nonce", str(ctx.exception))

    def test_auto_allocate_diverges_across_constructors(self):
        secret = bytes(range(64, 96))
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "nonce_counters.json")
            a = key_injector(
                shared_secret=secret, session_id=1, nonce_state_path=state
            )
            b = key_injector(
                shared_secret=secret, session_id=1, nonce_state_path=state
            )
            self.assertNotEqual((a._session_id, a._tx_seq), (b._session_id, b._tx_seq))


if __name__ == "__main__":
    unittest.main()
