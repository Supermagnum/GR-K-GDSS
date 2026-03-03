# GR-K-GDSS Test Results

This document records snapshot results from the gr-k-gdss test suite. For how to run the tests and what they do, see [TESTING.md](TESTING.md).

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

**Summary:** 30 passed, 0 failed. (With a build that supports empty key/nonce and key_injector, TestT1SetKeyMessagePort may run for 31 passed.)

---

## IQ file analysis

After generating IQ test files with `python3 tests/generate_iq_test_files.py`, run `python3 tests/analyse_iq_files.py`. Example result:

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
--------------------------------------------------------------------------------
PASSED: 19   FAILED: 0   WARNINGS: 0
```

**Summary:** 19 passed, 0 failed, 0 warnings. Keyed GDSS transmission (03) matches the Gaussian noise baseline (01) on all listed metrics; correct-key despread (04) recovers the payload; wrong-key despread (05) shows key isolation.

### IQ comparison plot

Generated by `python3 tests/plot_iq_comparison.py`. Row 1: amplitude histograms (noise baseline, keyed GDSS transmission, wrong-key despread). Row 2: power spectral density (noise baseline, keyed transmission, sync burst). Row 3: autocorrelation (noise baseline, keyed transmission, correct-key despread). Files 1 and 3 should be visually indistinguishable in rows 1 and 2 when GDSS masking is working correctly.

![gr-k-gdss IQ comparison plot](../tests/iq_files/iq_comparison.png)
