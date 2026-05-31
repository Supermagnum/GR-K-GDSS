# GDSS masking keystream contract and verification reference

This note is for **third-party transmitters and receivers** that must stay **bit- and numerically compatible** with gr-k-gdss keyed spreader/despreader blocks. It summarizes the **ChaCha20-IETF keystream usage**, **Box-Muller masking**, **matched-filter despreading**, **correlation recovery** (symbol recovery coherence), and **measured reference \(\rho\)** values from the project test suite.

**Authoritative implementation:** [`lib/chacha_ietf_keystream.h`](../lib/chacha_ietf_keystream.h), [`lib/kgdss_spreader_cc_impl.cc`](../lib/kgdss_spreader_cc_impl.cc), [`lib/kgdss_despreader_cc_impl.cc`](../lib/kgdss_despreader_cc_impl.cc). Session material: **`gdss_masking`** (32 bytes) and a **12-byte nonce** from [`python/session_key_derivation.py`](../python/session_key_derivation.py) (e.g. `derive_session_keys`, `gdss_nonce`).

---

## 1. ChaCha20-IETF byte stream

- **Primitive:** libsodium `crypto_stream_chacha20_ietf_xor_ic` with **32-byte key**, **12-byte nonce**, **32-bit block index** `ic`.
- **Byte counter `ctr`:** Logical **byte offset** into the stream (starts at **0** after `set_key`). The API `produce_chacha_ietf_keystream` in [`lib/chacha_ietf_keystream.h`](../lib/chacha_ietf_keystream.h) maps:
  - `block_idx = ctr / 64`
  - `ic = static_cast<uint32_t>(block_idx)` (overflow guarded)
  - **Partial first block:** `skip = ctr % 64`; consume only bytes `[skip, 64)` from the XOR output; save the tail in a **64-byte remainder buffer** for the next call.
- **Remainder:** Any **unused tail** of a ChaCha block is stored and drained **before** generating the next full block. **`ctr` advances by one for every byte emitted** (from remainder or from a new block).
- **Consumption order:** Spread and despread both advance the same counter in lockstep when using the same key/nonce and processing **the same symbol stream in order** (same number of chips per symbol).

Implementations **must** match this remainder behaviour; otherwise the Box-Muller masks diverge even with the correct key.

---

## 2. Keystream to Gaussian chip mask (Box-Muller)

For **each chip**:

1. Take **8 consecutive keystream bytes** from the stream described above (same order as the C++ `work()` / `process()` loops).
2. Form two **little-endian 32-bit** integers from bytes `[0..4)` and `[4..8)`.
3. Map to uniforms: `(float(v) + 0.5f) / 4294967296.0f` (see spreader/despreader code for exact expression).
4. **Box-Muller** (same angle formula on TX and RX):
   - **Spreader:** radius includes **`sqrt(variance)`** scaling (see `box_muller_pair` in spreader).
   - **Despreader:** Box-Muller **without** the extra `sqrt(variance)` on radius; **matched-filter normalization** `sum(|mask|^2)` restores the original symbol scale (see despreader comments).

Clamp small mask magnitudes to **`MIN_MASK = 1e-4`** (same rule on both sides) to avoid division blow-ups.

Output chip (complex) is **symbol times complex mask** on TX; RX applies the **matched filter** against the **same** mask sequence derived from the same keystream bytes.

**Per-chip mask statistics:** With `variance = 1`, each I and Q mask component is approximately **Gaussian** (mean 0, standard deviation 1). Regression tests (`TestT1GaussianDistribution`, optional `kgdss_test_spreader_stats`) check mean and standard deviation of mask samples. That distribution is what makes the **spread chip stream** look **noise-like** in the time domain and contributes to a **broad, flat spectrum** after spreading (no narrow tonal structure from the mask alone). IQ file analysis in [TESTING.md](TESTING.md) (kurtosis near 3, low autocorrelation at non-zero lags) exercises the same statistical picture on recorded `.cf32` data.

---

## 3. Correlation recovery (symbol recovery)

**Correlation recovery** is the project term for how well the **despreader restores the original symbol vector** after a noiseless spreader-to-despreader chain with the **same** key, nonce, and keystream alignment. It is **not** a number emitted by `box_muller_pair()` (that function outputs **Gaussian mask samples**, typically on the order of 0.1 to 3 in magnitude). Recovery quality is summarized by **zero-lag complex coherence** \(\rho\) (Section 4) and by per-symbol error \(\max_i |o_i - s_i|\).

### What a value near 1.0 means

- **\(\rho = 1\)** (ideal): despread output is a **complex scalar multiple** of the input symbols; the keyed chain is matched end-to-end.
- **\(\rho \approx 0.99999\)** (typical on the **float32** GNU Radio 3 blocks): still excellent recovery; the gap below 1.0 comes from **float32** arithmetic, **`MIN_MASK` clamp** on tiny Gaussians, **`u1` floored at 1e-10** before `log`, and **matched-filter summation** over many chips per symbol—not from a defective Box-Muller formula.
- **\(\rho \ll 1\)** with the wrong key: expected; proves masks are key-dependent.

The T1 round-trip tests require \(\rho \ge\) **`0.99999`** (`COHERENCE_ROUNDTRIP_MIN` in [`tests/test_t1_spreader_despreader.py`](../tests/test_t1_spreader_despreader.py)) for the C++ float32 pipeline, plus symbol-wise `allclose` tolerance **`5e-6`**.

### Link to Box-Muller and noise-like spectrum

Correlation recovery validates the **full masking path**, of which Box-Muller is the statistical core:

