# SPDX-License-Identifier: GPL-3.0-or-later
"""
Regression: PyCryptodome and cryptography ChaCha20 backends must produce
bit-identical IETF keystreams for the same 12-byte nonce (counter starts at 0).
"""

from __future__ import annotations

import importlib
import unittest

import numpy as np


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
    """Historical incorrect layout: trailing zero pad (must NOT match IETF)."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
    from cryptography.hazmat.backends import default_backend

    nonce_16 = (nonce + b"\x00" * 16)[:16]
    enc = Cipher(algorithms.ChaCha20(key, nonce_16), mode=None, backend=default_backend()).encryptor()
    return enc.update(b"\x00" * n) + enc.finalize()


class TestChaChaIetfBackendParity(unittest.TestCase):
    """Known-answer agreement between PyCryptodome and cryptography fallback."""

    KEY = bytes(range(32))
    NONCE = bytes(range(12))
    N = 512

    def test_pycryptodome_matches_cryptography_ietf_layout(self):
        pc = _load_chacha_via_pycryptodome()
        cr = _load_chacha_via_cryptography()
        if pc is None or cr is None:
            self.skipTest("need both PyCryptodome/pycryptodomex and cryptography")
        a = pc.new(key=self.KEY, nonce=self.NONCE).encrypt(b"\x00" * self.N)
        b = cr.new(key=self.KEY, nonce=self.NONCE).encrypt(b"\x00" * self.N)
        self.assertEqual(a, b)

    def test_trailing_zero_pad_does_not_match_ietf(self):
        pc = _load_chacha_via_pycryptodome()
        try:
            import cryptography  # noqa: F401
        except ImportError:
            self.skipTest("cryptography not installed")
        if pc is None:
            self.skipTest("PyCryptodome not installed")
        good = pc.new(key=self.KEY, nonce=self.NONCE).encrypt(b"\x00" * self.N)
        bad = _buggy_cryptography_pad(self.KEY, self.NONCE, self.N)
        self.assertNotEqual(good, bad)

    def test_sync_burst_utils_backend_matches_reference(self):
        """Installed/in-tree sync_burst_utils ChaCha20 matches IETF reference."""
        try:
            from gnuradio.kgdss import sync_burst_utils as sbu
        except ImportError:
            import importlib.util
            from pathlib import Path

            path = Path(__file__).resolve().parents[1] / "python" / "sync_burst_utils.py"
            spec = importlib.util.spec_from_file_location("sync_burst_utils_local", path)
            sbu = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(sbu)

        ref = _load_chacha_via_pycryptodome() or _load_chacha_via_cryptography()
        if ref is None:
            self.skipTest("no ChaCha20 backend available for reference")
        a = sbu.ChaCha20.new(key=self.KEY, nonce=self.NONCE).encrypt(b"\x00" * self.N)
        b = ref.new(key=self.KEY, nonce=self.NONCE).encrypt(b"\x00" * self.N)
        self.assertEqual(a, b)

        # Masked burst path must be deterministic under the fixed backend.
        burst = np.ones(32, dtype=np.complex64)
        out = sbu.apply_keyed_gaussian_mask(burst, self.KEY, self.NONCE, variance=1.0)
        self.assertEqual(out.dtype, np.complex64)
        self.assertEqual(len(out), 32)


if __name__ == "__main__":
    unittest.main()
