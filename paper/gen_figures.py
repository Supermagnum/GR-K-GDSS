#!/usr/bin/env python3
"""Generate all figures for KGDSS academic paper (matplotlib)."""
from __future__ import annotations

import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
from scipy import special
from scipy.stats import norm, rayleigh

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures")
os.makedirs(FIG, exist_ok=True)
BER_MC_NPZ = os.path.join(FIG, "ber_mc_results.npz")

MDPI_BLUE = "#004E8F"
RED = "#C44E52"
GREEN = "#55A868"
ORANGE = "#FFA500"


def fig1_block_diagram():
    fig, ax = plt.subplots(figsize=(10, 5), dpi=150)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")

    def box(x, y, w, h, text, color):
        r = FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.02", linewidth=1.2,
            edgecolor="black", facecolor=color, alpha=0.85,
        )
        ax.add_patch(r)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=7, wrap=True)

    def arrow(x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", lw=1.2, color="black"))

    # TX chain (top)
    y1 = 4.2
    box(0.3, y1, 0.9, 0.55, "Mic", "#E8F4FC")
    box(1.4, y1, 0.9, 0.55, "Codec2\n2400 bps", "#E8F4FC")
    box(2.5, y1, 1.1, 0.55, "ChaCha20-\nPoly1305", "#FFE8CC")
    box(3.8, y1, 0.9, 0.55, "SOQPSK\nmod", "#E8F4FC")
    box(4.9, y1, 1.0, 0.55, "K-GDSS\nSpreader", MDPI_BLUE)
    plt.setp(ax.texts[-1], color="white", fontweight="bold")
    box(6.1, y1, 1.0, 0.55, "Channel /\nSDR sink", "#DDEEFF")
    for i, xs in enumerate([(1.2, y1 + 0.28), (2.3, y1 + 0.28), (3.4, y1 + 0.28), (4.5, y1 + 0.28), (5.6, y1 + 0.28)]):
        pass
    arrow(1.2, y1 + 0.28, 1.4, y1 + 0.28)
    arrow(2.3, y1 + 0.28, 2.5, y1 + 0.28)
    arrow(3.6, y1 + 0.28, 3.8, y1 + 0.28)
    arrow(4.7, y1 + 0.28, 4.9, y1 + 0.28)
    arrow(5.9, y1 + 0.28, 6.1, y1 + 0.28)

    # Key path (bottom)
    y0 = 1.5
    box(0.3, y0, 1.0, 0.55, "Nitrokey /\nGnuPG key", "#FFE8CC")
    box(1.5, y0, 0.85, 0.55, "ECDH\nBrainpool", "#FFE8CC")
    box(2.5, y0, 0.85, 0.55, "HKDF\n4 subkeys", "#FFE8CC")
    box(3.5, y0, 1.2, 0.55, "Kernel\nkeyring", "#E8E8E8")
    box(4.9, y0, 1.0, 0.55, "Key\nInjector", MDPI_BLUE)
    plt.setp(ax.texts[-1], color="white", fontweight="bold")
    arrow(1.3, y0 + 0.28, 1.5, y0 + 0.28)
    arrow(2.35, y0 + 0.28, 2.5, y0 + 0.28)
    arrow(3.35, y0 + 0.28, 3.5, y0 + 0.28)
    arrow(4.7, y0 + 0.28, 4.9, y0 + 0.28)
    # dashed up to spreader
    ax.plot([5.4, 5.4, 5.4], [y0 + 0.55, 3.9, y1], "k--", lw=1)
    ax.annotate("", xy=(5.4, y1), xytext=(5.4, 3.9),
                arrowprops=dict(arrowstyle="->", lw=1, color="black", linestyle="--"))

    ax.set_title("Figure 1. Keyed GDSS transmit chain and key path (after tx_example_kgdss.grc)", fontsize=9, fontweight="bold", color=MDPI_BLUE)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig1_block_diagram.png"), bbox_inches="tight")
    plt.close(fig)


def fig2_key_derivation():
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 8)
    ax.axis("off")

    def box(x, y, w, h, t, c="#E8F4FC"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02", facecolor=c, edgecolor="black"))
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=7)

    box(0.5, 6.5, 1.8, 0.7, "TX Brainpool\nP256r1 keypair", "#DDEEFF")
    box(3.0, 6.5, 1.8, 0.7, "RX Brainpool\nP256r1 keypair", "#DDEEFF")
    ax.annotate("", xy=(5.0, 6.85), xytext=(2.3, 6.85), arrowprops=dict(arrowstyle="->", lw=1))
    ax.annotate("", xy=(4.8, 6.85), xytext=(3.0, 6.85), arrowprops=dict(arrowstyle="->", lw=1))
    box(4.0, 5.2, 2.0, 0.7, "ECDH shared\nsecret", "#FFE8CC")
    ax.plot([2.4, 5.0], [6.5, 5.9], "k-", lw=0.8)
    ax.plot([3.9, 5.0], [6.5, 5.9], "k-", lw=0.8)
    box(3.8, 3.8, 2.4, 0.7, "HKDF-SHA256\n(RFC 5869)", "#FFE8CC")
    ax.annotate("", xy=(5.0, 3.8), xytext=(5.0, 5.2), arrowprops=dict(arrowstyle="->", lw=1))

    infos = [
        (0.3, 2.2, "payload_enc\npayload-chacha20poly1305-v1"),
        (2.6, 2.2, "gdss_masking\ngdss-chacha20-masking-v1"),
        (5.0, 2.2, "sync_pn\nsync-dsss-pn-sequence-v1"),
        (7.3, 2.2, "sync_timing\nsync-burst-timing-offset-v1"),
    ]
    for x, y, t in infos:
        box(x, y, 2.0, 0.85, t, "#E8FFE8")
        ax.plot([5.0, x + 1.0], [3.8, y + 0.85], "k-", lw=0.6)

    ax.set_title("Figure 2. Session key derivation hierarchy (from session_key_derivation.py)", fontsize=9, fontweight="bold", color=MDPI_BLUE)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig2_key_derivation.png"), bbox_inches="tight")
    plt.close(fig)


