# GR-K-GDSS Test Suite

This document describes the unit tests for gr-k-gdss, how to run them, what each test does, and the expected results.

## Running the tests

Prerequisites:

- Module built and installed from `build/` (e.g. `cd build && make -j4 && sudo make install`).
- Python environment with `gnuradio`, `numpy`, and `pytest` available.
- For the keyring round-trip test: run in a normal terminal (not a sandbox) so `keyctl read` is allowed; `keyctl` must be on PATH. See [tests/README.md](../tests/README.md).

From the repository root, with the same Python that can import `gnuradio.kgdss`:

```bash
pytest tests/ -v
```

If you use a venv that does not see system-installed packages, set PYTHONPATH so it includes the install prefix (e.g. `/usr/local/lib/python3.12/dist-packages`), or use:

```bash
./tests/run_tests.sh
```

Install pytest if needed: `pip install pytest`.

**Keyring test:** The keyring round-trip test is skipped with "Permission denied" when run inside a restricted environment (e.g. some sandboxes). Run `pytest tests/ -v` in a normal system terminal so the process can read keys from the session keyring; then all 30 tests pass.

## Documented test run (30 passed)

Example full run from a normal terminal (Linux, Python 3.12, gr-test-env):

```
pytest tests/ -v
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
tests/test_t3_key_derivation.py::TestT3DomainSeparation::test_domain_separation PASSED                                                                                                     [ 76%]
tests/test_t3_key_derivation.py::TestT3Determinism::test_determinism PASSED                                                                                                                [ 80%]
tests/test_t3_key_derivation.py::TestT3InputSensitivity::test_input_sensitivity PASSED                                                                                                      [ 83%]
tests/test_t3_key_derivation.py::TestT3NonceConstruction::test_different_tx_seq_different_nonce PASSED                                                                                     [ 86%]
tests/test_t3_key_derivation.py::TestT3NonceConstruction::test_gdss_nonce_length PASSED                                                                                                       [ 90%]
tests/test_t3_key_derivation.py::TestT3NonceConstruction::test_payload_nonce_length PASSED                                                                                                 [ 93%]
tests/test_t3_key_derivation.py::TestT3NonceConstruction::test_session_tx_seq_collision_avoidance PASSED                                                                                   [ 96%]
tests/test_t3_key_derivation.py::TestT3KeyringRoundTrip::test_keyring_round_trip PASSED                                                                                                    [100%]

======================================================================================= 30 passed in 0.20s ==============
```

## What the tests do

### Suite overview

| Suite | File | What it tests |
|-------|------|----------------|
| T1 | test_t1_spreader_despreader.py | C++ spreader and despreader blocks: round-trip, keystream behaviour, key/nonce validation, Gaussian masking, block continuity. |
| T2 | test_t2_sync_burst.py | Python sync-burst helpers: PN sequence generation, timing offsets, Gaussian envelope shape. |
| T3 | test_t3_key_derivation.py | Session key derivation (HKDF), nonce construction, and storing/loading the GDSS key via the Linux kernel keyring. |
| Cross-layer | test_cross_layer.py | End-to-end: derive keys, build spreader/despreader, run a full spread/despread flow; output matches input. |

### T1 — Spreader/despreader (test_t1_spreader_despreader.py)

These tests exercise the C++ blocks via Python bindings. They ensure the keyed spreader and despreader behave correctly and reject bad parameters.

