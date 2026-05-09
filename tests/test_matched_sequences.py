# SPDX-License-Identifier: GPL-3.0-or-later
"""
Matched GDSS spread/despread using the same ChaCha20-IETF keystream as the C++ blocks.

Requires libsodium (shared library) for keystream generation. Skips tests if libsodium
is not available. Does not require GNU Radio.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import math
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "python") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "python"))

from session_key_derivation import (  # noqa: E402
    derive_session_keys,
    gdss_nonce,
)

_sodium_lib = None


def _load_sodium():
    global _sodium_lib
    if _sodium_lib is not None:
        return _sodium_lib
    path = ctypes.util.find_library("sodium")
    if path is None:
        return None
    lib = ctypes.CDLL(path)
    fn = lib.crypto_stream_chacha20_ietf_xor_ic
    fn.argtypes = [
        ctypes.POINTER(ctypes.c_ubyte),
        ctypes.POINTER(ctypes.c_ubyte),
        ctypes.c_ulonglong,
        ctypes.POINTER(ctypes.c_ubyte),
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_ubyte),
    ]
    fn.restype = ctypes.c_int
    _sodium_lib = lib, fn
    return _sodium_lib


def _produce_chacha_ietf_keystream(
    length: int,
    key: bytes,
    nonce: bytes,
    ctr: int,
    rem: bytearray,
    rem_len: List[int],
) -> Tuple[bytes, int]:
    """Mirror lib/chacha_ietf_keystream.h (byte offset ctr, 64-byte blocks)."""
    assert len(key) == 32 and len(nonce) == 12
    loaded = _load_sodium()
    if loaded is None:
        pytest.skip("libsodium shared library not found")
    _, xor_ic = loaded
    out = bytearray(length)
    filled = 0
    chacha_block = (ctypes.c_ubyte * 64)()

    while filled < length:
        if rem_len[0] > 0:
            take = min(rem_len[0], length - filled)
            out[filled : filled + take] = rem[:take]
            if take < rem_len[0]:
                rem[: rem_len[0] - take] = rem[take : rem_len[0]]
            rem_len[0] -= take
            filled += take
            ctr += take
            continue

        block_idx = ctr // 64
        if block_idx > 0xFFFFFFFF:
            raise RuntimeError("ChaCha IETF block counter overflow")
        skip = ctr % 64
        for i in range(64):
            chacha_block[i] = 0
        m = (ctypes.c_ubyte * 64)()
        r = xor_ic(
            chacha_block,
            m,
            64,
            (ctypes.c_ubyte * 12)(*nonce),
            ctypes.c_uint32(int(block_idx)),
            (ctypes.c_ubyte * 32)(*key),
        )
        if r != 0:
            raise RuntimeError("crypto_stream_chacha20_ietf_xor_ic failed")

        block = bytes(chacha_block)
        avail = 64 - skip
        take = min(avail, length - filled)
        out[filled : filled + take] = block[skip : skip + take]
        ctr += take
        filled += take
        used_from_block = skip + take
        if used_from_block < 64:
            tail = block[used_from_block:]
            rem[: len(tail)] = tail
            rem_len[0] = len(tail)
        else:
            rem_len[0] = 0

    return bytes(out), ctr


def _to_uniform_u32(b: bytes, off: int) -> float:
    v = (
        b[off]
        | (b[off + 1] << 8)
        | (b[off + 2] << 16)
        | (b[off + 3] << 24)
    ) & 0xFFFFFFFF
    return (float(v) + 0.5) / 4294967296.0


def _box_muller_spread(u1: float, u2: float, variance: float) -> Tuple[float, float]:
    u1 = max(u1, 1e-10)
    r = math.sqrt(-2.0 * math.log(u1)) * math.sqrt(variance)
    th = 2.0 * math.pi * u2
    return r * math.cos(th), r * math.sin(th)


def _box_muller_despread(u1: float, u2: float) -> Tuple[float, float]:
    u1 = max(u1, 1e-10)
    r = math.sqrt(-2.0 * math.log(u1))
    th = 2.0 * math.pi * u2
    return r * math.cos(th), r * math.sin(th)


def _clamp_mask(mi: float, mq: float, min_mask: float = 1e-4) -> Tuple[float, float]:
    if abs(mi) < min_mask:
        mi = min_mask if mi >= 0 else -min_mask
    if abs(mq) < min_mask:
        mq = min_mask if mq >= 0 else -min_mask
    return mi, mq


def spread_chips(
    symbols: np.ndarray,
    key: bytes,
    nonce: bytes,
    chips_per_symbol: int,
    variance: float,
    ctr: int = 0,
    rem: bytearray | None = None,
    rem_len: List[int] | None = None,
) -> Tuple[np.ndarray, int, bytearray, List[int]]:
    if rem is None:
        rem = bytearray(64)
    if rem_len is None:
        rem_len = [0]
    chips_out: List[complex] = []
    for sym in symbols:
        for _chip in range(chips_per_symbol):
            ks8, ctr = _produce_chacha_ietf_keystream(8, key, nonce, ctr, rem, rem_len)
            mi, mq = _box_muller_spread(
                _to_uniform_u32(ks8, 0), _to_uniform_u32(ks8, 4), variance
            )
            mi, mq = _clamp_mask(mi, mq)
            chips_out.append(sym * complex(mi, mq))
    return np.array(chips_out, dtype=np.complex128), ctr, rem, rem_len


def despread_symbols(
    chips: np.ndarray,
    key: bytes,
    nonce: bytes,
    chips_per_symbol: int,
    variance: float,
    ctr: int = 0,
    rem: bytearray | None = None,
    rem_len: List[int] | None = None,
) -> Tuple[np.ndarray, int, bytearray, List[int]]:
    if rem is None:
        rem = bytearray(64)
    if rem_len is None:
        rem_len = [0]
    n_sym = len(chips) // chips_per_symbol
    syms: List[complex] = []
    for i in range(n_sym):
        sl = chips[i * chips_per_symbol : (i + 1) * chips_per_symbol]
        sum_i = sum_q = 0.0
        mss = 0.0
        for samp in sl:
            ks8, ctr = _produce_chacha_ietf_keystream(8, key, nonce, ctr, rem, rem_len)
            mi, mq = _box_muller_despread(
                _to_uniform_u32(ks8, 0), _to_uniform_u32(ks8, 4)
            )
            mi, mq = _clamp_mask(mi, mq)
            sr, si = float(samp.real), float(samp.imag)
            sum_i += sr * mi + si * mq
            sum_q += si * mi - sr * mq
            mss += mi * mi + mq * mq
        norm = max(mss, 1e-6)
        syms.append(complex(sum_i / norm, sum_q / norm))
    return np.array(syms, dtype=np.complex128), ctr, rem, rem_len


def _coherence_zero_lag(a: np.ndarray, b: np.ndarray) -> float:
    """|sum conj(a)*b| / (||a|| ||b||) at zero lag; 1.0 when b is a complex scalar multiple of a."""
    a = np.asarray(a, dtype=np.complex128).ravel()
    b = np.asarray(b, dtype=np.complex128).ravel()
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    num = float(np.abs(np.vdot(a, b)))
    den = float(np.linalg.norm(a) * np.linalg.norm(b)) + 1e-12
    return num / den


def _complex_corr(a: np.ndarray, b: np.ndarray) -> float:
    """Normalized real inner product (legacy helper for wrong-key checks)."""
    a = np.asarray(a, dtype=np.complex128).ravel()
    b = np.asarray(b, dtype=np.complex128).ravel()
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    num = float(np.real(np.vdot(a, b)))
    den = float(np.linalg.norm(a) * np.linalg.norm(b)) + 1e-12
    return abs(num) / den


@pytest.fixture(scope="module")
def sodium():
    if _load_sodium() is None:
        pytest.skip("libsodium shared library not found")
    return True


@pytest.fixture
def session_material(sodium):
    test_secret = bytes(range(32))
    keys = derive_session_keys(test_secret)
    k = keys["gdss_masking"]
    n = gdss_nonce(1, 0)
    assert len(k) == 32 and len(n) == 12
    return k, n


@pytest.mark.parametrize("chips_per_symbol", [32, 64, 256])
def test_matched_key_near_unity_coherence_zero_lag(session_material, chips_per_symbol):
    """Noiseless ChaCha + Box-Muller + MF recovery matches input at machine precision (zero lag)."""
    key, nonce = session_material
    rng = np.random.default_rng(42)
    n_sym = 400
    phases = rng.uniform(0, 2 * np.pi, n_sym)
    mag = rng.uniform(0.5, 1.5, n_sym)
    symbols = mag * np.exp(1j * phases)
    variance = 1.0
    chips, _c1, _r1, _rl1 = spread_chips(symbols, key, nonce, chips_per_symbol, variance)
    out, _c2, _r2, _rl2 = despread_symbols(chips, key, nonce, chips_per_symbol, variance)
    coh = _coherence_zero_lag(symbols, out)
    assert coh >= 1.0 - 1e-12, f"zero-lag coherence should be ~1.0, got {coh}"
    max_err = float(np.max(np.abs(out - symbols)))
    assert max_err < 1e-12, f"max|out-sym| should be ~1e-15 scale, got {max_err}"


def test_wrong_key_low_correlation(session_material):
    key, nonce = session_material
    wrong_secret = bytes((x ^ 0xFF) for x in bytes(range(32)))
    wkey = derive_session_keys(wrong_secret)["gdss_masking"]
    assert wkey != key
    rng = np.random.default_rng(7)
    symbols = rng.standard_normal(200) + 1j * rng.standard_normal(200)
    chips_per_symbol = 32
    variance = 1.0
    chips, _, _, _ = spread_chips(symbols, key, nonce, chips_per_symbol, variance)
    out, _, _, _ = despread_symbols(chips, wkey, nonce, chips_per_symbol, variance)
    corr = _complex_corr(symbols, out)
    assert corr < 0.1, f"wrong key should decorrelate, got {corr}"