1. **ChaCha20** delivers uniform bytes; **Box-Muller** turns pairs into **Gaussian I/Q masks** on TX and RX.
2. If TX and RX disagree on uniforms, angle, variance scaling, or clamp rules, \(\rho\) drops sharply even with the correct key.
3. High \(\rho\) on a noiseless back-to-back test therefore shows that **Box-Muller masking is implemented consistently** and that **matched-filter despreading** inverts it correctly.
4. Separately, **Gaussian masks** (and chip-wise multiplication) make the **spread signal** resemble **wideband thermal noise** to passive analysis—see IQ checks (Files 01/03/09) and [GLOSSARY.md](GLOSSARY.md) entries for kurtosis and autocorrelation.

**Do not confuse** correlation recovery (\(\rho\) on **symbols** after spread/despread) with **round-trip Pearson correlation** on offline IQ payloads (File 04 in [TESTING.md](TESTING.md#round-trip-what-it-means)); both are encode-decode checks but use different signals and metrics.

---

## 4. Verification metrics (definitions)

### Zero-lag complex coherence

For aligned length-\(N\) vectors of symbols **s** and despread output **o** (complex):

\[
\rho = \frac{|\mathbf{s}^H \mathbf{o}|}{\|\mathbf{s}\|\,\|\mathbf{o}\|}
\]

With a **perfect** noiseless matched implementation, \(\rho \to 1\) and \(\mathbf{o} \approx \mathbf{s}\) up to floating-point error.

### `corrComplexMag` (GNU Radio 4 tests)

Used in `gnuradio4/test/qa_KgdssDespreaderCc.cpp` over **real-aligned** inner products:

\[
\sum_i \bigl(\Re\{s_i\}\Re\{o_i\} + \Im\{s_i\}\Im\{o_i\}\bigr) = \sum_i \Re\{\overline{s_i}\, o_i\}
\]

normalized by \(\|s\|\|o\|\). With **matched** float32 engines, this stays **above 0.999** in the regression tests (spreading factors 32, 64, 256).

---

## 5. Measured reference values (regression capture)

Values below were obtained in a **Linux x86_64** environment with **Python 3.12**, project **`tests/test_matched_sequences.py`** (libsodium via ctypes, **float64** reference chain), and **GNU Radio 3** Python bindings for the T1-style round trip. They are **not** a cryptographic proof; they are **sanity targets** for independent ports. Small deviations (ULP-level on float64, ~1e-6–1e-7 on float32) may occur on other platforms.

### 5.1 Python float64 reference (`tests/test_matched_sequences.py`)

Same inputs as the test: `derive_session_keys(bytes(range(32)))["gdss_masking"]`, `gdss_nonce(1, 0)`, `numpy.random.default_rng(42)`, 400 complex symbols, `variance = 1.0`.

| Spreading factor (chips/symbol) | Zero-lag coherence \(\rho\) | \(\max_i |o_i - s_i|\) |
|--------------------------------:|------------------------------:|----------------------:|
| 32 | 0.99999999999999767 | 7.448e-16 |
| 64 | 0.99999999999999745 | 1.196e-15 |
| 256 | 0.99999999999999745 | 2.227e-15 |

### 5.2 GNU Radio 3 bindings (T1-style round trip)

`SEQ_LEN=127`, `chips_per_symbol=42`, `VARIANCE=1.0`, `SEED=12345`, same HKDF key/nonce as §5.1, 20 QPSK-style symbols (`numpy` exponential pilot), **`kgdss_spreader_cc` \(\to\) `kgdss_despreader_cc`** (float32 pipeline).

| Quantity | Value |
|----------|------:|
| Zero-lag coherence \(\rho\) | 0.99999999999994016 |
| \(\max_i |o_i - s_i|\) | 3.686e-07 |

### 5.3 GNU Radio 4 (branch `gnuradio4`)

Boost.UT tests in **`gnuradio4/test/qa_KgdssDespreaderCc.cpp`**: noiseless **`SpreaderEngine` / `DespreaderEngine`** back-to-back for **SF ∈ {32, 64, 256}** assert **`corrComplexMag` > 0.999** (48 symbols per SF, fixed RNG seed in test). Run: build `gnuradio4/` and `ctest -R qa_KgdssDespreaderCc`.

### 5.4 Acceptance thresholds (quick reference)

| Pipeline | Coherence \(\rho\) target | Symbol error (typical) | Test reference |
|----------|---------------------------|-------------------------|----------------|
| Python float64 reference | \(\ge 1 - 10^{-12}\) | \(< 10^{-12}\) | `test_matched_key_near_unity_coherence_zero_lag` |
| GNU Radio 3 float32 blocks | \(\ge 0.99999\) | \(\sim 10^{-7}\) (see §5.2) | `TestT1RoundTrip`, `COHERENCE_ROUNDTRIP_MIN` |
| GNU Radio 4 engines | `corrComplexMag` \(> 0.999\) | (engine-specific) | `qa_KgdssDespreaderCc.cpp` |

---

## 6. Related tests and docs

| Artifact | Role |
|----------|------|
| [`tests/test_matched_sequences.py`](../tests/test_matched_sequences.py) | Float64 Python reference; wrong-key decorrelation check |
| [`tests/test_t1_spreader_despreader.py`](../tests/test_t1_spreader_despreader.py) | GR3 blocks; round-trip tolerance and coherence |
| [`gnuradio4/test/qa_KgdssDespreaderCc.cpp`](../gnuradio4/test/qa_KgdssDespreaderCc.cpp) | GR4 engine correlation (on **`gnuradio4`** branch) |
| [`docs/USAGE.md`](USAGE.md) | Block parameters and key injector |
| [`docs/TESTING.md`](TESTING.md) | How to run pytest and optional C++ tests |

---

## SPDX

Documentation text is provided under the same license as the project (GPL-3.0-or-later) as part of GR-K-GDSS.
