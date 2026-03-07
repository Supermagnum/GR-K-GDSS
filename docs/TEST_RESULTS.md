# GR-K-GDSS Test Results

This document records snapshot results from the gr-k-gdss test suite. For how to run the tests and what they do, see [TESTING.md](TESTING.md).

**Last recorded run: 6 March 2026 03:49**

- **IQ file analysis:** 29 passed, 0 failed, 0 warnings. Cross-session: Standard GDSS 1.0000 (VULNERABLE), Keyed GDSS 0.1028 (PROTECTED), 9.7x reduction. Plots: `tests/iq_files/iq_comparison.png`, `tests/iq_files/iq_comparison_vs_standard.png`.

---

## Table of Contents

- [Unit tests (pytest)](#unit-tests-pytest)
- [IQ test file generation](#iq-test-file-generation)
- [IQ file analysis](#iq-file-analysis)
  - [Explanation of analysis tests](#explanation-of-analysis-tests)
  - [IQ comparison plots](#iq-comparison-plots)

---

## Unit tests (pytest)

Run: `pytest tests/ -v` from the repository root (after installing the module and gr-linux-crypto). Example result with keyring available (Linux, Python 3.12):

```
====================================================================================== test session starts =======================================================================================
platform linux -- Python 3.12.3, pytest-9.0.2, pluggy-1.6.0 -- /home/haaken/gr-test-env/bin/python3
cachedir: .pytest_cache
rootdir: /mnt/2e9a1e9f-2097-408c-ab9a-a01b32f11d28/github-projects/GR-K-GDSS
collected 30 items

tests/test_cross_layer.py::TestCrossLayerFullStackRoundTrip::test_full_stack_round_trip PASSED                                                                                             [  3%]
tests/test_t1_spreader_despreader.py::TestT1RoundTrip::test_round_trip PASSED                                                                                                              [  6%]
tests/test_t1_spreader_despreader.py::TestT1KeystreamDeterminism::test_keystream_determinism PASSED                                                                                        [ 10%]
tests/test_t1_spreader_despreader.py::TestT1KeySensitivity::test_key_sensitivity PASSED                                                                                                    [ 13%]
tests/test_t1_spreader_despreader.py::TestT1WrongKeyDespreader::test_wrong_key_despreader PASSED                                                                                          [ 16%]
tests/test_t1_spreader_despreader.py::TestT1NonceSensitivity::test_nonce_sensitivity PASSED                                                                                                [ 20%]
tests/test_t1_spreader_despreader.py::TestT1InvalidKeySize::test_key_16_throws PASSED                                                                                                     [ 23%]
tests/test_t1_spreader_despreader.py::TestT1InvalidKeySize::test_key_31_throws PASSED                                                                                                      [ 26%]
tests/test_t1_spreader_despreader.py::TestT1InvalidKeySize::test_key_33_throws PASSED                                                                                                     [ 30%]
tests/test_t1_spreader_despreader.py::TestT1InvalidNonceSize::test_nonce_11_throws PASSED                                                                                                   [ 33%]
tests/test_t1_spreader_despreader.py::TestT1InvalidNonceSize::test_nonce_13_throws PASSED                                                                                                   [ 36%]
tests/test_t1_spreader_despreader.py::TestT1GaussianDistribution::test_gaussian_distribution PASSED                                                                                        [ 40%]
tests/test_t1_spreader_despreader.py::TestT1NoNearZeroMask::test_no_near_zero_mask PASSED                                                                                                  [ 43%]
tests/test_t1_spreader_despreader.py::TestT1BlockBoundaryContinuity::test_block_boundary_continuity PASSED                                                                                 [ 46%]
tests/test_t2_sync_burst.py::TestT2PNDeterminism::test_pn_determinism PASSED                                                                                                              [ 50%]
tests/test_t2_sync_burst.py::TestT2PNKeySensitivity::test_pn_key_sensitivity PASSED                                                                                                        [ 53%]
tests/test_t2_sync_burst.py::TestT2PNBalance::test_pn_balance PASSED                                                                                                                      [ 56%]
tests/test_t2_sync_burst.py::TestT2TimingOffsetDeterminism::test_timing_determinism PASSED                                                                                                 [ 60%]
tests/test_t2_sync_burst.py::TestT2TimingOffsetRange::test_timing_offset_range PASSED                                                                                                      [ 63%]
tests/test_t2_sync_burst.py::TestT2TimingOffsetDistribution::test_timing_offset_distribution PASSED                                                                                        [ 66%]
tests/test_t2_sync_burst.py::TestT2GaussianEnvelope::test_gaussian_envelope_shape PASSED                                                                                                   [ 70%]
tests/test_t3_key_derivation.py::TestT3OutputLength::test_output_length PASSED                                                                                                             [ 73%]
tests/test_t3_key_derivation.py::TestT3DomainSeparation::test_domain_separation PASSED                                                                                                    [ 76%]
tests/test_t3_key_derivation.py::TestT3Determinism::test_determinism PASSED                                                                                                               [ 80%]
tests/test_t3_key_derivation.py::TestT3InputSensitivity::test_input_sensitivity PASSED                                                                                                    [ 83%]
tests/test_t3_key_derivation.py::TestT3NonceConstruction::test_different_tx_seq_different_nonce PASSED                                                                                     [ 86%]
tests/test_t3_key_derivation.py::TestT3NonceConstruction::test_gdss_nonce_length PASSED                                                                                                    [ 90%]
tests/test_t3_key_derivation.py::TestT3NonceConstruction::test_payload_nonce_length PASSED                                                                                                 [ 93%]
tests/test_t3_key_derivation.py::TestT3NonceConstruction::test_session_tx_seq_collision_avoidance PASSED                                                                                    [ 96%]
tests/test_t3_key_derivation.py::TestT3KeyringRoundTrip::test_keyring_round_trip PASSED                                                                                                    [100%]

======================================================================================= 30 passed in 0.20s ==============
```

**Summary:** 30 passed, 0 failed. (With a build that supports empty key/nonce and key_injector, TestT1SetKeyMessagePort may run for 31 passed. The suite now also includes tests for sync-burst keyed masking and gdss_sync_burst_nonce; after a full install from current source, 33–38 tests may run depending on environment.)

---

## IQ test file generation

Run `python3 tests/generate_iq_test_files.py`. Example output:

```
VULNERABILITY CONFIRMED: Standard GDSS cross-session peak = 1.000
PROTECTION CONFIRMED: Keyed GDSS cross-session peak = 0.107
Generated all IQ test files in /path/to/GR-K-GDSS/tests/iq_files
```

## IQ file analysis

After generating IQ test files, run `python3 tests/analyse_iq_files.py`. Example result (with standard GDSS files 09 and cross-correlation 12/13 present):

```
=== gr-k-gdss IQ File Analysis ===

File                                       Test                         Result
--------------------------------------------------------------------------------
01_gaussian_noise_baseline.cf32            Mean (I)                     PASS
01_gaussian_noise_baseline.cf32            Mean (Q)                     PASS
01_gaussian_noise_baseline.cf32            Variance symmetry            PASS
01_gaussian_noise_baseline.cf32            Kurtosis (I)                 PASS
01_gaussian_noise_baseline.cf32            Kurtosis (Q)                 PASS
01_gaussian_noise_baseline.cf32            Skewness (I)                 PASS
01_gaussian_noise_baseline.cf32            Skewness (Q)                 PASS
01_gaussian_noise_baseline.cf32            Autocorrelation              PASS
03_keyed_gdss_transmission.cf32            Mean (I)                     PASS
03_keyed_gdss_transmission.cf32            Mean (Q)                     PASS
03_keyed_gdss_transmission.cf32            Variance symmetry            PASS
03_keyed_gdss_transmission.cf32            Kurtosis (I)                 PASS
03_keyed_gdss_transmission.cf32            Kurtosis (Q)                 PASS
03_keyed_gdss_transmission.cf32            Skewness (I)                 PASS
03_keyed_gdss_transmission.cf32            Skewness (Q)                 PASS
03_keyed_gdss_transmission.cf32            Autocorrelation              PASS
04_keyed_gdss_despread_correct_key.cf32    Round-trip correlation       PASS
05_keyed_gdss_despread_wrong_key.cf32      Key isolation                PASS
07_nonce_reuse                             Nonce reuse detection        PASS
09_standard_gdss_transmission.cf32         Mean (I)                     PASS
09_standard_gdss_transmission.cf32         Mean (Q)                     PASS
09_standard_gdss_transmission.cf32         Variance symmetry            PASS
09_standard_gdss_transmission.cf32         Kurtosis (I)                 PASS
09_standard_gdss_transmission.cf32         Kurtosis (Q)                 PASS
09_standard_gdss_transmission.cf32         Skewness (I)                 PASS
09_standard_gdss_transmission.cf32         Skewness (Q)                 PASS
09_standard_gdss_transmission.cf32         Autocorrelation              PASS
09_vs_03                                   KL divergence (I)            PASS
13_keyed_gdss_crosscorr                    Keyed cross-session peak < 0.15 PASS
--------------------------------------------------------------------------------
PASSED: 29   FAILED: 0   WARNINGS: 0

=== Cross-Session Sync Burst Correlation ===
Standard GDSS (sessions A vs B):  1.0000  VULNERABLE
Keyed GDSS    (sessions A vs B):  0.1028  PROTECTED
Improvement:  9.7x reduction in cross-session correlation
```

**Summary:** 29 passed, 0 failed, 0 warnings. Keyed GDSS (03) matches the noise baseline (01) on all metrics; standard GDSS (09) passes all noise-like tests and KL divergence vs 03; correct-key despread (04) and key isolation (05) pass; Keyed cross-session peak < 0.15 PASS. Cross-session correlation: Standard 1.0 VULNERABLE, Keyed 0.103 PROTECTED, 9.7x improvement. The keyed residual (e.g. ~0.10) is a simulation artifact; in a real channel it would be lower and is not considered exploitable (see [TESTING.md](TESTING.md)).

#### Explanation of analysis tests

| Test | Meaning |
|------|--------|
| **Mean (I)** / **Mean (Q)** | Sample mean of the in-phase (I) or quadrature (Q) component. PASS: mean is close to zero (no DC offset), as expected for noise-like or masked GDSS. See [Mean (I) and Mean (Q)](GLOSSARY.md#mean-i-and-mean-q). |
| **Variance symmetry** | I and Q have similar spread (standard deviation). PASS: ratio within tolerance; failure would suggest non-circular structure. See [Variance symmetry (IQ analysis)](GLOSSARY.md#variance-symmetry-iq-analysis). |
| **Kurtosis (I)** / **Kurtosis (Q)** | Peakedness of the I or Q distribution vs Gaussian (expected ~3). PASS: value in range ~2.7–3.3 so the signal looks Gaussian. See [Kurtosis (IQ analysis)](GLOSSARY.md#kurtosis-iq-analysis). |
| **Skewness (I)** / **Skewness (Q)** | Asymmetry of the I or Q distribution (0 = symmetric). PASS: |skewness| < 0.1. See [Skewness (IQ analysis)](GLOSSARY.md#skewness-iq-analysis). |
| **Autocorrelation** | Normalized correlation of the I component with itself at lags 1–100. PASS: no significant correlation (signal looks uncorrelated like noise). See [Autocorrelation (IQ analysis)](GLOSSARY.md#autocorrelation-iq-analysis). |
| **KL divergence (I)** | Compares the I-component distribution of File 09 (standard GDSS) with File 03 (keyed GDSS). PASS: distributions are close (both noise-like). See [KL divergence (IQ analysis)](GLOSSARY.md#kl-divergence-iq-analysis). |

### IQ comparison plots

Run `python3 tests/plot_iq_comparison.py`. A CSV index of all panels is in [plots_table.csv](plots_table.csv) (columns: plot_file, grid, row, col, panel_type, title, data_source). The script applies a DC block (mean subtraction) before computing PSD and excludes the first and last frequency bins when plotting PSD to avoid vertical lines at the plot edges. Row 1 amplitude histograms: File 1 (noise baseline) uses the same y-axis scale in both figures with a 0.07 upper margin so amplitudes barely fit; other panels in each row use a per-figure scale so File 05 and File 09 peaks are not cut off. Example output:

```
Saved: /path/to/GR-K-GDSS/tests/iq_files/iq_comparison.png
Saved: /path/to/GR-K-GDSS/tests/iq_files/iq_comparison_vs_standard.png
```

Two files are produced:

1. **iq_comparison.png** (3x3) — Keyed GDSS validation. Row 1: amplitude histograms (noise baseline, keyed GDSS transmission, wrong-key despread). Row 2: power spectral density (noise baseline, keyed transmission, sync burst). Row 3: autocorrelation (noise baseline, keyed transmission, correct-key despread). Files 1 and 3 should be visually indistinguishable in rows 1 and 2 when GDSS masking is working correctly.

![gr-k-gdss IQ comparison plot](../tests/iq_files/iq_comparison.png)

2. **iq_comparison_vs_standard.png** (4x3) — Keyed vs standard GDSS comparison. Rows 1–2: histograms and PSD for noise (01), keyed (03), and standard (09); all three should look alike. Row 3: cross-correlation of standard GDSS sessions (12, red) vs keyed sessions (13, green) and overlay; standard shows a detectable peak, keyed does not. Row 4: despreading (keyed correct/wrong key vs despread of standard GDSS without key).

![gr-k-gdss keyed vs standard GDSS comparison](../tests/iq_files/iq_comparison_vs_standard.png)
