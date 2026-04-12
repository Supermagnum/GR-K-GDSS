# GR-K-GDSS Test Suite

This document describes the unit tests for gr-k-gdss, how to run them, what each test does, and the expected results.

## Table of Contents

- [Running the tests](#running-the-tests)
- [C++ crypto tests (optional)](#c-crypto-tests-optional)
- [Documented test run](#documented-test-run)
- [Round trip (what it means)](#round-trip-what-it-means)
- [What the tests do](#what-the-tests-do)
  - [Suite overview](#suite-overview)
  - [T1 — Spreader/despreader (test_t1_spreader_despreader.py)](#t1--spreaderdespreader-test_t1_spreader_despreaderpy)
  - [T2 — Sync burst (test_t2_sync_burst.py)](#t2--sync-burst-test_t2_sync_burstpy)
  - [P372 — Receiver PSD profile (test_p372_receiver_profile.py)](#p372--receiver-psd-profile-test_p372_receiver_profilepy)
  - [T3 — Key derivation (test_t3_key_derivation.py)](#t3--key-derivation-test_t3_key_derivationpy)
  - [Galdralag mapping (test_galdralag_kgdss_compat.py)](#galdralag-mapping-test_galdralag_kgdss_compatpy)
  - [gr-linux-crypto HKDF (test_gr_linux_crypto_hkdf_compat.py)](#gr-linux-crypto-hkdf-test_gr_linux_crypto_hkdf_compatpy)
  - [Cross-layer (test_cross_layer.py)](#cross-layer-test_cross_layerpy)
- [Expected results](#expected-results)
- [IQ test file generation and analysis](#iq-test-file-generation-and-analysis)
  - [What IQ files are](#what-iq-files-are)
  - [Generated files vs the real recording](#generated-files-vs-the-real-recording)
  - [What each IQ test file is](#what-each-iq-test-file-is)
  - [Scripts](#scripts)
  - [Example generator output](#example-generator-output)
  - [Example IQ file analysis output](#example-iq-file-analysis-output)
  - [Example plot output](#example-plot-output)
  - [Unexpected PSD finding (Row 2, second plot): standard GDSS low-frequency peak](#unexpected-psd-finding-row-2-second-plot-standard-gdss-low-frequency-peak)

---

## Round trip (what it means)

In this project, **round trip** means running a **forward** transform and its matching **inverse** (or store-then-load) and checking that the result is consistent—usually that you recover the original data or the same bytes you stored.

**Spreader and despreader (T1, cross-layer, IQ File 04):** The tests run the **transmit-side** spreader and then the **receive-side** despreader with the **same key and nonce**, in software, often in one process. That is **conceptually the same shape as TX then RX** (encode then decode), but it is **not** a full radio link: there is typically **no over-the-air path**, **no RF front end**, and **no channel** unless a test or script adds noise or impairment. So it **simulates** the keyed GDSS signal chain for correctness, not a complete hardware transceiver.

**Keyring round trip (T3):** **Store** derived key material in the Linux kernel keyring, **load** it back, and assert the bytes match. That is a round trip in the **key-storage** sense only; it is **not** TX/RX.

**IQ analysis “Round-trip correlation” (File 04):** After generating a keyed transmission (File 03), the pipeline **despreads** with the correct key and checks **Pearson correlation** between the recovered stream and the known payload reference. That is another **encode-then-decode** style check on **offline IQ data**, still without a live RF loop.

For a short definition, see [Round trip (testing)](GLOSSARY.md#round-trip-testing) in [GLOSSARY.md](GLOSSARY.md).

---

## Running the tests

Prerequisites:

- Module built and installed from `build/` (e.g. `cd build && make -j4 && sudo make install`).
- Python environment with `gnuradio`, `numpy`, and `pytest` available.
- For the keyring round-trip test: run in a normal terminal (not a sandbox) so `keyctl read` is allowed; `keyctl` must be on PATH. See [tests/README.md](../tests/README.md).
- For **Galdralag / gr-linux-crypto** mapping tests: install gr-linux-crypto (with `python/galdralag_session_kdf.py`) or set **`GR_LINUX_CRYPTO_DIR`** to the gr-linux-crypto repository root. If a sibling directory `../gr-linux-crypto/python` exists, the test module sets it automatically.

From the repository root, with the same Python that can import `gnuradio.kgdss`:

```bash
pytest tests/ -v
```

If you use a venv that does not see system-installed packages, set PYTHONPATH so it includes the install prefix (e.g. `/usr/local/lib/python3.12/dist-packages`), or use:

```bash
./tests/run_tests.sh
```

Install pytest if needed: `pip install pytest`.

**Keyring test:** The keyring round-trip test is skipped with "Permission denied" when run inside a restricted environment (e.g. some sandboxes). Run `pytest tests/ -v` in a normal system terminal so the process can read keys from the session keyring.

**Compile check:** From the repo root, run `mkdir -p build && cd build && cmake .. && make -j4` to verify the C++ and Python build. Install with `make install` (or `sudo make install` for system prefix) so that the unit tests see the installed module.

### C++ crypto tests (optional)

Google Test binaries exercise **`gr::kgdss::detail::produce_chacha_ietf_keystream`** (the same ChaCha20-IETF path used by the spreader and despreader) and **`kgdss_spreader_cc::work()`** mask statistics. They are **off by default** and require **libsodium** (already required for the keyed blocks).

Configure with **`KGDSS_ENABLE_CRYPTO_TESTS=ON`**. The first configure **fetches** GoogleTest and nlohmann_json via CMake `FetchContent` (network required once). A **small Wycheproof-derived** JSON subset is committed under **`tests/cpp/data/`** (empty-AAD ChaCha20-Poly1305 cases; message XOR ciphertext equals the raw ChaCha20 keystream from byte offset 64 per RFC 7539 AEAD layout). The upstream C2SP Wycheproof tree no longer ships a standalone **`chacha20_test.json`**; those cases still validate the raw keystream primitive used by the spreader.

```bash
mkdir -p build && cd build
cmake .. -DKGDSS_ENABLE_CRYPTO_TESTS=ON
cmake --build . -j$(nproc)
ctest -R 'kgdss_test_' --output-on-failure
```

## Documented test run

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

(With the current source, after install, more tests run: TestT1SetKeyMessagePort plus TestT2KeyedGaussianMask, TestT2SyncBurstNonce, and TestT3SyncBurstNonce; expect 33–38 passed depending on environment.)

## What the tests do

### Suite overview

| Suite | File | What it tests |
|-------|------|----------------|
| T1 | test_t1_spreader_despreader.py | C++ spreader and despreader blocks: round-trip, keystream behaviour, key/nonce validation, Gaussian masking, block continuity. |
| T2 | test_t2_sync_burst.py | Python sync-burst helpers: multi-burst schedule derivation, per-burst PN evolution, Gaussian envelope shape, keyed Gaussian mask for sync bursts, sync-burst nonce. |
| P372 | test_p372_receiver_profile.py | P.372 baseline loader determinism, expected PSD profile shape, and robust calibration against measured receiver PSD bins. |
| T3 | test_t3_key_derivation.py | Session key derivation (HKDF), nonce construction, and storing/loading the GDSS key via the Linux kernel keyring. |
| Galdralag | test_galdralag_kgdss_compat.py | Maps gr-linux-crypto `derive_galdralag_session_keys` output to gr-k-gdss subkey names; swap-invariant GDSS keys; payload i2r vs r2i. Skips if Galdralag KDF is unavailable. |
| gr-linux-crypto HKDF | test_gr_linux_crypto_hkdf_compat.py | `derive_session_keys(...)['gdss_masking']` matches `CryptoHelpers.derive_key_hkdf` with salt `bytes(32)` and info `gdss-chacha20-masking-v1` (gr-linux-crypto / GDSS Set Key Source default path). Skips if `CryptoHelpers` unavailable. |
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

**Why TestT1SetKeyMessagePort is slow:** This test runs a full GNU Radio flowgraph (source -> spreader -> despreader with key_injector on the set_key port) until a fixed number of samples have been processed. The flowgraph scheduler is single-threaded by default, so all of that work runs on one CPU core. The test can take noticeably longer than the other T1 tests; that is expected.

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
| **TestT2KeyedGaussianMask** | apply_keyed_gaussian_mask: same key/nonce/burst yields identical output; shape preserved; different nonce yields different output. Ensures sync bursts can be masked like GDSS data. |
| **TestT2SyncBurstNonce** | gdss_sync_burst_nonce(session_id) returns 12 bytes; different session_id yields different nonce. |

T2 tests are skipped if `sync_burst_utils` (e.g. derive_sync_pn_sequence, gaussian_envelope) is not available (missing PyCryptodome or cryptography). The keyed-mask and sync-burst-nonce tests are skipped unless `apply_keyed_gaussian_mask` and `gdss_sync_burst_nonce` are exported by the installed module.

### P372 — Receiver PSD profile (test_p372_receiver_profile.py)

These tests cover receiver-side P.372 integration helpers.

| Test | What it does |
|------|----------------|
| **TestP372BaselineLoader** | Calls `load_p372_params()` twice and checks deterministic values (including `rise_fraction=0.15`). |
| **TestP372ExpectedProfile** | Builds expected per-bin PSD profile for FFT bins and checks shape/finite output. |
| **TestP372Calibration** | Verifies median-offset calibration against synthetic measured PSD. |

**Import-mode note:** In development environments, pytest may import from source tree while `gnuradio.kgdss` points to an older installed package. The tests include source fallback and `p372_receiver_profile.py` supports both package-relative and direct imports. This avoids collection-time errors such as `attempted relative import with no known parent package`.

### T3 — Key derivation (test_t3_key_derivation.py)

These tests cover HKDF-based session key derivation, nonce construction, and the Linux keyring store/load path.

| Test | What it does |
|------|----------------|
| **TestT3OutputLength** | Calls derive_session_keys and checks that it returns four keys, each 32 bytes. |
| **TestT3DomainSeparation** | Ensures all four derived key names yield different key bytes (domain separation). |
| **TestT3Determinism** | Same secret and salt; asserts the derived keys are identical. |
| **TestT3InputSensitivity** | Changes one byte of the secret; asserts all derived keys change. |
| **TestT3NonceConstruction** | Checks gdss_nonce and payload_nonce lengths and that different (session, tx_seq) pairs produce different nonces; ensures no collision between session/tx_seq combinations. |
| **TestT3SyncBurstNonce** | gdss_sync_burst_nonce(session_id) returns 12 bytes and is distinct from the data nonce gdss_nonce(session_id, 0) so the sync-burst keystream does not overlap the data keystream. |
| **TestT3KeyringRoundTrip** | Derives session keys, stores them via store_session_keys (kernel keyring), loads the gdss_masking key with load_gdss_key, and asserts the loaded bytes match the stored key. Requires keyctl and a context where keyctl read is allowed (e.g. normal terminal). |

The keyring round-trip is skipped if the keyring is not available (no keyctl) or if keyctl read fails (e.g. Permission denied in a sandbox).

### Galdralag mapping (test_galdralag_kgdss_compat.py)

These tests assert that **gr-linux-crypto** `derive_galdralag_session_keys` can be wrapped into the same four names as `derive_session_keys` (`payload_enc`, `gdss_masking`, `sync_pn`, `sync_timing`) for use with gr-k-gdss blocks and sync helpers.

| Test | What it does |
|------|----------------|
| **TestGaldralagKgdssMapping** | Derives via `derive_session_keys_from_galdralag`, checks four 32-byte keys; verifies `payload_direction` changes `payload_enc` but not GDSS/sync keys; verifies swapping initiator/responder ephemeral public keys leaves GDSS and sync keys unchanged. |
| **test_map_invalid_payload_direction** | `map_galdralag_keys_to_kgdss` rejects an invalid `payload_direction`. |

The entire class is skipped when `galdralag_kdf_available()` is false (no `derive_galdralag_session_keys` in gr-linux-crypto).

### gr-linux-crypto HKDF (test_gr_linux_crypto_hkdf_compat.py)

| Test | What it does |
|------|----------------|
| **TestGrLinuxCryptoGdssHkdfCompat** | Asserts `derive_session_keys(secret)["gdss_masking"]` equals `CryptoHelpers.derive_key_hkdf(secret, salt=bytes(32), info=b"gdss-chacha20-masking-v1", length=32)` for 32-byte and 48-byte ECDH-style secrets. |

Skipped when `gr_linux_crypto.CryptoHelpers` cannot be imported (install gr-linux-crypto or set **`GR_LINUX_CRYPTO_DIR`**).

### Cross-layer (test_cross_layer.py)

| Test | What it does |
|------|----------------|
| **TestCrossLayerFullStackRoundTrip** | Derives session keys from a secret, builds spreader and despreader using the GDSS key and nonce from derivation, runs source -> spreader -> despreader, and asserts the recovered symbols match the input. Validates the full stack from key derivation to spread/despread. |

## Expected results

With the module installed, **gr-linux-crypto** (including **galdralag_session_kdf** when you want Galdralag tests), dependencies available, and tests run in a normal terminal (so keyctl read is allowed):

- With **gr-linux-crypto** (including **galdralag_session_kdf**), **GNU Radio** / bindings installed, and keyring access where applicable, expect about **48 passed** and **1 skipped** (keyring round-trip often skips without `keyctl`). Fewer passes or more skips occur if Galdralag KDF is missing (four mapping tests skip) or the module is not installed. Run `pytest tests/ -q` for the exact tally on your machine.

If the keyring round-trip is skipped with "Permission denied", run `pytest tests/ -v` in a normal system terminal (outside any sandbox) so the process can read keys from the session keyring. If `gr_linux_crypto` and gr-k-gdss are installed in the default Python search path (e.g. `/usr/local`), no `PYTHONPATH` is needed for normal use. For co-development, set **`GR_LINUX_CRYPTO_DIR`** to the gr-linux-crypto repository root (see [USAGE.md](USAGE.md)).

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

All of the above IQ data files (generated 01–07, 09–13 and optional recording 08) are excluded from the repository by `.gitignore` because they are too large to commit. Only the generator script, analyser, plot scripts, placeholder README for File 8, and the generated plots (e.g. `iq_comparison.png`, `iq_comparison_vs_standard.png`, `spectrum_baseline.png`, `spectrum_standard_gdss.png`, `spectrum_keyed_gdss.png`, `spectrum_real_noise.png`, `spectrum_realistic_baseline.png`, `spectrum_realistic_plus_standard_gdss.png`, `spectrum_realistic_plus_keyed_gdss.png`) are tracked.

### What each IQ test file is

| File | Description |
|------|-------------|
| **01_gaussian_noise_baseline.cf32** | Pure complex Gaussian noise (I and Q each N(0,1)), same length and format as the other files. Used as the reference against which keyed GDSS output is compared; if masking works, keyed transmission should be statistically indistinguishable from this baseline. |
| **01b_realistic_noise_baseline.cf32** | Realistic receiver-like noise: tilt across band, slow power wandering, soft band-edge roll-off, 1/f near DC, small random bumps. Used as a base for merged signals 01c and 01d. |
| **01c_realistic_noise_plus_standard_gdss.cf32** | Realistic noise (01b) + unkeyed GDSS (09) with frequency-domain Gaussian roll-off on the GDSS component. For spectrum plots over realistic noise. |
| **01d_realistic_noise_plus_keyed_gdss.cf32** | Realistic noise (01b) + keyed GDSS (03) with frequency-domain Gaussian roll-off on the GDSS component. For spectrum plots over realistic noise. |
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
| **11a_keyed_gdss_sync_burst_session_A.cf32** | Keyed GDSS **scheduled multi-burst** waveform for session A: deterministic burst epochs from `derive_sync_schedule`, per-burst PN from `derive_sync_pn_sequence(..., burst_index=i)`, Gaussian envelope (`rise_fraction=0.15`), keyed Gaussian mask, and per-burst amplitude jitter. |
| **11b_keyed_gdss_sync_burst_session_B.cf32** | Same scheduled multi-burst construction for session B (different `session_id`). Schedule and per-burst PN differ from 11a, so cross-correlation of 11a vs 11b (File 13) should show no detectable recurring structure. |
| **12_standard_gdss_crosscorr_A_vs_B.cf32** | Normalized cross-correlation of 10a vs 10b (I component). Strong peak confirms standard GDSS sync bursts are detectable across sessions. Generator asserts peak > 0.5. |
| **13_keyed_gdss_crosscorr_A_vs_B.cf32** | Normalized cross-correlation of 11a vs 11b (I component) over the **full scheduled multi-burst waveforms**. No strong peak; keyed GDSS recurring structure is not detectable. Generator asserts peak < 0.15 (software simulation threshold; real transmission would be lower). The improvement ratio (standard peak / keyed peak) is what demonstrates protection. |

**Is the keyed GDSS residual exploitable?** The honest answer: **no**. The residual value in software tests is a **simulation artifact**. In the multi-burst test, two sessions use different schedules, per-burst PN sequences, and amplitude jitter; any remaining correlation comes from finite sample effects and simplified channel assumptions. In a real channel, additional noise, multipath, and hardware imperfections would push cross-session correlation lower. The residual is not considered exploitable for traffic analysis or session linking; the key metric is strong reduction versus standard GDSS.

### Scripts

1. **generate_iq_test_files.py** — Builds all test files in `tests/iq_files/`: 01, 01b (realistic noise), 01c (realistic + unkeyed GDSS), 01d (realistic + keyed GDSS), 02–08 as above, plus 09 (standard GDSS transmission), 10a/10b (standard sync bursts), 11a/11b (**keyed scheduled multi-burst** sync waveforms), 12 (standard cross-corr), 13 (keyed cross-corr). The keyed schedule uses Pareto-distributed inter-burst intervals, per-burst PN evolution (`burst_index`), and deterministic log-normal amplitude jitter. On success it prints "VULNERABILITY CONFIRMED" (File 12 peak > 0.5) and "PROTECTION CONFIRMED" (File 13 peak < 0.15), then "Generated all IQ test files in .../tests/iq_files". The 0.15 threshold is for software simulation; in real transmission, channel noise and hardware would push the keyed cross-session peak lower. The improvement ratio is what matters. Requires numpy, scipy, cryptography (and optionally pycryptodome for ChaCha20 IETF).
2. **analyse_iq_files.py** — Runs statistical checks: same as before on 01–08; on 09 the same eight noise-like tests (with relaxed thresholds for standard GDSS) plus KL divergence vs 03; reads JSON for 12/13 and prints a cross-session correlation summary (Standard GDSS peak, Keyed GDSS peak, improvement ratio). Prints a PASS/FAIL/WARN table and exits with 0 only if no tests fail.
3. **plot_iq_comparison.py** — Produces two plots. **iq_comparison.png**: original 3x3 grid (histograms, PSD, autocorrelation for 01, 03, 04, 05, 06). **iq_comparison_vs_standard.png**: 4x3 grid comparing keyed vs standard GDSS (rows 1–2: noise, keyed, standard; row 3: cross-correlation 12 vs 13 and overlay; row 4: despread comparison). Requires matplotlib.
4. **plot_spectrum_snapshots.py** — Produces spectrum snapshot images (600 kHz bandwidth, Welch PSD, DC bin excluded, Gaussian roll-off): **spectrum_baseline.png** (File 01), **spectrum_standard_gdss.png** (File 09 + File 06), **spectrum_keyed_gdss.png** (File 03), **spectrum_real_noise.png** when File 08 exists (Blackman-Harris), **spectrum_realistic_baseline.png** (File 01b synthetic realistic baseline), **spectrum_realistic_plus_standard_gdss.png** (File 01c), **spectrum_realistic_plus_keyed_gdss.png** (File 01d). Data is resampled from 500 kHz to 600 kHz. A notch at 0 Hz in spectrum displays is caused by the DC blocker in GNU Radio (see [Unexpected PSD finding](#unexpected-psd-finding-row-2-second-plot-standard-gdss-low-frequency-structure)). Requires matplotlib, scipy.

Run from the repo root or from `tests/`. The generator now uses FFT-based cross-correlation and should complete quickly on typical machines:

```bash
cd tests
timeout 600 python3 generate_iq_test_files.py
ls -lh iq_files/
python3 analyse_iq_files.py
python3 plot_iq_comparison.py
python3 plot_spectrum_snapshots.py
```

**Unit tests** (from repo root, with the module installed):

```bash
pytest tests/ -v
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

### File 09 histogram: notch or step at zero (Row 1, third plot)

In Row 1 of `iq_comparison_vs_standard.png`, the amplitude histogram for File 09 (standard GDSS) can show a **notch or step at zero** in the Gaussian-like profile. This is expected.

- **Cause:** File 09 is generated from **BPSK symbols** that are real-only (`symbols_bpsk = (2*bits - 1) + 0j`). The chip formula is `symbol.real * mask_i + 1j * symbol.imag * mask_q`, so the quadrature (Q) component is **identically zero**. The plot draws histograms of both I and Q; for File 09, the Q histogram is a **spike at zero** (all Q samples are 0). That spike, overlaid with the smooth Gaussian-shaped I distribution, appears as a vertical step or notch at zero.
- **Contrast:** File 01 (noise) and File 03 (keyed GDSS) have both I and Q drawn from zero-mean Gaussians, so their histograms are smooth bell curves with no spike at zero.
- So the notch/step in File 09 is an artifact of **BPSK (real symbols)** in the test generator, not a bug in the plot or in standard GDSS.

### Unexpected PSD finding (Row 2, second plot): standard GDSS low-frequency structure

In Row 2 of `iq_comparison_vs_standard.png`, standard GDSS (File 09) can show **low-frequency structure** that the noise baseline and keyed GDSS (File 03) do not. This is expected from the structure of standard GDSS, not a bug.

**DC block in PSD:** The plot script applies a **DC block** before computing the PSD: it subtracts the mean from the real component (`data.real - np.mean(data.real)`) so that the zero-frequency bin does not dominate or create a notch in the display. This matches common SDR practice (DC blocking so the rest of the spectrum is visible). Without this block, standard GDSS (File 09) would show a sharp notch at DC (the zero-mean signal has negligible DC power, so the first Welch bin appears very low); that notch is a structural feature of standard GDSS (deterministic autocorrelation at zero lag). Keyed GDSS has no such structure at DC. With the DC block applied, the displayed PSD is comparable across the band; the remaining contrast (e.g. low-frequency peak in File 09) still shows that standard GDSS has structural features that keyed GDSS eliminates.

**Notch at 0 Hz:** A notch or dip at 0 Hz in a spectrum display (e.g. in GNU Radio or in the spectrum snapshot images) is caused by the **DC blocker** in the GNU Radio flowgraph or in the processing. The DC block removes the DC component so that the rest of the spectrum is visible; the zero-frequency bin then shows very low power, which appears as a notch at center frequency.

For **live receive** flowgraphs (RTL-SDR DC spike, IQ imbalance, mirror images), mitigation is **outside** the GDSS blocks; see [DC spike and IQ imbalance (real SDR hardware)](USAGE.md#dc-spike-and-iq-imbalance-real-sdr-hardware) in [USAGE.md](USAGE.md).

- **Standard GDSS**: The same BPSK symbol is repeated for 256 chips (one symbol per spreading block). So the baseband chip stream is `symbol_1, symbol_1, ..., symbol_1` (256 times), then `symbol_2` repeated 256 times, and so on. The *symbol* therefore changes only every 256 samples; the mask (RNG) changes every sample. That slow, periodic change in the sign/magnitude of the symbol acts like a **amplitude modulation at the symbol rate** = sample rate / 256. At 500 kHz that is about 1.95 kHz. The PSD of such a process has extra energy at low frequencies (around that symbol rate), so a low-frequency peak appears. The mask is random but positive (abs of Gaussian), so it does not average out this slow envelope.

- **Keyed GDSS**: The mask is derived from ChaCha20 and is **signed** (zero-mean Gaussian) and different every chip. So the product (symbol × mask) has no persistent “symbol envelope” visible in the spectrum: the zero-mean mask decorrelates the output from the slow symbol pattern. The PSD therefore stays effectively flat, like the noise baseline.

So the low-frequency peak in standard GDSS is a **structural side effect of repeating the same symbol over 256 chips** with a positive (absolute-value) mask. Keyed GDSS avoids it by using a zero-mean, per-chip mask that removes that periodic component. This is another sense in which keyed GDSS is harder to distinguish from noise than standard GDSS.

If you add a real-noise recording (e.g. copy `sdr-noise/08_real_noise_with_hardware_artifacts.cf32` into `tests/iq_files/` as described in the placeholder README), the analyser runs the same noise tests on it and includes File 8 in the table.
