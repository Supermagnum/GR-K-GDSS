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

- **30 passed** — All tests, including keyring round-trip and block-boundary continuity, pass.

If the keyring round-trip is skipped with "Permission denied", run `pytest tests/ -v` in a normal system terminal (outside any sandbox) so the process can read keys from the session keyring. If gr_linux_crypto and gr-k-gdss are installed in the default Python search path (e.g. /usr/local), no PYTHONPATH is needed for normal use.
