#!/usr/bin/env python3
"""
Monte Carlo BER simulation for GR-K-GDSS paper (Section 7).
Python/numpy only — statistical channel models (not GNU Radio runtime).

Models:
  - DSSS: Shakeel eq.1 theoretical reference.
  - Standard GDSS: BPSK chip x_i = s * |G_i|, receiver Z = sum_i r_i (unknown mask).
  - Keyed GDSS: x_i = s * m_i, m_i from Box-Muller, receiver Z = mean(r_i / m_i), MIN_MASK clamp.
"""
from __future__ import annotations

import math
import os
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from scipy import special

# Match gr-k-gdss spreader/despreader
MIN_MASK = 1e-4
SNR_DB_GRID = np.arange(-20, 6, 1.0, dtype=np.float64)
N_VALUES = (64, 128, 256)

# Bits per (SNR, scenario) for production; override with BER_MC_NUM_BITS for quick runs
_DEFAULT_NUM_BITS = 1_000_000
_NUM_BITS = int(os.environ.get("BER_MC_NUM_BITS", str(_DEFAULT_NUM_BITS)))
_BATCH = 10_000


def _ebn0_linear(db: float) -> float:
    return 10.0 ** (db / 10.0)


def ber_dsss_theory(snr_db: np.ndarray, n: int) -> np.ndarray:
    """Shakeel-style: P_b = 0.5 * erfc(sqrt(N * Es/N0 / 2)), Es/N0 = 10^(snr_db/10)."""
    esn0 = _ebn0_linear(snr_db)
    x = np.sqrt(n * esn0 / 2.0)
    return np.clip(0.5 * special.erfc(x), 1e-12, 0.5)


def _chip_noise_sigma(eb_n0_db: float, n: int) -> float:
    """
    AWGN variance per chip for repetition-combine DSSS reference:
    r_i = s + n_i, Z = sum r_i, match BER ~ Q(sqrt(2*Eb/N0)) with Eb = N * Ec, Ec=1.
    sigma_n^2 = N / (2 * Eb/N0).
    """
    g = _ebn0_linear(eb_n0_db)
    return math.sqrt(n / (2.0 * g))


def _box_muller_pair(u1: np.ndarray, u2: np.ndarray, variance: float = 1.0) -> np.ndarray:
    u1 = np.clip(u1, 1e-12, 1.0 - 1e-12)
    return np.sqrt(-2.0 * np.log(u1)) * np.cos(2.0 * math.pi * u2) * math.sqrt(variance)


def _clamp_mask(m: np.ndarray) -> np.ndarray:
    out = m.copy()
    out = np.where(np.abs(out) < MIN_MASK, np.sign(out) * MIN_MASK + (out == 0) * MIN_MASK, out)
    out = np.where(out == 0, MIN_MASK, out)
    return out


def mc_ber_keyed_awgn(
    n: int,
    eb_n0_db: float,
    rng: np.random.Generator,
    n_bits: int = _NUM_BITS,
    batch: int = _BATCH,
) -> float:
    """Keyed GDSS: tx chip = s * m_i (Box-Muller), rx Z = mean((s*m_i + n_i)/m_i)."""
    sigma_n = _chip_noise_sigma(eb_n0_db, n)
    err = 0
    total = 0
    while total < n_bits:
        b = min(batch, n_bits - total)
        s = rng.choice([-1.0, 1.0], size=b)
        u1 = rng.random((b, n))
        u2 = rng.random((b, n))
        m = _clamp_mask(_box_muller_pair(u1, u2))
        noise = rng.standard_normal((b, n)) * sigma_n
        r = s[:, None] * m + noise
        z = np.mean(r / m, axis=1)
        err += int(np.sum(np.sign(z) != np.sign(s)))
        total += b
    return err / max(total, 1)


def mc_ber_standard_gdss_awgn(
    n: int,
    eb_n0_db: float,
    rng: np.random.Generator,
    n_bits: int = _NUM_BITS,
    batch: int = _BATCH,
) -> float:
    """
    Standard GDSS: chip = s * |G_i|, G ~ N(0,1). Receiver sums chips (mask unknown).
    Z = sum_i r_i; decision sign(Z) vs 0 for s=+1 mapped by symmetry.
    """
    sigma_n = _chip_noise_sigma(eb_n0_db, n)
    err = 0
    total = 0
    while total < n_bits:
        b = min(batch, n_bits - total)
        s = rng.choice([-1.0, 1.0], size=b)
        a = np.abs(rng.standard_normal((b, n)))
        noise = rng.standard_normal((b, n)) * sigma_n
        r = s[:, None] * a + noise
        z = np.sum(r, axis=1)
        err += int(np.sum(np.sign(z) != np.sign(s)))
        total += b
    return err / max(total, 1)