def fig3_state_machine():
    fig, ax = plt.subplots(figsize=(6, 3.5), dpi=150)
    ax.set_xlim(0, 8)
    ax.set_ylim(0, 4)
    ax.axis("off")
    r = 0.9

    def state(x, y, name):
        circ = plt.Circle((x, y), r, facecolor="#E8F4FC", edgecolor="black", lw=1.5)
        ax.add_patch(circ)
        ax.text(x, y, name, ha="center", va="center", fontsize=8, fontweight="bold")

    state(1.5, 2, "ACQUISITION")
    state(4.0, 2, "TRACKING")
    state(6.5, 2, "LOCKED")

    ax.annotate("", xy=(2.4, 2), xytext=(2.1, 2), arrowprops=dict(arrowstyle="->", lw=1.2))
    ax.text(2.25, 2.35, "lock", fontsize=6)
    ax.annotate("", xy=(5.4, 2), xytext=(4.9, 2), arrowprops=dict(arrowstyle="->", lw=1.2))
    ax.text(5.0, 2.35, "lock", fontsize=6)
    ax.annotate("", xy=(4.0, 1.1), xytext=(1.5, 1.1), arrowprops=dict(arrowstyle="->", lw=1, linestyle="--"))
    ax.annotate("", xy=(4.0, 1.1), xytext=(6.5, 1.1), arrowprops=dict(arrowstyle="<-", lw=1, linestyle="--"))
    ax.text(4, 0.75, "lock loss (counter to 0)", ha="center", fontsize=6)

    ax.set_title("Figure 3. Despreader sync state machine (kgdss_despreader_cc_impl)", fontsize=9, fontweight="bold", color=MDPI_BLUE)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig3_state_machine.png"), bbox_inches="tight")
    plt.close(fig)


