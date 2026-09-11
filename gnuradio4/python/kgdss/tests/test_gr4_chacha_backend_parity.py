# SPDX-License-Identifier: GPL-3.0-or-later
"""
ChaCha20 IETF backend parity for gnuradio4/python/kgdss/sync_burst_utils.py.

Top-level tests/test_chacha_backend_parity.py only imports the top-level copy.
Unique basename avoids pytest import-file mismatch when both suites run together.
"""

from __future__ import annotations

import unittest

import numpy as np

from _load_gr4 import load_gr4_kgdss_module

_sbu = load_gr4_kgdss_module("sync_burst_utils")


def _load_chacha_via_pycryptodome():
    try:
        from Crypto.Cipher import ChaCha20 as C
    except ImportError:
        try:
            from Cryptodome.Cipher import ChaCha20 as C
        except ImportError:
            return None
    return C


def _load_chacha_via_cryptography():
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        return None

    class Wrapper:
        def __init__(self, key: bytes, nonce: bytes):
            if len(nonce) != 12:
                raise ValueError("expected 12-byte IETF nonce")
            nonce_16 = (0).to_bytes(4, "little") + nonce
            self._cipher = Cipher(
                algorithms.ChaCha20(key, nonce_16),
                mode=None,
                backend=default_backend(),
            )

        def encrypt(self, data: bytes) -> bytes:
            encryptor = self._cipher.encryptor()
            return encryptor.update(data) + encryptor.finalize()

    class Facade:
        @staticmethod
        def new(key: bytes, nonce: bytes):
            return Wrapper(key, nonce)

    return Facade


def _buggy_cryptography_pad(key: bytes, nonce: bytes, n: int) -> bytes:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
    from cryptography.hazmat.backends import default_backend

    nonce_16 = (nonce + b"\x00" * 16)[:16]
    enc = Cipher(
        algorithms.ChaCha20(key, nonce_16), mode=None, backend=default_backend()
    ).encryptor()
    return enc.update(b"\x00" * n) + enc.finalize()


class TestGr4ChaChaIetfBackendParity(unittest.TestCase):
    KEY = bytes(range(32))
    NONCE = bytes(range(12))
    N = 512

    def test_gr4_sync_burst_utils_matches_ietf_reference(self):
        ref = _load_chacha_via_pycryptodome() or _load_chacha_via_cryptography()
        if ref is None:
            self.skipTest("no ChaCha20 backend available for reference")
        a = _sbu.ChaCha20.new(key=self.KEY, nonce=self.NONCE).encrypt(
            b"\x00" * self.N
        )
        b = ref.new(key=self.KEY, nonce=self.NONCE).encrypt(b"\x00" * self.N)
        self.assertEqual(a, b)

        burst = np.ones(32, dtype=np.complex64)
        out = _sbu.apply_keyed_gaussian_mask(
            burst, self.KEY, self.NONCE, variance=1.0
        )
        self.assertEqual(out.dtype, np.complex64)
        self.assertEqual(len(out), 32)

    def test_trailing_zero_pad_does_not_match_gr4_backend(self):
        try:
            import cryptography  # noqa: F401
        except ImportError:
            self.skipTest("cryptography not installed")
        good = _sbu.ChaCha20.new(key=self.KEY, nonce=self.NONCE).encrypt(
            b"\x00" * self.N
        )
        bad = _buggy_cryptography_pad(self.KEY, self.NONCE, self.N)
        self.assertNotEqual(good, bad)


if __name__ == "__main__":
    unittest.main()
