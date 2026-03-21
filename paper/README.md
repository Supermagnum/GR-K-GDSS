![Open Invention Network member](../docs/oin-member-horiz.jpg)

# KGDSS preprint PDF (AI-generated)

This folder builds the Cryptographically Keyed GDSS academic-style preprint.

## Requirements

- `pdflatex` (TeX Live)
- Python 3 with `matplotlib`, `numpy`, `scipy`

## Build

BER figures (Figs. 7-10) read Monte Carlo results from `figures/ber_mc_results.npz`. Generate that file first (full paper default: `10^6` bits per SNR per curve; expect a long run):

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

The first page includes a mandatory AI disclaimer banner.

Section ``Intellectual Property and Licensing'' (before references) states GPL-3.0-or-later, Open Invention Network registration, the raw `LICENSE` URL, and links to GR-K-GDSS, gr-linux-crypto, and gr-qradiolink.

## Environment

| Variable | Meaning |
|----------|---------|
| `BER_MC_NUM_BITS` | Bits simulated per SNR point per Monte Carlo curve (default `1000000`). |

`ber_simulation.py` also records `MIN_MASK` (mask clamp) in the NPZ metadata.
