#!/usr/bin/env python3
"""
Generate 3x3 comparison plot for gr-k-gdss IQ test files.
Output: iq_files/iq_comparison.png. Requires: numpy, scipy, matplotlib.
"""

import os
import sys

import numpy as np
from scipy.signal import welch

IQ_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iq_files")
SAMPLE_RATE = 500_000


def load_cf32(path: str) -> np.ndarray:
    return np.fromfile(path, dtype=np.complex64)


def main():
    if not os.path.isdir(IQ_DIR):
        print("IQ directory not found:", IQ_DIR, file=sys.stderr)
        sys.exit(2)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib required for plot_iq_comparison.py", file=sys.stderr)
        sys.exit(1)

    def safe_load(name):
        p = os.path.join(IQ_DIR, name)
        return load_cf32(p) if os.path.isfile(p) else None

    f1 = safe_load("01_gaussian_noise_baseline.cf32")
    f3 = safe_load("03_keyed_gdss_transmission.cf32")
    f4 = safe_load("04_keyed_gdss_despread_correct_key.cf32")
    f5 = safe_load("05_keyed_gdss_despread_wrong_key.cf32")
    f6 = safe_load("06_sync_burst_isolation.cf32")

    fig, axes = plt.subplots(3, 3, figsize=(14, 12))
    fig.suptitle(
        "gr-k-gdss Statistical Validation - Files 1 and 3 should be visually "
        "indistinguishable in rows 1 and 2 if GDSS masking is working correctly.",
        fontsize=11,
    )
    n_hist = 100_000
    n_ac = 500
    n_psd = 4096

    # Row 1 - Amplitude histograms
    for ax, data, title in [
        (axes[0, 0], f1, "File 1 (noise baseline)"),
        (axes[0, 1], f3, "File 3 (keyed GDSS transmission)"),
        (axes[0, 2], f5, "File 5 (wrong-key despread)"),
    ]:
        if data is not None:
            d = data[:n_hist]
            ax.hist(d.real, bins=150, density=True, alpha=0.7, label="I", color="steelblue")
            ax.hist(d.imag, bins=150, density=True, alpha=0.5, label="Q", color="tomato")
        ax.set_title(title)
        ax.set_xlabel("Amplitude")
        ax.legend()
        ax.grid(True, alpha=0.3)

    # Row 2 - PSD
    for ax, data, title in [
        (axes[1, 0], f1, "File 1 (noise baseline)"),
        (axes[1, 1], f3, "File 3 (keyed GDSS transmission)"),
        (axes[1, 2], f6, "File 6 (sync burst)"),
    ]:
        if data is not None and len(data) >= n_psd:
            f, p = welch(data.real, fs=SAMPLE_RATE, nperseg=n_psd, scaling="density")
            ax.plot(f / 1e3, 10 * np.log10(p + 1e-12), linewidth=0.8, color="steelblue")
        ax.set_title(title)
        ax.set_xlabel("Frequency offset (kHz)")
        ax.set_ylabel("Power (dB)")
        ax.grid(True, alpha=0.3)

    # Row 3 - Autocorrelation
    for ax, data, title in [
        (axes[2, 0], f1, "File 1 (noise baseline)"),
        (axes[2, 1], f3, "File 3 (keyed GDSS transmission)"),
        (axes[2, 2], f4, "File 4 (correct-key despread)"),
    ]:
        if data is not None and len(data) >= n_ac:
            chunk = data.real[: 50_000]
            ac = np.correlate(chunk - chunk.mean(), chunk - chunk.mean(), mode="full")
            ac = ac[len(ac) // 2 : len(ac) // 2 + n_ac + 1]
            if ac[0] != 0:
                ac = ac / ac[0]
            ax.plot(ac[1:], linewidth=0.8, color="steelblue")
        ax.set_title(title)
        ax.set_xlabel("Lag (samples)")
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    out_path = os.path.join(IQ_DIR, "iq_comparison.png")
    plt.savefig(out_path, dpi=150)
    plt.close()
    print("Saved:", out_path)


if __name__ == "__main__":
    main()