| Test | What it does |
|------|----------------|
| **TestT1RoundTrip** | Sends known complex symbols through spreader then despreader; checks that the recovered symbols match the input (within tolerance). Validates the full chain with the same key and nonce. |
| **TestT1KeystreamDeterminism** | Runs the spreader twice with the same key, nonce, and seed; asserts the spreader output is identical. Ensures the ChaCha20-based keystream is deterministic. |
| **TestT1KeySensitivity** | Runs the spreader with two different keys; asserts the outputs differ. Ensures a different key produces a different mask. |
| **TestT1WrongKeyDespreader** | Spreads with key A, despreads with key B; asserts the recovered symbols do not match the input. Ensures the despreader cannot recover data without the correct key. |
| **TestT1NonceSensitivity** | Same key, different nonces; asserts spreader outputs differ. Ensures nonce is part of the keystream. |
| **TestT1InvalidKeySize** | Calls the blocks with key length 16, 31, and 33 bytes; expects an exception. Ensures only 32-byte keys are accepted. |
| **TestT1InvalidNonceSize** | Calls with nonce length 11 and 13 bytes; expects an exception. Ensures only 12-byte nonces are accepted. |
| **TestT1GaussianDistribution** | Inspects the spreader output mask values (I and Q); checks mean near 0 and standard deviation near 1. Validates the Box-Muller Gaussian masking. |
| **TestT1NoNearZeroMask** | Checks that no mask value is below a small threshold; ensures the spreader clamps near-zero masks to avoid division issues in the despreader. |
| **TestT1BlockBoundaryContinuity** | Runs spreader/despreader with 25 symbols and with 50 symbols (same key/nonce); asserts the first 25 recovered symbols of the 50-symbol run match the 25-symbol run. Ensures keystream continuity across work() calls in one flowgraph. |
| **TestT1SetKeyMessagePort** | Builds spreader and despreader with empty key/nonce, adds key_injector(shared_secret, session_id, tx_seq), connects key_out to both set_key ports, runs the flowgraph; key_injector sends the key automatically on start(). Asserts round-trip output matches input. Validates runtime key injection via the set_key message port. Skipped if key_injector is unavailable or the build does not support empty key/nonce. |

T1 tests are skipped if the C++ Python bindings (`gnuradio.kgdss.kgdss_python`) are not available.

### T2 — Sync burst (test_t2_sync_burst.py)

These tests cover the Python sync-burst utilities: PN sequence generation, timing-offset derivation, and Gaussian envelope.

| Test | What it does |
|------|----------------|
| **TestT2PNDeterminism** | Generates the sync PN sequence twice with the same key/session/chip count; asserts the sequences are identical. |
| **TestT2PNKeySensitivity** | Generates PN with two different keys; asserts the sequences differ. |
| **TestT2PNBalance** | Checks that the binary PN sequence has roughly balanced 0/1 counts within an acceptable range. |
| **TestT2TimingOffsetDeterminism** | Derives timing offset twice with the same inputs; asserts the same offset. |
| **TestT2TimingOffsetRange** | Checks that derived timing offsets fall within the configured window. |
| **TestT2TimingOffsetDistribution** | Checks that offsets are spread across the range (not always the same value). |
| **TestT2GaussianEnvelope** | Builds a Gaussian envelope and checks shape: rise, peak, and fall (right flank descending). |

T2 tests are skipped if `sync_burst_utils` (e.g. derive_sync_pn_sequence, gaussian_envelope) is not available (missing PyCryptodome or cryptography).

### T3 — Key derivation (test_t3_key_derivation.py)

These tests cover HKDF-based session key derivation, nonce construction, and the Linux keyring store/load path.

| Test | What it does |
|------|----------------|
| **TestT3OutputLength** | Calls derive_session_keys and checks that it returns four keys, each 32 bytes. |
| **TestT3DomainSeparation** | Ensures all four derived key names yield different key bytes (domain separation). |
| **TestT3Determinism** | Same secret and salt; asserts the derived keys are identical. |
| **TestT3InputSensitivity** | Changes one byte of the secret; asserts all derived keys change. |
| **TestT3NonceConstruction** | Checks gdss_nonce and payload_nonce lengths and that different (session, tx_seq) pairs produce different nonces; ensures no collision between session/tx_seq combinations. |
| **TestT3KeyringRoundTrip** | Derives session keys, stores them via store_session_keys (kernel keyring), loads the gdss_masking key with load_gdss_key, and asserts the loaded bytes match the stored key. Requires keyctl and a context where keyctl read is allowed (e.g. normal terminal). |

The keyring round-trip is skipped if the keyring is not available (no keyctl) or if keyctl read fails (e.g. Permission denied in a sandbox).

### Cross-layer (test_cross_layer.py)

| Test | What it does |
|------|----------------|
| **TestCrossLayerFullStackRoundTrip** | Derives session keys from a secret, builds spreader and despreader using the GDSS key and nonce from derivation, runs source -> spreader -> despreader, and asserts the recovered symbols match the input. Validates the full stack from key derivation to spread/despread. |

## Expected results

With the module installed, dependencies available, and tests run in a normal terminal (so keyctl read is allowed):

