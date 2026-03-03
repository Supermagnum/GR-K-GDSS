# SPDX-License-Identifier: GPL-3.0-or-later
"""
T3 - Key derivation (Python) tests: HKDF, nonce construction, keyring round-trip.
"""

import unittest
import os

try:
    from gnuradio.kgdss import (
        derive_session_keys,
        store_session_keys,
        load_gdss_key,
        gdss_nonce,
        payload_nonce,
        keyring_available,
        keyring_import_error,
    )
    T3_AVAILABLE = derive_session_keys is not None and gdss_nonce is not None and payload_nonce is not None
except ImportError:
    T3_AVAILABLE = False
    keyring_available = None
    keyring_import_error = None



@unittest.skipUnless(T3_AVAILABLE, "gnuradio.kgdss session_key_derivation not available")
class TestT3OutputLength(unittest.TestCase):
    """derive_session_keys returns exactly four keys, each 32 bytes."""

    def test_output_length(self):
        secret = os.urandom(32)
        keys = derive_session_keys(secret)
        self.assertEqual(len(keys), 4)
        self.assertIn("payload_enc", keys)
        self.assertIn("gdss_masking", keys)
        self.assertIn("sync_pn", keys)
        self.assertIn("sync_timing", keys)
        for k, v in keys.items():
            self.assertEqual(len(v), 32, f"key {k} length")


@unittest.skipUnless(T3_AVAILABLE, "session_key_derivation not available")
class TestT3DomainSeparation(unittest.TestCase):
    """All four derived keys are different."""

    def test_domain_separation(self):
        secret = os.urandom(32)
        keys = derive_session_keys(secret)
        vals = list(keys.values())
        for i in range(len(vals)):
            for j in range(i + 1, len(vals)):
                self.assertNotEqual(vals[i], vals[j])


@unittest.skipUnless(T3_AVAILABLE, "session_key_derivation not available")
class TestT3Determinism(unittest.TestCase):
    """Same shared secret and salt -> identical keys every time."""

    def test_determinism(self):
        secret = os.urandom(32)
        salt = os.urandom(32)
        a = derive_session_keys(secret, salt=salt)
        b = derive_session_keys(secret, salt=salt)
        for name in a:
            self.assertEqual(a[name], b[name])


@unittest.skipUnless(T3_AVAILABLE, "session_key_derivation not available")
class TestT3InputSensitivity(unittest.TestCase):
    """Changing one byte of shared secret -> all four keys different."""

    def test_input_sensitivity(self):
        secret = os.urandom(32)
        keys_a = derive_session_keys(secret)
        secret_modified = bytearray(secret)
        secret_modified[0] ^= 1
        keys_b = derive_session_keys(bytes(secret_modified))
        for name in keys_a:
            self.assertNotEqual(keys_a[name], keys_b[name])


@unittest.skipUnless(T3_AVAILABLE, "session_key_derivation not available")
class TestT3NonceConstruction(unittest.TestCase):
    """gdss_nonce and payload_nonce return 12 bytes; different tx_seq -> different nonces."""

    def test_gdss_nonce_length(self):
        n = gdss_nonce(0, 1)
        self.assertEqual(len(n), 12)

    def test_payload_nonce_length(self):
        n = payload_nonce(0, 1)
        self.assertEqual(len(n), 12)

    def test_different_tx_seq_different_nonce(self):
        n1 = gdss_nonce(0, 1)
        n2 = gdss_nonce(0, 2)
        self.assertNotEqual(n1, n2)

    def test_session_tx_seq_collision_avoidance(self):
        """Session 0 tx_seq 1 != session 1 tx_seq 0."""
        n_a = gdss_nonce(0, 1)
        n_b = gdss_nonce(1, 0)
        self.assertNotEqual(n_a, n_b)


def _keyring_skip_reason():
    if not T3_AVAILABLE or keyring_available is None:
        return "session_key_derivation not available"
    if keyring_available():
        return None
    err = keyring_import_error() if callable(keyring_import_error) else "keyring not available"
    return "Linux keyring: {}".format(err)


@unittest.skipUnless(
    T3_AVAILABLE and keyring_available is not None and keyring_available(),
    _keyring_skip_reason() or "keyring not available",
)
class TestT3KeyringRoundTrip(unittest.TestCase):
    """Store key via store_session_keys, retrieve via load_gdss_key -> bytes identical."""

    def test_keyring_round_trip(self):
        secret = os.urandom(32)
        keys = derive_session_keys(secret)
        ids = store_session_keys(keys)
        self.assertIn("gdss_masking", ids)
        key_id = ids["gdss_masking"]
        key_id_int = int(key_id) if not isinstance(key_id, int) else key_id
        try:
            loaded = load_gdss_key(key_id_int)
        except RuntimeError as e:
            msg = str(e).lower()
            if "permission" in msg or "keyctl" in msg or "denied" in msg:
                self.skipTest("keyctl read not allowed in this environment: {}".format(e))
            raise
        self.assertEqual(loaded, keys["gdss_masking"])


if __name__ == "__main__":
    unittest.main()
