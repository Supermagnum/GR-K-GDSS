#!/usr/bin/env python3
"""
Generate spectrum snapshot images (600 kHz bandwidth) from gr-k-gdss IQ test files.
Output: spectrum_baseline.png, spectrum_realistic_baseline.png (01b), spectrum_standard_gdss.png,
spectrum_keyed_gdss.png, spectrum_real_noise.png (if File 08 present), spectrum_realistic_plus_standard_gdss.png (01c),
spectrum_realistic_plus_keyed_gdss.png (01d). All use Gaussian roll-off where applicable.
Requires: numpy, scipy, matplotlib.
Run after generate_iq_test_files.py so that 01, 01b, 03, 06, 09 exist.
"""

import os
import sys

import numpy as np
from scipy.signal import welch, resample, windows

IQ_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iq_files")
SAMPLE_RATE_IN = 500_000   # Hz; test files are 500 kHz
BANDWIDTH = 600_000        # Hz; desired display bandwidth
SAMPLE_RATE_OUT = BANDWIDTH
N_PERSEG = 8192
N_SAMPLES_USE = 500_000    # use first 1 s at 500 kHz for PSD


def load_cf32(path: str) -> np.ndarray:
    return np.fromfile(path, dtype=np.complex64)


def compute_psd_600k(data: np.ndarray, nperseg: int = N_PERSEG, sample_rate_in: int = SAMPLE_RATE_IN) -> tuple:
    """Resample to 600 kHz and compute two-sided PSD with Gaussian roll-off.

    sample_rate_in: actual sample rate of data (Hz). Use for real recordings that differ from 500 kHz.
    Returns (freq_khz, power_dB).
    """
    n_in = min(len(data), N_SAMPLES_USE)
    data = data[:n_in]
    real = data.real - np.mean(data.real)
    n_out = int(n_in * SAMPLE_RATE_OUT / sample_rate_in)
    real_600 = resample(real, n_out)
    real_600 = real_600 - np.mean(real_600)
    # Apply a Gaussian window in time so the spectrum has a smooth roll-off at the band edges.
    if len(real_600) > 0:
        win = windows.gaussian(len(real_600), std=len(real_600) / 8.0, sym=False)
        win = win / np.max(win)
        real_600 = real_600 * win
    f, p = welch(
        real_600,
        fs=SAMPLE_RATE_OUT,
        nperseg=min(nperseg, len(real_600) // 2),
        scaling="density",
        return_onesided=False,
    )
    # Center frequency axis: -300 to +300 kHz
    f_shift = np.fft.fftshift(f)
    p_shift = np.fft.fftshift(p)
    # Drop the exact DC bin to avoid a vertical notch at 0 kHz.
    if len(f_shift) > 0:
        idx0 = int(np.argmin(np.abs(f_shift)))
        f_shift = np.delete(f_shift, idx0)
        p_shift = np.delete(p_shift, idx0)
    f_shift = f_shift / 1e3
    p_dB = 10 * np.log10(p_shift + 1e-12)
    return f_shift, p_dB


def compute_psd_600k_blackman_harris(data: np.ndarray, sample_rate_in: int = SAMPLE_RATE_IN) -> tuple:
    """Single-FFT PSD with a Blackman-Harris window, to match typical SDR GUI plots.

    Used for the real-noise snapshot so the offline plot resembles the live spectrum display.
    Returns (freq_khz, power_dB).
    """
    n_in = min(len(data), N_SAMPLES_USE)
    data = data[:n_in]
    real = data.real
    if len(real) == 0:
        return np.array([]), np.array([])
    n = len(real)
    win = windows.blackmanharris(n, sym=False)
    win_power = np.sum(win**2) / n
    real_w = (real - np.mean(real)) * win
    spec = np.fft.fftshift(np.fft.fft(real_w))
    freq = np.fft.fftshift(np.fft.fftfreq(n, d=1.0 / sample_rate_in))
    psd = (np.abs(spec) ** 2) / (n * sample_rate_in * win_power + 1e-24)
    # Drop exact DC bin to avoid a narrow notch in the middle.
    idx0 = int(np.argmin(np.abs(freq)))
    freq = np.delete(freq, idx0)
    psd = np.delete(psd, idx0)
    return freq / 1e3, 10 * np.log10(psd + 1e-12)


def save_spectrum_image(freq_khz: np.ndarray, p_dB: np.ndarray, title: str, out_path: str) -> None:
    """Plot spectrum and save as PNG."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 1, figsize=(8, 4))
    ax.plot(freq_khz, p_dB, linewidth=0.8, color="steelblue")
    ax.set_xlim(-BANDWIDTH / 1e3 / 2, BANDWIDTH / 1e3 / 2)
    ax.set_xlabel("Frequency offset (kHz)")
    ax.set_ylabel("Power (dB)")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print("Saved:", out_path)


def main():
    if not os.path.isdir(IQ_DIR):
        print("IQ directory not found:", IQ_DIR, file=sys.stderr)
        sys.exit(2)

    def safe_load(name: str):
        p = os.path.join(IQ_DIR, name)
        return load_cf32(p) if os.path.isfile(p) else None

    # 1) Baseline: Gaussian noise
    f01 = safe_load("01_gaussian_noise_baseline.cf32")
    if f01 is not None and len(f01) >= N_PERSEG:
        f_khz, p_dB = compute_psd_600k(f01)
        save_spectrum_image(
            f_khz, p_dB,
            "Spectrum snapshot: baseline (Gaussian noise), 600 kHz bandwidth",
            os.path.join(IQ_DIR, "spectrum_baseline.png"),
        )
    else:
        print("Skip spectrum_baseline.png (missing or short 01_gaussian_noise_baseline.cf32)", file=sys.stderr)

    # 1b) Synthetic realistic baseline (01b)
    f01b = safe_load("01b_realistic_noise_baseline.cf32")
    if f01b is not None and len(f01b) >= N_PERSEG:
        f_khz, p_dB = compute_psd_600k(f01b)
        save_spectrum_image(
            f_khz, p_dB,
            "Spectrum snapshot: synthetic realistic baseline (01b), 600 kHz bandwidth",
            os.path.join(IQ_DIR, "spectrum_realistic_baseline.png"),
        )
    else:
        print("Skip spectrum_realistic_baseline.png (missing or short 01b)", file=sys.stderr)

    # 2) Unkeyed GDSS with sync pulse: standard GDSS (09) with sync burst (06) embedded
    f09 = safe_load("09_standard_gdss_transmission.cf32")
    f06 = safe_load("06_sync_burst_isolation.cf32")
    if f09 is not None and len(f09) >= N_SAMPLES_USE:
        composite = f09[:N_SAMPLES_USE].copy()
        if f06 is not None and len(f06) > 0:
            pos = len(composite) // 4
            end = min(pos + len(f06), len(composite))
            composite[pos:end] = f06[: end - pos]
        f_khz, p_dB = compute_psd_600k(composite)
        save_spectrum_image(
            f_khz, p_dB,
            "Spectrum snapshot: unkeyed GDSS with sync pulse, 600 kHz bandwidth",
            os.path.join(IQ_DIR, "spectrum_standard_gdss.png"),
        )
    else:
        print("Skip spectrum_standard_gdss.png (missing or short 09)", file=sys.stderr)

    # 3) Keyed GDSS
    f03 = safe_load("03_keyed_gdss_transmission.cf32")
    if f03 is not None and len(f03) >= N_PERSEG:
        f_khz, p_dB = compute_psd_600k(f03)
        save_spectrum_image(
            f_khz, p_dB,
            "Spectrum snapshot: keyed GDSS, 600 kHz bandwidth",
            os.path.join(IQ_DIR, "spectrum_keyed_gdss.png"),
        )
    else:
        print("Skip spectrum_keyed_gdss.png (missing or short 03_keyed_gdss_transmission.cf32)", file=sys.stderr)

    # 4) Real recorded noise (File 08): try iq_files/ then sdr-noise/
    path08 = os.path.join(IQ_DIR, "08_real_noise_with_hardware_artifacts.cf32")
    if not os.path.isfile(path08):
        path08 = os.path.join(IQ_DIR, "08_real_noise_reference.cf32")
    if not os.path.isfile(path08):
        sdr_noise_dir = os.path.join(os.path.dirname(os.path.dirname(IQ_DIR)), "sdr-noise")
        path08 = os.path.join(sdr_noise_dir, "08_real_noise_with_hardware_artifacts.cf32")
    if os.path.isfile(path08):
        f08 = load_cf32(path08)
        if len(f08) >= N_PERSEG:
            rate_08 = SAMPLE_RATE_IN
            env_rate = os.environ.get("REAL_NOISE_SAMPLE_RATE")
            if env_rate is not None:
                try:
                    rate_08 = int(env_rate)
                except ValueError:
                    pass
            if rate_08 != SAMPLE_RATE_IN:
                print("File 08: using sample rate {} Hz (REAL_NOISE_SAMPLE_RATE)".format(rate_08), file=sys.stderr)
            print("File 08: {}".format(path08), file=sys.stderr)
            # For the real recording, use a single Blackman-Harris-windowed FFT so
            # the shape matches the live SDR GUI spectrum.
            f_khz, p_dB = compute_psd_600k_blackman_harris(f08, sample_rate_in=rate_08)
            save_spectrum_image(
                f_khz, p_dB,
                "Spectrum snapshot: real recorded noise (File 08), 600 kHz bandwidth",
                os.path.join(IQ_DIR, "spectrum_real_noise.png"),
            )
        else:
            print("Skip spectrum_real_noise.png (File 08 too short)", file=sys.stderr)
    else:
        print("Skip spectrum_real_noise.png (no 08_real_noise_*.cf32 found)", file=sys.stderr)

    # 5) Realistic noise + unkeyed GDSS (01c), with Gaussian roll-off in plot
    f01c = safe_load("01c_realistic_noise_plus_standard_gdss.cf32")
    if f01c is not None and len(f01c) >= N_PERSEG:
        f_khz, p_dB = compute_psd_600k(f01c)
        save_spectrum_image(
            f_khz, p_dB,
            "Spectrum snapshot: realistic noise + unkeyed GDSS, 600 kHz bandwidth",
            os.path.join(IQ_DIR, "spectrum_realistic_plus_standard_gdss.png"),
        )
    else:
        print("Skip spectrum_realistic_plus_standard_gdss.png (missing or short 01c)", file=sys.stderr)

    # 6) Realistic noise + keyed GDSS (01d), with Gaussian roll-off in plot
    f01d = safe_load("01d_realistic_noise_plus_keyed_gdss.cf32")
    if f01d is not None and len(f01d) >= N_PERSEG:
        f_khz, p_dB = compute_psd_600k(f01d)
        save_spectrum_image(
            f_khz, p_dB,
            "Spectrum snapshot: realistic noise + keyed GDSS, 600 kHz bandwidth",
            os.path.join(IQ_DIR, "spectrum_realistic_plus_keyed_gdss.png"),
        )
    else:
        print("Skip spectrum_realistic_plus_keyed_gdss.png (missing or short 01d)", file=sys.stderr)


if __name__ == "__main__":
    main()
