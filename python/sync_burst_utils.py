#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sync burst timing and PN sequence utilities for gr-k-gdss.

Provides cryptographically derived sync burst parameters so that each session
uses a unique PN sequence and timing offset, preventing cross-session
correlation (unlike standard GDSS with a fixed PN). Uses ChaCha20 for
deterministic keystream; requires PyCryptodome or cryptography.

Sync bursts can be masked with the same keyed Gaussian masking as the data
(apply_keyed_gaussian_mask) so they are statistically indistinguishable from
the GDSS waveform to a passive observer.

Exported API:
  - derive_sync_schedule(master_key, session_id, ...) -> list[int]
  - derive_sync_pn_sequence(master_key, session_id, chips, burst_index=0) -> np.ndarray
  - derive_sync_amplitude_scaling(master_key, session_id, n_bursts, ...) -> list[float]
  - gaussian_envelope(samples, rise_fraction) -> np.ndarray
  - apply_keyed_gaussian_mask(burst, gdss_key, nonce, variance) -> np.ndarray
"""

from __future__ import annotations

import math
import struct
from typing import Iterable

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

# Minimum mask magnitude to match C++ spreader/despreader (avoids division instability).
_MIN_MASK = 1e-4


def _to_uniform(b: bytes) -> float:
    """Four bytes LE to uniform [0, 1). Matches C++ spreader."""
    v = struct.unpack("<I", b[:4])[0]
    return (float(v) + 0.5) / 4294967296.0


def _box_muller(u1: float, u2: float, variance: float = 1.0) -> float:
    """Box-Muller: two uniform [0,1) -> one Gaussian(0, variance). Matches C++ spreader."""
    if u1 < 1e-10:
        u1 = 1e-10
    g = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    return g * math.sqrt(variance)


def apply_keyed_gaussian_mask(
    burst: np.ndarray,
    gdss_key: bytes,
    nonce: bytes,
    variance: float = 1.0,
) -> np.ndarray:
    """
    Apply the same keyed Gaussian masking to a burst as used for GDSS data.

    Uses ChaCha20 IETF keystream and Box-Muller (matching kgdss_spreader_cc_impl)
    so the burst is statistically indistinguishable from the GDSS waveform. A
    passive observer sees Gaussian-noise-like statistics instead of a
    recognizable DSSS chip pattern. Use gdss_sync_burst_nonce(session_id) for
    nonce so the sync-burst keystream does not overlap with the data keystream.

    Args:
        burst: Complex array (chip-rate burst, e.g. PN * gaussian_envelope).
        gdss_key: 32-byte GDSS masking key (e.g. gdss_masking from derive_session_keys).
        nonce: 12-byte ChaCha20 IETF nonce (e.g. from gdss_sync_burst_nonce(session_id)).
        variance: Gaussian variance for mask (default 1.0, match spreader).

    Returns:
        New complex array: out[i] = (burst[i].real * mask_i, burst[i].imag * mask_q).
    """
    n = len(burst)
    num_bytes = n * 16
    cipher = ChaCha20.new(key=gdss_key, nonce=nonce)
    keystream = cipher.encrypt(b"\x00" * num_bytes)
    w = np.frombuffer(keystream, dtype="<u4", count=n * 4).reshape(n, 4)
    u = (w.astype(np.float64) + 0.5) / 4294967296.0
    u1 = u[:, 0]
    u2 = u[:, 1]
    u3 = u[:, 2]
    u4 = u[:, 3]
    u1c = np.maximum(u1, 1e-10)
    u3c = np.maximum(u3, 1e-10)
    mask_i = np.sqrt(-2.0 * np.log(u1c)) * np.cos(2.0 * np.pi * u2) * np.sqrt(variance)
    mask_q = np.sqrt(-2.0 * np.log(u3c)) * np.cos(2.0 * np.pi * u4) * np.sqrt(variance)
    mask_i = np.where(
        np.abs(mask_i) < _MIN_MASK,
        np.where(mask_i >= 0, _MIN_MASK, -_MIN_MASK),
        mask_i,
    )
    mask_q = np.where(
        np.abs(mask_q) < _MIN_MASK,
        np.where(mask_q >= 0, _MIN_MASK, -_MIN_MASK),
        mask_q,
    )
    out = np.empty(n, dtype=np.complex64)
    br = burst.real.astype(np.float64, copy=False)
    bi = burst.imag.astype(np.float64, copy=False)
    out.real[...] = (br * mask_i).astype(np.float32)
    out.imag[...] = (bi * mask_q).astype(np.float32)
    return out


def derive_sync_schedule(
    master_key: bytes,
    session_id: int,
    *,
    session_duration_s: float = 900.0,
    n_bursts: int = 20,
    mean_interval_s: float = 60.0,
    pareto_alpha: float = 2.0,
    min_interval_s: float = 5.0,
) -> list[int]:
    """
    Derive a deterministic multi-burst sync schedule for a session.

    Instead of emitting a single burst at session start, TX emits a pseudo-random
    sequence of sync bursts throughout the session lifetime. TX and RX derive the
    same ordered list of burst epochs (milliseconds since session start) from the
    same inputs, without any explicit signalling.

    Inter-burst intervals are derived from per-burst key material and mapped
    through a Pareto inverse CDF (heavy-tailed), producing an irregular cadence.

    Args:
        master_key: 32-byte key (e.g. sync_timing from derive_session_keys).
        session_id: Session identifier; different sessions get different offsets.
        session_duration_s: Maximum session duration to schedule over.
        n_bursts: Number of sync bursts to schedule (best-effort; may be fewer if
            parameters would exceed session_duration_s).
        mean_interval_s: Target mean interval between bursts (seconds). Used to
            parameterize the Pareto scale.
        pareto_alpha: Pareto shape parameter alpha (> 1.0). Larger alpha reduces
            tail weight; smaller alpha produces longer gaps.
        min_interval_s: Lower bound on inter-burst interval (seconds) to avoid
            degenerate clustering.

    Returns:
        Ordered list of burst epochs in milliseconds since session start.
    """
    import hashlib
    import hmac

    if n_bursts <= 0:
        return []
    if session_duration_s <= 0:
        return []
    if mean_interval_s <= 0:
        raise ValueError("mean_interval_s must be > 0")
    if pareto_alpha <= 1.0:
        raise ValueError("pareto_alpha must be > 1.0")
    if min_interval_s < 0:
        raise ValueError("min_interval_s must be >= 0")

    # HKDF-Expand-like: domain label + session + burst_index (monotonic counter).
    base = hmac.new(
        master_key,
        b"sync-schedule-v2" + session_id.to_bytes(8, "big"),
        hashlib.sha256,
    ).digest()

    # Parameterize Pareto scale xm so that E[X] ~= mean_interval_s.
    # For Pareto(xm, alpha): mean = alpha*xm/(alpha-1), so xm = mean*(alpha-1)/alpha.
    xm = float(mean_interval_s) * (float(pareto_alpha) - 1.0) / float(pareto_alpha)
    duration_ms = int(session_duration_s * 1000.0)
    min_interval_ms = int(min_interval_s * 1000.0)

    epochs: list[int] = []
    t_ms = 0
    for i in range(int(n_bursts)):
        # Derive per-burst uniform u in (0,1) from ChaCha20 keystream.
        # Nonce uses burst index to avoid overlap and keep it deterministic.
        per = hmac.new(base, b"/i/" + i.to_bytes(8, "big"), hashlib.sha256).digest()
        nonce = i.to_bytes(8, "little") + b"\x00" * 4
        cipher = ChaCha20.new(key=per, nonce=nonce)
        u_bytes = cipher.encrypt(b"\x00" * 4)
        u = _to_uniform(u_bytes)
        # Pareto inverse CDF: x = xm / (1-u)^(1/alpha). Heavy-tailed.
        interval_s = xm / pow(max(1e-12, 1.0 - u), 1.0 / float(pareto_alpha))
        interval_ms = max(min_interval_ms, int(interval_s * 1000.0))
        t_ms += interval_ms
        if t_ms >= duration_ms:
            break
        epochs.append(t_ms)
    return epochs


def derive_sync_pn_sequence(
    master_key: bytes,
    session_id: int,
    chips: int = 10000,
    burst_index: int = 0,
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
        burst_index: Burst index within the schedule. Defaults to 0 for backward
            compatibility; when provided, each burst gets a unique PN sequence.

    Returns:
        One-dimensional float32 array of length chips with values in {-1.0, +1.0}.
    """
    import hashlib
    import hmac

    pn_key = hmac.new(
        master_key,
        b"sync-pn-v2"
        + session_id.to_bytes(8, "big")
        + b"/i/"
        + int(burst_index).to_bytes(8, "big", signed=False),
        hashlib.sha256,
    ).digest()

    nonce = b"\x00" * 12
    cipher = ChaCha20.new(key=pn_key, nonce=nonce)
    raw = cipher.encrypt(bytes(chips // 8 + 1))

    bits = np.unpackbits(np.frombuffer(raw, dtype=np.uint8))[:chips]
    return bits.astype(np.float32) * 2 - 1


def derive_sync_amplitude_scaling(
    master_key: bytes,
    session_id: int,
    n_bursts: int,
    *,
    lognorm_mu: float = 0.0,
    lognorm_sigma: float = 0.35,
) -> list[float]:
    """
    Derive a deterministic per-burst amplitude scaling sequence.

    The scaling is log-normally distributed: scale = exp(mu + sigma * Z), where
    Z ~ Normal(0, 1) derived deterministically from key material. TX and RX compute
    the same scale factors for the same inputs.
    """
    import hashlib
    import hmac

    if n_bursts <= 0:
        return []
    if lognorm_sigma < 0:
        raise ValueError("lognorm_sigma must be >= 0")

    base = hmac.new(
        master_key,
        b"sync-amp-scale-v1" + session_id.to_bytes(8, "big"),
        hashlib.sha256,
    ).digest()

    scales: list[float] = []
    for i in range(int(n_bursts)):
        per = hmac.new(base, b"/i/" + i.to_bytes(8, "big"), hashlib.sha256).digest()
        nonce = i.to_bytes(8, "little") + b"\x00" * 4
        cipher = ChaCha20.new(key=per, nonce=nonce)
        r = cipher.encrypt(b"\x00" * 8)
        u1 = _to_uniform(r[:4])
        u2 = _to_uniform(r[4:8])
        z = _box_muller(u1, u2, variance=1.0)
        scale = math.exp(float(lognorm_mu) + float(lognorm_sigma) * float(z))
        scales.append(float(scale))
    return scales


def gaussian_envelope(
    samples: np.ndarray,
    rise_fraction: float = 0.15,
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