- **30 or 31 passed** — All tests pass. If the build supports empty key/nonce and key_injector is available, TestT1SetKeyMessagePort runs and 31 tests pass; otherwise that test is skipped and 30 pass.

If the keyring round-trip is skipped with "Permission denied", run `pytest tests/ -v` in a normal system terminal (outside any sandbox) so the process can read keys from the session keyring. If gr_linux_crypto and gr-k-gdss are installed in the default Python search path (e.g. /usr/local), no PYTHONPATH is needed for normal use.

## IQ test file generation and analysis

Three scripts in `tests/` generate and validate IQ test files used to check the keyed GDSS blocks statistically. **No IQ files are included in the repository** (generated or recorded); they are too large. Run `generate_iq_test_files.py` locally to create the generated set, and optionally copy a real recording into `tests/iq_files/` as described below. See `.gitignore` for `tests/iq_files/`.

### What IQ files are

**IQ** means in-phase (I) and quadrature (Q): two real signals that together represent a complex baseband (or IF) waveform. Each sample is one complex number: I is the real part, Q the imaginary part. So the waveform is I(t) + j*Q(t). This is the usual format for SDR and GNU Radio: one complex sample per time step.

In this test suite, IQ files are stored as **.cf32**: complex 32-bit float, with I and Q interleaved as consecutive float32 values (same as GNU Radio’s complex64 / `np.complex64`). So each sample is 8 bytes (I, Q), and the file has no separate header; it is raw complex samples. All generated and recorded files in `tests/iq_files/` use this format at 500 kHz sample rate so they can be compared directly.

### Generated files vs the real recording

| Source | Files | Role |
|--------|--------|------|
| **Generated** | 01–07, 09–13 (and 02_payload_reference.bin, JSON metadata) | Created by `generate_iq_test_files.py` from fixed parameters (seeds, keys, payload). No SDR or radio involved. Used as baselines (noise, plaintext), keyed/standard GDSS signals, despread results, sync bursts, and cross-correlations. |
| **Placeholder** | 08_real_noise_placeholder_README.txt | Written by the generator. It is a text file with instructions for recording real noise and, optionally, where to copy the project’s SDR recording. |
| **Recording (optional)** | 08_real_noise_with_hardware_artifacts.cf32 (or 08_real_noise_reference.cf32) | **Not** produced by the generator. It is a **real SDR recording** of the antenna input with no transmission: antenna to SDR source to file sink, 500 kHz, complex float32, at least 10 seconds. A pre-recorded example is provided in the project at `sdr-noise/08_real_noise_with_hardware_artifacts.cf32`. You can copy that file into `tests/iq_files/` (same name or as 08_real_noise_reference.cf32). |

**How the recording is used:** If `analyse_iq_files.py` finds either `08_real_noise_with_hardware_artifacts.cf32` or `08_real_noise_reference.cf32` in `tests/iq_files/`, it runs the same set of noise tests on that file as on the synthetic noise (01) and keyed GDSS (03): mean, variance symmetry, kurtosis, skewness, autocorrelation. That lets you compare keyed GDSS and synthetic noise against **real hardware noise** (including any DC, gain, or spur artifacts from the SDR). The recording is only used by the analyser when present; the generator never creates or overwrites it.

All of the above IQ data files (generated 01–07, 09–13 and optional recording 08) are excluded from the repository by `.gitignore` because they are too large to commit. Only the generator script, analyser, plot script, placeholder README for File 8, and the generated comparison plots (e.g. `iq_comparison.png`, `iq_comparison_vs_standard.png`) are tracked.

### What each IQ test file is