def fig4_sync_burst():
    fig, ax = plt.subplots(figsize=(8, 3), dpi=150)
    t = np.linspace(0, 1, 500)
    # Standard: fixed position
    std = np.zeros_like(t)
    pos_std = 0.35
    w = 0.04
    std[(t > pos_std) & (t < pos_std + w)] = 1.0
    ax.fill_between(t, 0, std, step="pre", alpha=0.5, color=RED, label="Standard GDSS (fixed PN / position)")
    # Keyed: offset + envelope
    pos_k = 0.55
    env = np.exp(-((t - (pos_k + w / 2)) / (w / 3)) ** 2 / 2)
    env = np.clip(env, 0, 1)
    ax.plot(t, env * 0.95, color=GREEN, lw=2, label="Keyed GDSS (session offset + Gaussian envelope)")
    ax.set_xlabel("Time (arbitrary units)")
    ax.set_ylabel("Relative amplitude")
    ax.legend(loc="upper right", fontsize=7)
    ax.set_title("Figure 4. Sync burst timing: standard vs keyed (conceptual)", fontsize=9, fontweight="bold", color=MDPI_BLUE)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig4_sync_burst.png"), bbox_inches="tight")
    plt.close(fig)


def fig5_bar_cross_session():
    fig, ax = plt.subplots(figsize=(5, 4), dpi=150)
    labels = ["Standard GDSS", "Keyed GDSS"]
    vals = [1.0000, 0.1028]
    colors = [RED, GREEN]
    bars = ax.bar(labels, vals, color=colors, edgecolor="black", width=0.5)
    ax.set_ylabel("Cross-session correlation coefficient")
    ax.set_ylim(0, 1.15)
    ax.axhline(0.15, color="gray", linestyle=":", lw=1)
    ax.text(1.15, 0.16, "simulation threshold (keyed)", fontsize=7, color="gray")
    for b, v, lab in zip(bars, vals, ["VULNERABLE", "PROTECTED"]):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.03, f"{v:.4f}\n{lab}", ha="center", fontsize=8, fontweight="bold")
    ax.annotate("", xy=(1, 0.55), xytext=(0, 0.55), arrowprops=dict(arrowstyle="<->", color="black", lw=1))
    ax.text(0.5, 0.58, "~9.7x reduction\n(docs/TEST_RESULTS.md)", ha="center", fontsize=8)
    ax.set_title("Figure 5. Cross-session sync burst correlation (gr-k-gdss IQ generator)", fontsize=9, fontweight="bold", color=MDPI_BLUE)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig5_cross_session_bar.png"), bbox_inches="tight")
    plt.close(fig)


def fig6_histograms():
    rng = np.random.default_rng(42)
    n = 8000
    base = rng.standard_normal(n)
    keyed = rng.standard_normal(n) * np.abs(rng.standard_normal(n))
    wrong = rng.standard_normal(n)

    fig, axes = plt.subplots(1, 3, figsize=(10, 3.2), dpi=150, sharey=True)
    titles = [
        "(a) 01_gaussian_noise_baseline.cf32 (simulated)",
        "(b) 03_keyed_gdss_transmission.cf32 (simulated I)",
        "(c) 05_keyed_gdss_despread_wrong_key.cf32 (simulated)",
    ]
    datas = [base, keyed, wrong]
    for ax, data, tit in zip(axes, datas, titles):
        ax.hist(data, bins=50, density=True, alpha=0.6, color=MDPI_BLUE, edgecolor="white")
        xs = np.linspace(-4, 4, 200)
        ax.plot(xs, norm.pdf(xs), "r-", lw=1.5, label="N(0,1) PDF")
        ax.set_title(tit, fontsize=7)
        ax.set_xlabel("Amplitude (I)")
        ax.legend(fontsize=6)
    axes[0].set_ylabel("Density")
    fig.suptitle("Figure 6. IQ amplitude histogram comparison (synthetic stand-in; full tests use recorded .cf32)", fontsize=9, fontweight="bold", color=MDPI_BLUE, y=1.02)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig6_histograms.png"), bbox_inches="tight")
    plt.close(fig)


def ber_dsss_theory(snr_db: np.ndarray, n: int) -> np.ndarray:
    """Shakeel-style DSSS BER: 0.5 * erfc(sqrt(N * Es/N0 / 2)), linear Es/N0."""
    esn0 = 10 ** (snr_db / 10.0)
    x = np.sqrt(n * esn0 / 2.0)
    return 0.5 * special.erfc(x)