def mc_ber_keyed_rayleigh(
    n: int,
    eb_n0_db: float,
    rng: np.random.Generator,
    n_bits: int = _NUM_BITS,
    batch: int = _BATCH,
    fd_hz: float = 50.0,
    chip_rate: float = 500_000.0,
) -> float:
    """
    Rayleigh amplitude block fading (E[|h|^2]=1) with Doppler-induced phase rotation
    across chips (ITU-R P.1406 land-mobile style, simplified baseband real model).
    """
    sigma_n = _chip_noise_sigma(eb_n0_db, n)
    err = 0
    total = 0
    dphi = 2.0 * math.pi * fd_hz / chip_rate
    while total < n_bits:
        b = min(batch, n_bits - total)
        s = rng.choice([-1.0, 1.0], size=b)
        h = rng.rayleigh(scale=1.0 / math.sqrt(2.0), size=b)
        phase0 = rng.uniform(0, 2 * math.pi, size=b)
        u1 = rng.random((b, n))
        u2 = rng.random((b, n))
        m = _clamp_mask(_box_muller_pair(u1, u2))
        k = np.arange(n, dtype=np.float64)[None, :]
        phi = phase0[:, None] + dphi * k
        h_eff = h[:, None] * np.cos(phi)
        noise = rng.standard_normal((b, n)) * sigma_n
        r = s[:, None] * h_eff * m + noise
        z = np.mean(r / m, axis=1)
        err += int(np.sum(np.sign(z) != np.sign(s)))
        total += b
    return err / max(total, 1)


def mc_ber_standard_gdss_rayleigh(
    n: int,
    eb_n0_db: float,
    rng: np.random.Generator,
    n_bits: int = _NUM_BITS,
    batch: int = _BATCH,
    fd_hz: float = 50.0,
    chip_rate: float = 500_000.0,
) -> float:
    sigma_n = _chip_noise_sigma(eb_n0_db, n)
    err = 0
    total = 0
    dphi = 2.0 * math.pi * fd_hz / chip_rate
    while total < n_bits:
        b = min(batch, n_bits - total)
        s = rng.choice([-1.0, 1.0], size=b)
        h = rng.rayleigh(scale=1.0 / math.sqrt(2.0), size=b)
        phase0 = rng.uniform(0, 2 * math.pi, size=b)
        a = np.abs(rng.standard_normal((b, n)))
        k = np.arange(n, dtype=np.float64)[None, :]
        phi = phase0[:, None] + dphi * k
        h_eff = h[:, None] * np.cos(phi)
        noise = rng.standard_normal((b, n)) * sigma_n
        r = s[:, None] * h_eff * a + noise
        z = np.sum(r, axis=1)
        err += int(np.sum(np.sign(z) != np.sign(s)))
        total += b
    return err / max(total, 1)


def _normalize_taps(h: np.ndarray) -> np.ndarray:
    h = np.asarray(h, dtype=np.float64)
    return h / np.sqrt(np.sum(h**2) + 1e-24)


# Stylised STANAG-like HF multipath (complex baseband real-only BPSK on I)
HF_TAPS: Dict[str, np.ndarray] = {
    "AWGN": _normalize_taps(np.array([1.0])),
    "Good": _normalize_taps(np.array([0.92, 0.28, 0.12])),
    "Poor": _normalize_taps(np.array([0.65, 0.48, 0.32, 0.22, 0.12])),
    "Disturbed": _normalize_taps(np.array([0.45, 0.40, 0.38, 0.32, 0.28, 0.22, 0.18, 0.12])),
}


def _apply_isi_channel(chips: np.ndarray, taps: np.ndarray) -> np.ndarray:
    """chips shape (b, n); ISI convolve along n, truncate to n."""
    b, n = chips.shape
    L = len(taps)
    out = np.zeros_like(chips)
    padded = np.concatenate([np.zeros((b, L - 1)), chips], axis=1)
    for i in range(n):
        out[:, i] = np.sum(padded[:, i : i + L] * taps[::-1], axis=1)
    return out


def mc_ber_keyed_hf(
    n: int,
    eb_n0_db: float,
    rng: np.random.Generator,
    profile: str,
    n_bits: int = _NUM_BITS,
    batch: int = _BATCH,
) -> float:
    taps = HF_TAPS[profile]
    sigma_n = _chip_noise_sigma(eb_n0_db, n)
    err = 0
    total = 0
    while total < n_bits:
        b = min(batch, n_bits - total)
        s = rng.choice([-1.0, 1.0], size=b)
        u1 = rng.random((b, n))
        u2 = rng.random((b, n))
        m = _clamp_mask(_box_muller_pair(u1, u2))
        x = s[:, None] * m
        y = _apply_isi_channel(x, taps)
        noise = rng.standard_normal((b, n)) * sigma_n
        r = y + noise
        z = np.mean(r / m, axis=1)
        err += int(np.sum(np.sign(z) != np.sign(s)))
        total += b
    return err / max(total, 1)