| File | Description |
|------|-------------|
| **01_gaussian_noise_baseline.cf32** | Pure complex Gaussian noise (I and Q each N(0,1)), same length and format as the other files. Used as the reference against which keyed GDSS output is compared; if masking works, keyed transmission should be statistically indistinguishable from this baseline. |
| **02_plaintext_reference.cf32** | The known payload (PAYLOAD_BYTES) mapped to BPSK symbols (+1/-1 on I, zero on Q) and repeated to fill the same number of samples. Stored alongside **02_payload_reference.bin** (raw bytes). Reference for what the despreader should recover when the key is correct. |
| **03_keyed_gdss_transmission.cf32** | The same payload as in 02, spread with the keyed GDSS construction (ChaCha20 keystream, Box-Muller masking, spreading factor 256) using the test key and nonce. This is the "transmitted" signal; it should look like Gaussian noise (same statistics as 01) to a passive observer. |
| **04_keyed_gdss_despread_correct_key.cf32** | Result of despreading 03 with the correct key and nonce. After averaging over the spreading factor and dividing by the same masks used on transmit, the result should match the original payload; the analyser checks Pearson correlation > 0.95. |
| **05_keyed_gdss_despread_wrong_key.cf32** | Result of despreading 03 with a wrong key and nonce. Without the correct key, the recovered stream should be uncorrelated with the payload; the analyser checks \|correlation\| < 0.05 (key isolation). |
| **06_sync_burst_isolation.cf32** | A short (2 ms) sync burst (PN sequence with Gaussian envelope, calibrated above noise) centred in 1 second of silence. Used to validate sync burst generation and to compare PSD in the plot script. |
| **07_nonce_reuse_transmission_A.cf32 / B.cf32** | Two transmissions with the same key and nonce but different payloads (A and B). Reusing key+nonce is insecure; the XOR of the two streams can leak structure. The analyser reports WARN if correlation of the XOR result with a known pattern exceeds a threshold. |
| **08_real_noise_placeholder_README.txt** | Instructions for recording real noise from an SDR (sample rate, duration, format). Optionally, copy a real recording (e.g. from `sdr-noise/08_real_noise_with_hardware_artifacts.cf32`) into `tests/iq_files/` to run the same noise tests on File 8. |
| **09_standard_gdss_transmission.cf32** | Standard (unkeyed) GDSS per Shakeel et al. 2023: masking from Gaussian RNG (not ChaCha20), same payload and spreading factor as 03. Used to compare keyed vs standard GDSS; both should look noise-like in histograms and PSD. |
| **10a_standard_gdss_sync_burst_session_A.cf32** | Standard GDSS sync burst for "session A": fixed PN sequence (seed 99), 2 ms burst at fixed position 10000 in a 500k-sample silence window. Same PN for every session (vulnerability). |
| **10b_standard_gdss_sync_burst_session_B.cf32** | Identical to 10a (same PN, same position). Cross-correlation of 10a vs 10b shows a strong peak (File 12), confirming the repeating-PN vulnerability. |
| **11a_keyed_gdss_sync_burst_session_A.cf32** | Keyed GDSS sync burst for session A: session-unique PN and timing from derive_sync_pn_sequence / derive_sync_schedule. |
| **11b_keyed_gdss_sync_burst_session_B.cf32** | Keyed GDSS sync burst for session B (different session_id). PN and burst position differ from 11a. Cross-correlation of 11a vs 11b (File 13) should show no detectable peak. |
| **12_standard_gdss_crosscorr_A_vs_B.cf32** | Normalized cross-correlation of 10a vs 10b (I component). Strong peak confirms standard GDSS sync bursts are detectable across sessions. Generator asserts peak > 0.5. |
| **13_keyed_gdss_crosscorr_A_vs_B.cf32** | Normalized cross-correlation of 11a vs 11b (I component). No strong peak; keyed GDSS session-unique PN is not detectable. Generator asserts peak < 0.15 (software simulation threshold; real transmission would be lower). The improvement ratio (standard peak / keyed peak) is what demonstrates protection. |

**Is the keyed GDSS residual (~0.107) exploitable?** The honest answer: **no**. That value is a **simulation artifact**. In the test, two sessions use different session-unique PN sequences and timing; the residual correlation comes from the finite sample size, identical burst envelope shape, and lack of channel effects. In a real channel, additional noise, multipath, and hardware imperfections would push the cross-session correlation lower. The residual is not considered exploitable for traffic analysis or session linking; the design goal is that keyed GDSS does not reveal repeating structure across sessions, and the roughly 9x reduction versus standard GDSS is what matters for that claim.

### Scripts