def ber_gdss_family(snr_db: np.ndarray, n: int, penalty_db: float) -> np.ndarray:
    """Approximate family as DSSS with effective SNR penalty (Monte Carlo cost)."""
    return ber_dsss_theory(snr_db - penalty_db, n)


def _load_ber_mc_npz():
    if not os.path.isfile(BER_MC_NPZ):
        return None
    return np.load(BER_MC_NPZ, allow_pickle=False)


def _ber_clip_plot(y: np.ndarray) -> np.ndarray:
    return np.maximum(np.asarray(y, dtype=np.float64), 1e-12)


def fig7_awgn_ber_fallback():
    snr = np.arange(-20, 6, 1.0)
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
    styles = {"64": ("--", 1.0), "128": ("--", 0.7), "256": ("--", 0.4)}
    for n, (ls, al) in styles.items():
        Ni = int(n)
        ax.semilogy(snr, np.maximum(ber_dsss_theory(snr, Ni), 1e-8), ls, color="black", alpha=al, lw=1.2, label=f"DSSS theory N={Ni}")
    for n, lw in [("64", 1.0), ("128", 0.8), ("256", 0.6)]:
        Ni = int(n)
        ax.semilogy(snr, np.maximum(ber_gdss_family(snr, Ni, 1.2), 1e-8), "-", color=MDPI_BLUE, lw=lw, label=f"Std GDSS (approx. +1.2 dB) N={Ni}")
    for n, lw in [("64", 1.0), ("128", 0.8), ("256", 0.6)]:
        Ni = int(n)
        ax.semilogy(snr, np.maximum(ber_gdss_family(snr, Ni, 3.2), 1e-8), "-.", color=ORANGE, lw=lw, label=f"Keyed GDSS (approx. +3.2 dB) N={Ni}")
    ax.set_xlabel(r"$E_b/N_0$ (dB) (fallback parametric model)")
    ax.set_ylabel("BER")
    ax.set_ylim(1e-6, 0.5)
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=5, loc="upper right", ncol=2)
    ax.set_title("Figure 7. AWGN BER (fallback: run ber_simulation.py for MC curves)", fontsize=9, fontweight="bold", color=MDPI_BLUE)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig7_awgn_ber.png"), bbox_inches="tight")
    plt.close(fig)


def fig7_awgn_ber():
    d = _load_ber_mc_npz()
    if d is None:
        print("gen_figures: ber_mc_results.npz not found; Figure 7 uses parametric fallback.")
        fig7_awgn_ber_fallback()
        return
    snr = np.asarray(d["snr_db"])
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
    styles = [(64, "--", 1.0), (128, "--", 0.7), (256, "--", 0.4)]
    for n, ls, al in styles:
        ax.semilogy(snr, _ber_clip_plot(d[f"dsss_{n}"]), ls, color="black", alpha=al, lw=1.2, label=f"DSSS theory N={n}")
    lw_n = [(64, 1.0), (128, 0.8), (256, 0.6)]
    for n, lw in lw_n:
        ax.semilogy(snr, _ber_clip_plot(d[f"std_{n}"]), "-", color=MDPI_BLUE, lw=lw, label=f"Standard GDSS (MC) N={n}")
    for n, lw in lw_n:
        ax.semilogy(snr, _ber_clip_plot(d[f"keyed_{n}"]), "-.", color=ORANGE, lw=lw, label=f"Keyed GDSS (MC) N={n}")
    nbits = int(d["meta_bits"][0]) if "meta_bits" in d.files else 0
    ax.set_xlabel(r"$E_b/N_0$ (dB)")
    ax.set_ylabel("BER")
    ax.set_ylim(1e-6, 0.5)
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=5, loc="upper right", ncol=2)
    sub = f" ({nbits} simulated bits per SNR per curve)" if nbits else ""
    ax.set_title(f"Figure 7. AWGN: DSSS (Shakeel eq.1) vs standard vs keyed GDSS (Monte Carlo){sub}", fontsize=9, fontweight="bold", color=MDPI_BLUE)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig7_awgn_ber.png"), bbox_inches="tight")
    plt.close(fig)


