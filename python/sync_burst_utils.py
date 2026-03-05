#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sync burst timing and PN sequence utilities for gr-k-gdss.

Provides cryptographically derived sync burst parameters so that each session
uses a unique PN sequence and timing offset, preventing cross-session
correlation (unlike standard GDSS with a fixed PN). Uses ChaCha20 for
deterministic keystream; requires PyCryptodome or cryptography.

Exported API:
  - derive_sync_schedule(master_key, session_id, window_ms) -> Callable[[int], int]
  - derive_sync_pn_sequence(master_key, session_id, chips) -> np.ndarray
  - gaussian_envelope(samples, rise_fraction) -> np.ndarray
"""

from __future__ import annotations

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


def derive_sync_schedule(
    master_key: bytes,
    session_id: int,
    window_ms: int = 50,
) -> Callable[[int], int]:
    """
    Derive a deterministic sync-burst timing schedule for a session.

    Returns a callable that maps a nominal epoch (milliseconds since session
    start) to an actual TX offset in milliseconds in the range [-window_ms,
    +window_ms]. TX and RX compute the same offset given the same master_key
    and session_id, so sync bursts are aligned without using a fixed position
    (which would be correlatable across sessions).

    Args:
        master_key: 32-byte key (e.g. sync_timing from derive_session_keys).
        session_id: Session identifier; different sessions get different offsets.
        window_ms: Half-width of the offset window in ms. Default 50.

    Returns:
        Function get_offset(epoch_ms: int) -> int giving offset in milliseconds.
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


def derive_sync_pn_sequence(
    master_key: bytes,
    session_id: int,
    chips: int = 10000,
) -> np.ndarray:
    """
    Derive a session-unique pseudo-noise sequence for sync bursts.

    Uses HMAC-SHA256 to derive a ChaCha20 key from master_key and session_id,
    then expands ChaCha20 keystream to bits. Both TX and RX generate the same
    sequence given the same master_key and session_id. Values are +1.0 or -1.0
    (BPSK-like) as float32.

    Args:
        master_key: 32-byte key (e.g. sync_pn from derive_session_keys).
        session_id: Session identifier; different sessions get different PN.
        chips: Length of the PN sequence. Default 10000.

    Returns:
        One-dimensional float32 array of length chips with values in {-1.0, +1.0}.
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


def gaussian_envelope(
    samples: np.ndarray,
    rise_fraction: float = 0.1,
) -> np.ndarray:
    """
    Apply a Gaussian-shaped amplitude envelope to a burst to reduce sidelobes.

    The envelope is unity in the center and ramps up from zero at the start
    and down to zero at the end using a half-Gaussian (exp(-x^2/2)) shape.
    This softens the burst edges in the time domain and reduces spectral
    splatter compared to a rectangular window.

    Args:
        samples: Complex or real array of burst samples (modified in place if
            possible; otherwise a copy is returned multiplied by the envelope).
        rise_fraction: Fraction of the burst length used for rise (start) and
            fall (end). Default 0.1 (10% on each side).

    Returns:
        Array of same shape and dtype as samples, scaled by the envelope.
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

