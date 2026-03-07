#!/usr/bin/env python3
"""
Generate comparison plots for gr-k-gdss IQ test files.
Output: iq_files/iq_comparison.png (3x3), iq_files/iq_comparison_vs_standard.png (4x3).
Requires: numpy, scipy, matplotlib.
"""

import os
import sys

import numpy as np
from scipy.signal import welch

IQ_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iq_files")
SAMPLE_RATE = 500_000
SPREADING_N = 256


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

    # Row-1 amplitude histograms: same File 1 scale in both figures (0.07 upper margin).
    # File 09's Q=0 spike would dominate a global max and make File 1 look flat; use File-1-only scale for col 1.
    bins_r1 = np.linspace(-5, 5, 151)
    UPPER_MARGIN = 0.07

    def max_density(data, bins):
        if data is None:
            return 0.0
        d = data[:n_hist]
        hi, _ = np.histogram(d.real, bins=bins, density=True)
        hq, _ = np.histogram(d.imag, bins=bins, density=True)
        return max(float(np.max(hi)), float(np.max(hq)))

    ymax_f1 = max_density(f1, bins_r1) if f1 is not None else 0.0
    y_upper_file1 = ymax_f1 * (1.0 + UPPER_MARGIN)  # same File 1 scale in both figures
    ymax_fig1 = max(ymax_f1, max_density(f3, bins_r1), max_density(f5, bins_r1))
    y_upper_fig1 = ymax_fig1 * (1.0 + UPPER_MARGIN)

    # Row 1 - Amplitude histograms (fig 1: col1 uses File-1 scale so it matches fig 2; cols 2-3 use row max so nothing clips)
    for col, (ax, data, title) in enumerate([
        (axes[0, 0], f1, "File 1 (noise baseline)"),
        (axes[0, 1], f3, "File 3 (keyed GDSS transmission)"),
        (axes[0, 2], f5, "File 5 (wrong-key despread)"),
    ]):
        if data is not None:
            d = data[:n_hist]
            ax.hist(d.real, bins=bins_r1, density=True, alpha=0.7, label="I", color="steelblue")
            ax.hist(d.imag, bins=bins_r1, density=True, alpha=0.5, label="Q", color="tomato")
        ax.set_xlim(-5, 5)
        ax.set_ylim(0, y_upper_file1 if col == 0 else y_upper_fig1)
        ax.set_title(title)
        ax.set_xlabel("Amplitude")
        ax.legend()
        ax.grid(True, alpha=0.3)

    # Row 2 - PSD (exclude first and last bins to avoid vertical lines at edges)
    for ax, data, title in [
        (axes[1, 0], f1, "File 1 (noise baseline)"),
        (axes[1, 1], f3, "File 3 (keyed GDSS transmission)"),
        (axes[1, 2], f6, "File 6 (sync burst)"),
    ]:
        if data is not None and len(data) >= n_psd:
            real_dc_blocked = data.real - np.mean(data.real)
            f, p = welch(real_dc_blocked, fs=SAMPLE_RATE, nperseg=n_psd, scaling="density")
            ax.plot(f[1:-1] / 1e3, 10 * np.log10(p[1:-1] + 1e-12), linewidth=0.8, color="steelblue")
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

    # Second plot: 4x3 keyed vs standard GDSS comparison (requires 09, 12, 13 from generator)
    f9 = safe_load("09_standard_gdss_transmission.cf32")
    f12 = safe_load("12_standard_gdss_crosscorr_A_vs_B.cf32")
    f13 = safe_load("13_keyed_gdss_crosscorr_A_vs_B.cf32")
    missing = [n for n, d in [("09", f9), ("12", f12), ("13", f13)] if d is None]
    if f9 is not None and f12 is not None and f13 is not None:
        fig2, ax2 = plt.subplots(4, 3, figsize=(14, 16))
        fig2.suptitle(
            "gr-k-gdss vs Standard GDSS - Empirical Comparison\n"
            "Rows 1-2: Both indistinguishable from noise (both achieve LPD)\n"
            "Row 3: Standard GDSS sync bursts cross-session detectable - keyed are not\n"
            "Row 4: Keyed GDSS requires correct key - standard GDSS does not",
            fontsize=10,
        )
        n_hist = 100_000
        n_psd = 4096
        n_ac = 500

        # Row 1 - File 01 same scale as in first figure (y_upper_file1); cols 2-3 scale so File 09 spike fits
        ymax_fig2 = max(ymax_f1, max_density(f3, bins_r1), max_density(f9, bins_r1))
        y_upper_fig2 = ymax_fig2 * (1.0 + UPPER_MARGIN)
        for col, (ax, data, title) in enumerate([
            (ax2[0, 0], f1, "File 01 (noise baseline)"),
            (ax2[0, 1], f3, "File 03 (keyed GDSS)"),
            (ax2[0, 2], f9, "File 09 (standard GDSS)"),
        ]):
            if data is not None:
                d = data[:n_hist]
                ax.hist(d.real, bins=bins_r1, density=True, alpha=0.7, label="I", color="steelblue")
                ax.hist(d.imag, bins=bins_r1, density=True, alpha=0.5, label="Q", color="tomato")
            ax.set_xlim(-5, 5)
            ax.set_ylim(0, y_upper_file1 if col == 0 else y_upper_fig2)
            ax.set_title(title)
            ax.set_xlabel("Amplitude")
            ax.legend()
            ax.grid(True, alpha=0.3)

        # Row 2 - PSD (File 01, 03, 09)
        for ax, data, title in [
            (ax2[1, 0], f1, "File 01 (noise baseline)"),
            (ax2[1, 1], f3, "File 03 (keyed GDSS)"),
            (ax2[1, 2], f9, "File 09 (standard GDSS)"),
        ]:
            if data is not None and len(data) >= n_psd:
                real_dc_blocked = data.real - np.mean(data.real)
                freq, p = welch(real_dc_blocked, fs=SAMPLE_RATE, nperseg=n_psd, scaling="density")
                ax.plot(freq[1:-1] / 1e3, 10 * np.log10(p[1:-1] + 1e-12), linewidth=0.8, color="steelblue")
            ax.set_title(title)
            ax.set_xlabel("Frequency offset (kHz)")
            ax.set_ylabel("Power (dB)")
            ax.grid(True, alpha=0.3)

        # Row 3 - Sync burst cross-correlation (12, 13, overlay)
        cc12 = f12.real if len(f12) > 0 else np.array([0.0])
        cc13 = f13.real if len(f13) > 0 else np.array([0.0])
        ax2[2, 0].plot(cc12, color="red", linewidth=0.8)
        ax2[2, 0].set_title("File 12 (standard GDSS cross-corr)")
        ax2[2, 0].set_xlabel("Lag")
        ax2[2, 0].annotate("DETECTABLE REPEATING PATTERN", xy=(0.5, 0.95), xycoords="axes fraction", ha="center", fontsize=9)
        ax2[2, 0].grid(True, alpha=0.3)
        ax2[2, 1].plot(cc13, color="green", linewidth=0.8)
        ax2[2, 1].set_title("File 13 (keyed GDSS cross-corr)")
        ax2[2, 1].set_xlabel("Lag")
        ax2[2, 1].annotate("NO DETECTABLE STRUCTURE", xy=(0.5, 0.95), xycoords="axes fraction", ha="center", fontsize=9)
        ax2[2, 1].grid(True, alpha=0.3)
        ax2[2, 2].plot(cc12, color="red", alpha=0.8, linewidth=0.6, label="Standard")
        ax2[2, 2].plot(cc13, color="green", alpha=0.8, linewidth=0.6, label="Keyed")
        ax2[2, 2].set_title("Overlay (red=standard, green=keyed)")
        ax2[2, 2].set_xlabel("Lag")
        peak12 = float(np.max(np.abs(cc12))) if len(cc12) > 0 else 0
        peak13 = float(np.max(np.abs(cc13))) if len(cc13) > 0 else 0
        ratio = peak12 / peak13 if peak13 > 0 else 0
        ax2[2, 2].text(0.5, 0.95, "Peak std: {:.4f}  Peak keyed: {:.4f}\nImprovement: {:.1f}x".format(peak12, peak13, ratio), transform=ax2[2, 2].transAxes, ha="center", fontsize=9, verticalalignment="top")
        ax2[2, 2].legend()
        ax2[2, 2].grid(True, alpha=0.3)

        # Row 4 - Despreading
        if f4 is not None and len(f4) >= n_ac:
            chunk4 = f4.real[: 50_000]
            ac4 = np.correlate(chunk4 - chunk4.mean(), chunk4 - chunk4.mean(), mode="full")
            ac4 = ac4[len(ac4) // 2 : len(ac4) // 2 + n_ac + 1]
            if ac4[0] != 0:
                ac4 = ac4 / ac4[0]
            ax2[3, 0].plot(ac4[1:], linewidth=0.8, color="steelblue")
        ax2[3, 0].set_title("File 04 (keyed correct-key despread)")
        ax2[3, 0].set_xlabel("Lag (samples)")
        ax2[3, 0].grid(True, alpha=0.3)
        if f5 is not None:
            d5 = f5.real[:n_hist]
            ax2[3, 1].hist(d5, bins=150, density=True, color="steelblue", alpha=0.7)
        ax2[3, 1].set_xlim(-5, 5)
        ax2[3, 1].set_title("File 05 (keyed wrong-key despread)")
        ax2[3, 1].set_xlabel("Amplitude")
        ax2[3, 1].grid(True, alpha=0.3)
        if f9 is not None and len(f9) >= SPREADING_N:
            n_sym9 = len(f9) // SPREADING_N
            despread9 = f9[: n_sym9 * SPREADING_N].reshape(n_sym9, SPREADING_N).mean(axis=1)
            if len(despread9) >= n_ac:
                ac9 = np.correlate(despread9.real - despread9.real.mean(), despread9.real - despread9.real.mean(), mode="full")
                ac9 = ac9[len(ac9) // 2 : len(ac9) // 2 + n_ac + 1]
                if ac9[0] != 0:
                    ac9 = ac9 / ac9[0]
                ax2[3, 2].plot(ac9[1:], linewidth=0.8, color="steelblue")
        ax2[3, 2].set_title("Despread File 09 (no key needed)")
        ax2[3, 2].set_xlabel("Lag (samples)")
        ax2[3, 2].grid(True, alpha=0.3)

        plt.tight_layout()
        out_path2 = os.path.join(IQ_DIR, "iq_comparison_vs_standard.png")
        plt.savefig(out_path2, dpi=150)
        plt.close()
        print("Saved:", out_path2)
    else:
        print("Skipping iq_comparison_vs_standard.png (missing file(s): {})".format(", ".join(missing)), file=sys.stderr)


if __name__ == "__main__":
    main()