def fig8_vhf_fallback():
    snr = np.arange(-15, 11, 1.0)
    base = ber_gdss_family(snr, 256, 3.2)

    def rayleigh_ber(snr_db, fade_sigma_db):
        return np.minimum(base * 10 ** (fade_sigma_db / 10), 0.49)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 3.8), dpi=150, sharey=True)
    ax1.semilogy(snr, np.maximum(base, 1e-7), "k--", lw=1, label="AWGN keyed ref.")
    ax1.semilogy(snr, np.maximum(rayleigh_ber(snr, 2.5), 1e-7), "-", color=MDPI_BLUE, lw=1.2, label="SOQPSK Mode 1 (illustr.)")
    ax1.semilogy(snr, np.maximum(rayleigh_ber(snr, 1.8), 1e-7), "-.", color=GREEN, lw=1.2, label="SOQPSK Mode 2 (illustr.)")
    ax1.set_title("Pedestrian (50 Hz Doppler, stylised loss)")
    ax1.set_xlabel("SNR (dB)")
    ax1.set_ylabel("BER")
    ax1.grid(True, which="both", alpha=0.3)
    ax1.legend(fontsize=6)
    ax2.semilogy(snr, np.maximum(base, 1e-7), "k--", lw=1, label="AWGN keyed ref.")
    ax2.semilogy(snr, np.maximum(rayleigh_ber(snr, 4.0), 1e-7), "-", color=MDPI_BLUE, lw=1.2, label="Mode 1")
    ax2.semilogy(snr, np.maximum(rayleigh_ber(snr, 3.2), 1e-7), "-.", color=GREEN, lw=1.2, label="Mode 2")
    ax2.set_title("Vehicular (200 Hz Doppler, stylised loss)")
    ax2.set_xlabel("SNR (dB)")
    ax2.grid(True, which="both", alpha=0.3)
    ax2.legend(fontsize=6)
    fig.suptitle("Figure 8. VHF (fallback): run ber_simulation.py for MC", fontsize=9, fontweight="bold", color=MDPI_BLUE)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig8_vhf_ber.png"), bbox_inches="tight")
    plt.close(fig)


def fig8_vhf():
    d = _load_ber_mc_npz()
    if d is None or "vhf_ped_50_m1_unc" not in d.files:
        print("gen_figures: missing VHF arrays in npz; Figure 8 uses parametric fallback.")
        fig8_vhf_fallback()
        return
    snr = np.asarray(d["snr_db"])
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 3.8), dpi=150, sharey=True)
    ax1.semilogy(snr, _ber_clip_plot(d["vhf_ped_50_m1_unc"]), "-", color=MDPI_BLUE, lw=1.2, label="Mode 1 uncoded")
    ax1.semilogy(snr, _ber_clip_plot(d["vhf_ped_50_m1_coded"]), "--", color=MDPI_BLUE, lw=1.0, alpha=0.85, label="Mode 1 + LDPC r=1/2")
    ax1.semilogy(snr, _ber_clip_plot(d["vhf_ped_50_m2_unc"]), "-.", color=GREEN, lw=1.2, label="Mode 2 uncoded")
    ax1.semilogy(snr, _ber_clip_plot(d["vhf_ped_50_m2_coded"]), ":", color=GREEN, lw=1.5, label="Mode 2 + LDPC r=1/2")
    ax1.set_title("Pedestrian, max Doppler 50 Hz (Rayleigh + phase walk)")
    ax1.set_xlabel(r"$E_b/N_0$ (dB)")
    ax1.set_ylabel("BER")
    ax1.grid(True, which="both", alpha=0.3)
    ax1.legend(fontsize=5, loc="upper right")
    ax2.semilogy(snr, _ber_clip_plot(d["vhf_veh_200_m1_unc"]), "-", color=MDPI_BLUE, lw=1.2, label="Mode 1 uncoded")
    ax2.semilogy(snr, _ber_clip_plot(d["vhf_veh_200_m1_coded"]), "--", color=MDPI_BLUE, lw=1.0, alpha=0.85, label="Mode 1 + LDPC r=1/2")
    ax2.semilogy(snr, _ber_clip_plot(d["vhf_veh_200_m2_unc"]), "-.", color=GREEN, lw=1.2, label="Mode 2 uncoded")
    ax2.semilogy(snr, _ber_clip_plot(d["vhf_veh_200_m2_coded"]), ":", color=GREEN, lw=1.5, label="Mode 2 + LDPC r=1/2")
    ax2.set_title("Vehicular, max Doppler 200 Hz")
    ax2.set_xlabel(r"$E_b/N_0$ (dB)")
    ax2.grid(True, which="both", alpha=0.3)
    ax2.legend(fontsize=5, loc="upper right")
    nbits = int(d["meta_bits"][0]) if "meta_bits" in d.files else 0
    sub = f", N=256, {nbits} bits/SNR" if nbits else ", N=256"
    fig.suptitle(f"Figure 8. VHF land mobile (simplified ITU-R P.1406-style Rayleigh){sub}", fontsize=9, fontweight="bold", color=MDPI_BLUE)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig8_vhf_ber.png"), bbox_inches="tight")
    plt.close(fig)


