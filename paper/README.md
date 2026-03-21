![Open Invention Network member](../docs/oin-member-horiz.jpg)

# KGDSS preprint PDF (AI-generated)

This folder builds the Cryptographically Keyed GDSS academic-style preprint.

## Requirements

- `pdflatex` (TeX Live)
- Python 3 with `matplotlib`, `numpy`, `scipy`

## Build

BER figures (Figs. 7-10) read Monte Carlo results from `figures/ber_mc_results.npz`. The default SNR grid is $E_b/N_0$ from **-20 dB to +25 dB** (step 1 dB); **Figure 8 (VHF) alone** uses **`snr_db_vhf`**, **-20 dB to +40 dB**, so the Rayleigh + keyed curves show a falling slope (a steep waterfall may still lie beyond +40 dB). The upper end is needed because keyed `mean(r/m)` has strong noise enhancement: a short grid can look like a stuck receiver near BER 0.5. VHF curves use **flat block Rayleigh** (constant gain per symbol); per-chip Doppler phase was removed because it collapses the keyed combiner.

Generate `ber_mc_results.npz` first (full paper default: `10^6` bits per SNR per curve; expect a long run):

```bash
cd paper
python3 ber_simulation.py
```

Quick test (example):

```bash
BER_MC_NUM_BITS=50000 python3 ber_simulation.py
```

Then build figures and PDF:

```bash
python3 gen_figures.py
pdflatex -interaction=nonstopmode kgdss_paper.tex
pdflatex -interaction=nonstopmode kgdss_paper.tex
```

Output: `paper/kgdss_paper.pdf`

If `ber_mc_results.npz` is missing, `gen_figures.py` falls back to parametric placeholder curves for Figs. 7-10 and prints a warning.

**Spectrum and IQ comparison figures (Section 5--6):** after generating IQ fixtures, run `python3 tests/plot_spectrum_snapshots.py` and `python3 tests/plot_iq_comparison.py` so `tests/iq_files/` contains `spectrum_*.png` and `iq_comparison_vs_standard.png`. Then `gen_figures.py` copies or crops them into `paper/figures/` (`fig_spectrum_*.png`, `fig_iq_psd_row_vs_standard.png`). If those sources are absent, placeholder PNGs are written so the PDF still builds.

The first page includes a mandatory AI disclaimer banner.

Section ``Intellectual Property and Licensing'' (before references) states GPL-3.0-or-later, Open Invention Network registration, the raw `LICENSE` URL, and links to GR-K-GDSS, gr-linux-crypto, and gr-qradiolink.

## Environment

| Variable | Meaning |
|----------|---------|
| `BER_MC_NUM_BITS` | Bits simulated per SNR point per Monte Carlo curve (default `1000000`). |

`ber_simulation.py` also records `MIN_MASK` (mask clamp) in the NPZ metadata.