def mc_ber_standard_hf(
    n: int,
    eb_n0_db: float,
    rng: np.random.Generator,
    profile: str,
    n_bits: int = _NUM_BITS,
    batch: int = _BATCH,
) -> float:
    taps = HF_TAPS[profile]
    sigma_n = _chip_noise_sigma(eb_n0_db, n)
    err = 0
    total = 0
    while total < n_bits:
        b = min(batch, n_bits - total)
        s = rng.choice([-1.0, 1.0], size=b)
        a = np.abs(rng.standard_normal((b, n)))
        x = s[:, None] * a
        y = _apply_isi_channel(x, taps)
        noise = rng.standard_normal((b, n)) * sigma_n
        r = y + noise
        z = np.sum(r, axis=1)
        err += int(np.sum(np.sign(z) != np.sign(s)))
        total += b
    return err / max(total, 1)


def ldpc_effective_ber(
    uncoded_ber: np.ndarray,
    coding_gain_db: float,
) -> np.ndarray:
    """Ideal rate-1/2: shift SNR axis by coding gain (equivalent Eb/N0 improvement)."""
    # BER_u(Eb/N0) ~ BER_c(Eb/N0 + G)  =>  interpolate in log-BER vs SNR
    snr_axis = SNR_DB_GRID
    snr_shifted = snr_axis + coding_gain_db
    # build uncoded curve as function of snr, sample at shifted points via interp on log ber
    logb = np.log10(np.clip(uncoded_ber, 1e-12, 0.49))
    return np.clip(10 ** np.interp(snr_shifted, snr_axis, logb), 1e-12, 0.49)


def run_awgn_curves(seed: int = 42) -> Dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    out: Dict[str, np.ndarray] = {}
    for n in N_VALUES:
        out[f"dsss_{n}"] = ber_dsss_theory(SNR_DB_GRID, n)
        std = []
        keyed = []
        for snr in SNR_DB_GRID:
            std.append(mc_ber_standard_gdss_awgn(n, float(snr), rng))
            keyed.append(mc_ber_keyed_awgn(n, float(snr), rng))
        out[f"std_{n}"] = np.array(std)
        out[f"keyed_{n}"] = np.array(keyed)
    return out


def run_vhf_curves(seed: int = 43) -> Dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = 256
    res = {}
    for label, fd in [("ped_50", 50.0), ("veh_200", 200.0)]:
        for mode in ("m1", "m2"):
            # Mode 2: approximate multicarrier diversity as 0.6 dB effective gain vs Mode 1
            snr_eff = SNR_DB_GRID + (0.6 if mode == "m2" else 0.0)
            unc_k = []
            for snr in snr_eff:
                unc_k.append(mc_ber_keyed_rayleigh(n, float(snr), rng, fd_hz=fd))
            unc_k = np.array(unc_k)
            coded_k = ldpc_effective_ber(unc_k, 5.0)
            res[f"{label}_{mode}_unc"] = unc_k
            res[f"{label}_{mode}_coded"] = coded_k
    return res


def run_hf_curves(seed: int = 44) -> Dict[str, np.ndarray]:
    n = 256
    res = {}
    for i, prof in enumerate(HF_TAPS):
        rng = np.random.default_rng(seed + i * 997)
        std_u = []
        key_unc = []
        for snr in SNR_DB_GRID:
            std_u.append(mc_ber_standard_hf(n, float(snr), rng, prof))
            key_unc.append(mc_ber_keyed_hf(n, float(snr), rng, prof))
        std_u = np.array(std_u)
        key_unc = np.array(key_unc)
        key_coded = ldpc_effective_ber(key_unc, 5.0)
        res[f"{prof}_std_unc"] = std_u
        res[f"{prof}_keyed_unc"] = key_unc
        res[f"{prof}_keyed_coded"] = key_coded
    return res


def run_ldpc_block_comparison(seed: int = 45) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Keyed AWGN N=256: uncoded vs LDPC ~5 dB gain for block 576 vs 1152 (slightly different gain)."""
    rng = np.random.default_rng(seed)
    n = 256
    unc = []
    for snr in SNR_DB_GRID:
        unc.append(mc_ber_keyed_awgn(n, float(snr), rng))
    unc = np.array(unc)
    coded_576 = ldpc_effective_ber(unc, 4.8)
    coded_1152 = ldpc_effective_ber(unc, 5.2)
    return unc, coded_576, coded_1152


def save_all_npz(path: str, seed_base: int = 42) -> None:
    awgn = run_awgn_curves(seed_base)
    vhf = run_vhf_curves(seed_base + 1)
    hf = run_hf_curves(seed_base + 2)
    unc, c576, c1152 = run_ldpc_block_comparison(seed_base + 3)
    snr = SNR_DB_GRID
    payload = {"snr_db": snr, "ldpc_unc": unc, "ldpc_576": c576, "ldpc_1152": c1152}
    payload.update(awgn)
    payload.update({f"vhf_{k}": v for k, v in vhf.items()})
    payload.update({f"hf_{k}": v for k, v in hf.items()})
    payload["meta_bits"] = np.array([_NUM_BITS], dtype=np.int64)
    payload["meta_min_mask"] = np.array([MIN_MASK])
    np.savez(path, **payload)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "figures", "ber_mc_results.npz")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    print("BER_MC_NUM_BITS =", _NUM_BITS, "(set env for faster test)")
    save_all_npz(out)
    print("Saved", out)