def fig9_hf_fallback():
    snr = np.arange(-18, 8, 1.0)
    uncoded = ber_gdss_family(snr, 256, 3.2)
    coded = ber_gdss_family(snr - 5.0, 256, 3.2)
    fig, ax = plt.subplots(figsize=(7, 4), dpi=150)
    channels = [
        ("AWGN", uncoded, 1.0),
        ("Good HF", uncoded * 3, 0.85),
        ("Poor HF", uncoded * 12, 0.7),
        ("Disturbed HF", uncoded * 40, 0.55),
    ]
    for name, curve, a in channels:
        ax.semilogy(snr, np.maximum(curve, 1e-7), "-", lw=1.2, alpha=a, label=f"{name} uncoded")
    ax.semilogy(snr, np.maximum(coded, 1e-7), "k--", lw=2, label="Keyed + LDPC r=1/2 (illustr. +5 dB)")
    ax.set_xlabel("SNR (dB)")
    ax.set_ylabel("BER")
    ax.set_ylim(1e-6, 0.5)
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=6)
    ax.set_title("Figure 9. HF (fallback): run ber_simulation.py for MC", fontsize=9, fontweight="bold", color=MDPI_BLUE)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig9_hf_ber.png"), bbox_inches="tight")
    plt.close(fig)


def fig9_hf():
    d = _load_ber_mc_npz()
    if d is None or "hf_AWGN_std_unc" not in d.files:
        print("gen_figures: missing HF arrays in npz; Figure 9 uses parametric fallback.")
        fig9_hf_fallback()
        return
    snr = np.asarray(d["snr_db"])
    fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=150)
    profiles = ["AWGN", "Good", "Poor", "Disturbed"]
    colors = {"AWGN": "black", "Good": MDPI_BLUE, "Poor": ORANGE, "Disturbed": RED}
    for prof in profiles:
        ax.semilogy(
            snr,
            _ber_clip_plot(d[f"hf_{prof}_std_unc"]),
            "-",
            color=colors[prof],
            lw=1.2,
            label=f"{prof}: std GDSS uncoded",
        )
        ax.semilogy(
            snr,
            _ber_clip_plot(d[f"hf_{prof}_keyed_coded"]),
            "--",
            color=colors[prof],
            lw=1.0,
            alpha=0.85,
            label=f"{prof}: keyed GDSS + LDPC r=1/2",
        )
    ax.set_xlabel(r"$E_b/N_0$ (dB)")
    ax.set_ylabel("BER")
    ax.set_ylim(1e-6, 0.5)
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=5, loc="upper right", ncol=2)
    nbits = int(d["meta_bits"][0]) if "meta_bits" in d.files else 0
    sub = f" ({nbits} bits/SNR; STANAG-style TDL approx.)" if nbits else " (STANAG-style TDL approx.)"
    ax.set_title(f"Figure 9. HF military bands: uncoded standard GDSS vs LDPC-coded keyed GDSS, N=256{sub}", fontsize=9, fontweight="bold", color=MDPI_BLUE)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig9_hf_ber.png"), bbox_inches="tight")
    plt.close(fig)