1. **generate_iq_test_files.py** — Builds all test files in `tests/iq_files/`: 01–08 as above, plus 09 (standard GDSS transmission), 10a/10b (standard sync bursts), 11a/11b (keyed sync bursts), 12 (standard cross-corr), 13 (keyed cross-corr). On success it prints "VULNERABILITY CONFIRMED" (File 12 peak > 0.5) and "PROTECTION CONFIRMED" (File 13 peak < 0.15), then "Generated all IQ test files in .../tests/iq_files". The 0.15 threshold is for software simulation; in real transmission, channel noise and hardware would push the keyed cross-session peak lower. The improvement ratio (e.g. 9x reduction) is what matters. Requires numpy, scipy, cryptography (and optionally pycryptodome for ChaCha20 IETF).
2. **analyse_iq_files.py** — Runs statistical checks: same as before on 01–08; on 09 the same eight noise-like tests (with relaxed thresholds for standard GDSS) plus KL divergence vs 03; reads JSON for 12/13 and prints a cross-session correlation summary (Standard GDSS peak, Keyed GDSS peak, improvement ratio). Prints a PASS/FAIL/WARN table and exits with 0 only if no tests fail.
3. **plot_iq_comparison.py** — Produces two plots. **iq_comparison.png**: original 3x3 grid (histograms, PSD, autocorrelation for 01, 03, 04, 05, 06). **iq_comparison_vs_standard.png**: 4x3 grid comparing keyed vs standard GDSS (rows 1–2: noise, keyed, standard; row 3: cross-correlation 12 vs 13 and overlay; row 4: despread comparison). Requires matplotlib.

Run from the repo root or from `tests/`:

```bash
cd tests
python3 generate_iq_test_files.py
ls -lh iq_files/
python3 analyse_iq_files.py
python3 plot_iq_comparison.py
```

### Example generator output

A successful run of `generate_iq_test_files.py`:

```
VULNERABILITY CONFIRMED: Standard GDSS cross-session peak = 1.000
PROTECTION CONFIRMED: Keyed GDSS cross-session peak = 0.107
Generated all IQ test files in /path/to/GR-K-GDSS/tests/iq_files
```

### Example IQ file analysis output

Example run of `analyse_iq_files.py` (with all generated files present, including 09 and 12/13):

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
Keyed GDSS    (sessions A vs B):  0.1070  PROTECTED
Improvement:  9.3x reduction in cross-session correlation
```

### Example plot output

After `plot_iq_comparison.py`:

```
Saved: /path/to/GR-K-GDSS/tests/iq_files/iq_comparison.png
Saved: /path/to/GR-K-GDSS/tests/iq_files/iq_comparison_vs_standard.png
```

Output files:

- `tests/iq_files/iq_comparison.png` — Keyed GDSS validation (3x3).
- `tests/iq_files/iq_comparison_vs_standard.png` — Keyed vs standard GDSS comparison (4x3).

### Unexpected PSD finding (Row 2, second plot): standard GDSS low-frequency peak

In Row 2 of `iq_comparison_vs_standard.png`, standard GDSS (File 09) can show a **low-frequency spectral peak** that the noise baseline and keyed GDSS (File 03) do not. This is expected from the structure of standard GDSS, not a bug.

- **Standard GDSS**: The same BPSK symbol is repeated for 256 chips (one symbol per spreading block). So the baseband chip stream is `symbol_1, symbol_1, ..., symbol_1` (256 times), then `symbol_2` repeated 256 times, and so on. The *symbol* therefore changes only every 256 samples; the mask (RNG) changes every sample. That slow, periodic change in the sign/magnitude of the symbol acts like a **amplitude modulation at the symbol rate** = sample rate / 256. At 500 kHz that is about 1.95 kHz. The PSD of such a process has extra energy at low frequencies (around that symbol rate), so a low-frequency peak appears. The mask is random but positive (abs of Gaussian), so it does not average out this slow envelope.

- **Keyed GDSS**: The mask is derived from ChaCha20 and is **signed** (zero-mean Gaussian) and different every chip. So the product (symbol × mask) has no persistent “symbol envelope” visible in the spectrum: the zero-mean mask decorrelates the output from the slow symbol pattern. The PSD therefore stays effectively flat, like the noise baseline.

So the low-frequency peak in standard GDSS is a **structural side effect of repeating the same symbol over 256 chips** with a positive (absolute-value) mask. Keyed GDSS avoids it by using a zero-mean, per-chip mask that removes that periodic component. This is another sense in which keyed GDSS is harder to distinguish from noise than standard GDSS.

If you add a real-noise recording (e.g. copy `sdr-noise/08_real_noise_with_hardware_artifacts.cf32` into `tests/iq_files/` as described in the placeholder README), the analyser runs the same noise tests on it and includes File 8 in the table.
