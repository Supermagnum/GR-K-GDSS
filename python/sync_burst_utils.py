#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sync burst timing and PN sequence utilities for gr-k-gdss.
"""

from typing import Callable

import numpy as np

try:
    from Crypto.Cipher import ChaCha20 as _ChaCha20
except ImportError:
    _ChaCha20 = None

if _ChaCha20 is None:
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
        from cryptography.hazmat.backends import default_backend

        class _ChaCha20Wrapper:
            def __init__(self, key: bytes, nonce: bytes):
                # cryptography's ChaCha20 requires 16-byte nonce; pad 12-byte (RFC 7539) with zeros
                nonce_16 = (nonce + b"\x00" * 16)[:16] if len(nonce) == 12 else nonce
                self._cipher = Cipher(
                    algorithms.ChaCha20(key, nonce_16),
                    mode=None,
                    backend=default_backend(),
                )

            def encrypt(self, data: bytes) -> bytes:
                encryptor = self._cipher.encryptor()
                return encryptor.update(data) + encryptor.finalize()

        class _ChaCha20:
            @staticmethod
            def new(key: bytes, nonce: bytes):
                return _ChaCha20Wrapper(key, nonce)
    except ImportError:
        _ChaCha20 = None

if _ChaCha20 is None:
    raise ImportError("sync_burst_utils requires PyCryptodome or cryptography for ChaCha20")

ChaCha20 = _ChaCha20


def derive_sync_schedule(master_key: bytes, session_id: int, window_ms: int = 50) -> Callable[[int], int]:
    """
    Returns a function that, given a nominal epoch (integer milliseconds
    since session start), returns the actual TX offset in milliseconds.
    Offset is deterministic for both TX and RX given the same master_key.
    """
    import hashlib
    import hmac

    sync_key = hmac.new(
        master_key,
        b"sync-timing-v1" + session_id.to_bytes(8, "big"),
        hashlib.sha256,
    ).digest()

    def get_offset(epoch_ms: int) -> int:
        # Use ChaCha20 keystream indexed by epoch to get deterministic offset
        nonce = epoch_ms.to_bytes(8, "little") + b"\x00" * 4
        cipher = ChaCha20.new(key=sync_key, nonce=nonce)
        rand_bytes = cipher.encrypt(b"\x00" * 4)
        raw = int.from_bytes(rand_bytes, "little")
        return int((raw / 0xFFFFFFFF) * 2 * window_ms) - window_ms

    return get_offset


def derive_sync_pn_sequence(master_key: bytes, session_id: int, chips: int = 10000) -> np.ndarray:
    """
    Returns a binary PN sequence derived from the session key.
    Both TX and RX generate identical sequences given same inputs.
    """
    import hashlib
    import hmac

    pn_key = hmac.new(
        master_key,
        b"sync-pn-v1" + session_id.to_bytes(8, "big"),
        hashlib.sha256,
    ).digest()

    nonce = b"\x00" * 12
    cipher = ChaCha20.new(key=pn_key, nonce=nonce)
    raw = cipher.encrypt(bytes(chips // 8 + 1))

    bits = np.unpackbits(np.frombuffer(raw, dtype=np.uint8))[:chips]
    return bits.astype(np.float32) * 2 - 1


def gaussian_envelope(samples: np.ndarray, rise_fraction: float = 0.1) -> np.ndarray:
    """
    Applies a Gaussian amplitude envelope to a burst.
    rise_fraction: fraction of burst used for rise/fall (each side).
    """
    n = len(samples)
    env = np.ones(n, dtype=np.float32)
    flank = int(n * rise_fraction)
    if flank > 0:
        x = np.linspace(-3, 0, flank, dtype=np.float32)
        ramp = np.exp(-x**2 / 2)
        ramp = ramp / ramp[-1]
        env[:flank] = ramp
        env[-flank:] = ramp[::-1]
    return samples * env