def fig10_ldpc_fallback():
    snr = np.arange(-12, 10, 0.5)
    u = ber_gdss_family(snr, 256, 3.2)
    c = ber_gdss_family(snr - 5.2, 256, 3.2)
    fig, ax = plt.subplots(figsize=(6, 3.8), dpi=150)
    ax.semilogy(snr, np.maximum(u, 1e-8), "-", color=MDPI_BLUE, lw=1.5, label="Uncoded keyed GDSS")
    ax.semilogy(snr, np.maximum(c, 1e-8), "--", color=GREEN, lw=1.5, label="LDPC rate 1/2 (illustr. ~5.2 dB @ 1e-4)")
    ax.set_xlabel("SNR (dB)")
    ax.set_ylabel("BER")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend()
    ax.set_title("Figure 10. LDPC (fallback): run ber_simulation.py for MC", fontsize=9, fontweight="bold", color=MDPI_BLUE)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig10_ldpc.png"), bbox_inches="tight")
    plt.close(fig)


def fig10_ldpc():
    d = _load_ber_mc_npz()
    if d is None or "ldpc_unc" not in d.files:
        print("gen_figures: missing LDPC arrays in npz; Figure 10 uses parametric fallback.")
        fig10_ldpc_fallback()
        return
    snr = np.asarray(d["snr_db"])
    fig, ax = plt.subplots(figsize=(6.5, 3.8), dpi=150)
    ax.semilogy(snr, _ber_clip_plot(d["ldpc_unc"]), "-", color=MDPI_BLUE, lw=1.5, label="Uncoded keyed GDSS (MC), N=256")
    ax.semilogy(snr, _ber_clip_plot(d["ldpc_576"]), "--", color=GREEN, lw=1.5, label="LDPC r=1/2, block 576 (ideal ~4.8 dB shift)")
    ax.semilogy(snr, _ber_clip_plot(d["ldpc_1152"]), "-.", color=ORANGE, lw=1.5, label="LDPC r=1/2, block 1152 (ideal ~5.2 dB shift)")
    ax.set_xlabel(r"$E_b/N_0$ (dB)")
    ax.set_ylabel("BER")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=6)
    nbits = int(d["meta_bits"][0]) if "meta_bits" in d.files else 0
    sub = f" ({nbits} bits/SNR on uncoded MC)" if nbits else ""
    ax.set_title(f"Figure 10. LDPC coding gain vs block length (AWGN keyed GDSS){sub}", fontsize=9, fontweight="bold", color=MDPI_BLUE)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig10_ldpc.png"), bbox_inches="tight")
    plt.close(fig)


def fig11_radar():
    labels = ["Passive\ndet.", "Cyclo-\nstationary", "Moments", "Mod.\nstrip", "Sync\nburst", "Traffic\nanalysis", "Jam-\nming", "BER\nmargin"]
    N = len(labels)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    std = [7, 8, 8, 8, 4, 5, 5.5, 6]
    keyed = [7, 8, 8, 8, 8, 8, 7, 5]
    std += std[:1]
    keyed += keyed[:1]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(5, 5), subplot_kw=dict(polar=True), dpi=150)
    ax.plot(angles, np.array(std) / 10.0, "o-", color=MDPI_BLUE, lw=1.5, label="Standard GDSS")
    ax.fill(angles, np.array(std) / 10.0, alpha=0.15, color=MDPI_BLUE)
    ax.plot(angles, np.array(keyed) / 10.0, "s-", color=ORANGE, lw=1.5, label="Keyed GDSS")
    ax.fill(angles, np.array(keyed) / 10.0, alpha=0.15, color=ORANGE)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=6)
    ax.set_ylim(0, 1.0)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=7)
    ax.set_title("Figure 11. Security comparison (normalised 0-1; README tables)", fontsize=9, fontweight="bold", color=MDPI_BLUE, y=1.08)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig11_radar.png"), bbox_inches="tight")
    plt.close(fig)


def main():
    fig1_block_diagram()
    fig2_key_derivation()
    fig3_state_machine()
    fig4_sync_burst()
    fig5_bar_cross_session()
    fig6_histograms()
    fig7_awgn_ber()
    fig8_vhf()
    fig9_hf()
    fig10_ldpc()
    fig11_radar()
    print("Wrote figures to", FIG)


if __name__ == "__main__":
    main()
