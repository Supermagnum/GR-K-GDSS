"""Deterministic ITU-style channel simulation helpers (NumPy-only)."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class ChannelModel:
    name: str
    delays_ns: tuple[float, ...]
    powers_db: tuple[float, ...]
    speed_kmh: float
    carrier_hz: float = 915e6


# ITU-R M.1225 Pedestrian A profile (4 taps)
M1225_PEDESTRIAN_A = ChannelModel(
    name="M1225_PEDESTRIAN_A",
    delays_ns=(0.0, 110.0, 190.0, 410.0),
    powers_db=(0.0, -9.7, -19.2, -22.8),
    speed_kmh=3.0,
)

# ITU-R M.1225 Pedestrian B profile (6 taps)
M1225_PEDESTRIAN_B = ChannelModel(
    name="M1225_PEDESTRIAN_B",
    delays_ns=(0.0, 200.0, 800.0, 1200.0, 2300.0, 3700.0),
    powers_db=(0.0, -0.9, -4.9, -8.0, -7.8, -23.9),
    speed_kmh=3.0,
)

# ITU-R M.1225 Vehicular A profile (6 taps)
M1225_VEHICULAR_A = ChannelModel(
    name="M1225_VEHICULAR_A",
    delays_ns=(0.0, 310.0, 710.0, 1090.0, 1730.0, 2510.0),
    powers_db=(0.0, -1.0, -9.0, -10.0, -15.0, -20.0),
    speed_kmh=120.0,
)

# ITU-R P.1238-inspired short-range indoor profile (multipath spread 30-100 ns)
P1238_INDOOR = ChannelModel(
    name="P1238_INDOOR",
    delays_ns=(0.0, 35.0, 70.0, 100.0),
    powers_db=(0.0, -3.0, -6.5, -10.0),
    speed_kmh=1.0,
)

ALL_MODELS: tuple[ChannelModel, ...] = (
    P1238_INDOOR,
    M1225_VEHICULAR_A,
    M1225_PEDESTRIAN_A,
    M1225_PEDESTRIAN_B,
)

def make_delay_sweep_profile(max_delay_ns: float, speed_kmh: float = 3.0, n_taps: int = 6) -> ChannelModel:
    """
    Build a deterministic synthetic ITU-style profile for boundary sweeps.
    Taps are uniformly spaced from 0..max_delay_ns with exponentially decaying power.
    """
    if n_taps < 2:
        raise ValueError("n_taps must be >= 2")
    delays = tuple(float(x) for x in np.linspace(0.0, max_delay_ns, n_taps))
    # 3 dB decay per additional tap, normalized in apply_channel.
    powers = tuple(float(-3.0 * i) for i in range(n_taps))
    return ChannelModel(
        name=f"DELAY_SWEEP_{int(round(max_delay_ns))}ns",
        delays_ns=delays,
        powers_db=powers,
        speed_kmh=speed_kmh,
    )


def max_doppler_hz(speed_kmh: float, carrier_hz: float) -> float:
    c = 299_792_458.0
    v = speed_kmh / 3.6
    return (v / c) * carrier_hz


def _jakes_fading(num_samples: int, fd_hz: float, fs_hz: float, rng: np.random.Generator) -> np.ndarray:
    """Simple 8-tone Jakes-like fading approximation."""
    if fd_hz <= 0.0:
        # Static Rayleigh
        return (rng.normal(0.0, 1.0, size=num_samples) + 1j * rng.normal(0.0, 1.0, size=num_samples)) / math.sqrt(2.0)

    n_terms = 8
    t = np.arange(num_samples, dtype=np.float64) / fs_hz
    phases = rng.uniform(0.0, 2.0 * math.pi, size=(n_terms,))
    angles = rng.uniform(0.0, 2.0 * math.pi, size=(n_terms,))

    i = np.zeros(num_samples, dtype=np.float64)
    q = np.zeros(num_samples, dtype=np.float64)
    for k in range(n_terms):
        w = 2.0 * math.pi * fd_hz * math.cos(angles[k])
        i += np.cos(w * t + phases[k])
        q += np.sin(w * t + phases[k])

    fading = (i + 1j * q) / math.sqrt(n_terms)
    power = np.mean(np.abs(fading) ** 2) + 1e-12
    return (fading / math.sqrt(power)).astype(np.complex64)


def apply_frequency_offset(samples: np.ndarray, hz: float, sample_rate: float) -> np.ndarray:
    if hz == 0.0:
        return samples.copy()
    n = np.arange(len(samples), dtype=np.float64)
    ph = np.exp(1j * 2.0 * math.pi * hz * n / sample_rate).astype(np.complex64)
    return (samples * ph).astype(np.complex64)


def apply_channel(
    samples: np.ndarray,
    model: ChannelModel,
    snr_db: float,
    sample_rate: float = 1e6,
    seed: int = 42,
) -> np.ndarray:
    """
    Apply ITU-style multipath + Rayleigh fading + AWGN.
    AWGN is added after multipath and scaled to target SNR at channel output.
    """
    rng = np.random.default_rng(seed)
    x = np.asarray(samples, dtype=np.complex64)
    n = len(x)

    delays_samples = [int(round((d_ns * 1e-9) * sample_rate)) for d_ns in model.delays_ns]
    tap_powers = np.array([10.0 ** (p_db / 10.0) for p_db in model.powers_db], dtype=np.float64)
    tap_powers /= np.sum(tap_powers) + 1e-12

    fd = max_doppler_hz(model.speed_kmh, model.carrier_hz)
    y = np.zeros(n, dtype=np.complex64)
    for tap_idx, (d, p) in enumerate(zip(delays_samples, tap_powers)):
        if d >= n:
            continue
        fading = _jakes_fading(n - d, fd, sample_rate, np.random.default_rng(seed + 100 + tap_idx))
        tap_gain = math.sqrt(float(p))
        y[d:] += (tap_gain * fading * x[: n - d]).astype(np.complex64)

    sig_power = float(np.mean(np.abs(y) ** 2) + 1e-12)
    noise_power = sig_power / (10.0 ** (snr_db / 10.0))
    sigma = math.sqrt(noise_power / 2.0)
    noise = (rng.normal(0.0, sigma, size=n) + 1j * rng.normal(0.0, sigma, size=n)).astype(np.complex64)
    return (y + noise).astype(np.complex64)


def apply_chip_timing_offset(samples: np.ndarray, offset_chips: int) -> np.ndarray:
    """Integer chip timing offset (samples are chip-rate in these tests)."""
    x = np.asarray(samples, dtype=np.complex64)
    if offset_chips == 0:
        return x.copy()
    n = len(x)
    y = np.zeros_like(x)
    if offset_chips > 0:
        y[offset_chips:] = x[: n - offset_chips]
    else:
        k = -offset_chips
        y[: n - k] = x[k:]
    return y

