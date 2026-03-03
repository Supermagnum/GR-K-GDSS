# GR-K-GDSS Usage

This document describes how to use the keyed GDSS spreader and despreader blocks, their inputs and outputs, and how to connect them with gr-linux-crypto and SOQPSK (gr-qradiolink) for TX/RX.

---

## Keyed GDSS spreader and despreader blocks

The core of this OOT module is a pair of keyed GDSS blocks:

- `kgdss_spreader_cc` (GRC: **Keyed GDSS Spreader**)
- `kgdss_despreader_cc` (GRC: **Keyed GDSS Despreader**)

Both must be configured with **matching parameters and the same ChaCha20 key/nonce pair** for a given session.

### `kgdss_spreader_cc` (Keyed GDSS Spreader)

- **Input**:
  - One complex stream (`complex`), at the symbol rate.
  - Each sample is a complex baseband symbol (e.g. QPSK/pi/4-DQPSK/OFDM subcarrier symbol) before spreading.
- **Output**:
  - One complex stream (`complex`), at `chips_per_symbol` times the input rate.
  - Each input symbol is expanded into `chips_per_symbol` complex chips.
  - The real and imaginary parts are multiplied by keyed Gaussian mask values derived from:
    - A fixed Gaussian spreading sequence (length `sequence_length`, variance `variance`, RNG `seed`).
    - A ChaCha20 keystream keyed by `chacha_key` and `chacha_nonce`, converted to Gaussian via Box-Muller and clamped away from zero.

**Key parameters (must match despreader):**

- `sequence_length` (int): Length of the base Gaussian spreading sequence. Same on TX/RX.
- `chips_per_symbol` (int): Interpolation factor; number of chips per input symbol. Same on TX/RX.
- `variance` (float): Variance of the Gaussian spreading sequence; typically `1.0`. Same on TX/RX.
- `seed` (int): RNG seed for the base spreading sequence. Must be identical on TX/RX if you let each side generate its own sequence.
- `chacha_key` (32-byte key, hex string in GRC): Session GDSS masking key (e.g. `gdss_masking` from `derive_session_keys`), encoded as 64 hex characters.
- `chacha_nonce` (12-byte nonce, hex string in GRC): Session GDSS nonce (e.g. `gdss_nonce`), encoded as 24 hex characters. **Never reuse the same (key, nonce) pair across sessions.**

**Usage:**

- In GRC, insert **Keyed GDSS Spreader** before your channel/noise/modulator:
  - `Symbols -> Keyed GDSS Spreader -> Channel / RF chain`.
- In Python:

  ```python
  from gnuradio import kgdss

  spreader = kgdss.kgdss_spreader_cc(
      sequence_length,
      chips_per_symbol,
      variance,
      seed,
      list(chacha_key_bytes),
      list(chacha_nonce_bytes),
  )
  ```

  where `chacha_key_bytes` is 32 bytes and `chacha_nonce_bytes` is 12 bytes from the key-derivation helpers.

### `kgdss_despreader_cc` (Keyed GDSS Despreader)

- **Input**:
  - One complex stream (`complex`), at the **chip rate**, i.e. the output of `kgdss_spreader_cc` after the channel.
- **Outputs**:
  - **Output 0**: complex stream (`complex`, label: *Despread Symbols*).
    - Recovered complex symbols at the original symbol rate.
    - This should match the pre-spreader symbols (within channel/noise limits).
  - **Output 1**: float stream (`float`, label: *Lock Status*).
    - Per-symbol lock metric.
    - Values near 1.0 indicate acquisition/lock; values near 0.0 indicate loss of lock.
  - **Output 2**: float stream (`float`, label: *SNR Estimate (dB)*).
    - Per-symbol SNR estimate derived from the despreading correlation and noise statistics.

**Key parameters (must match spreader):**

- `sequence_length`, `chips_per_symbol`, `variance`, `seed`: Must be identical to the transmitter values (or you can explicitly pass the same spreading sequence).
- `correlation_threshold` (float): Threshold on the normalized correlation used to declare lock/acquisition. Typical starting value: `0.7`.
- `timing_error_tolerance` (int): Allowed chip offset tolerance when aligning the spreading sequence to the received chips.
- `chacha_key` (32-byte key, hex string): Must be the **same key** as the spreader.
- `chacha_nonce` (12-byte nonce, hex string): Must be the **same nonce** as the spreader for that session.

**Usage:**

- In GRC, insert **Keyed GDSS Despreader** after the channel/noise/demodulator:
  - `Channel / RF chain -> Keyed GDSS Despreader -> (symbols, lock, snr)`.
  - Connect:
    - Output 0 to your symbol sink / decoder.
    - Output 1 to a scope or threshold block to monitor lock.
    - Output 2 to a meter/scope to monitor SNR.
- In Python:

  ```python
  from gnuradio import kgdss

  despreader = kgdss.kgdss_despreader_cc(
      spreading_sequence,          # list[float] or numpy array
      chips_per_symbol,
      correlation_threshold,
      timing_error_tolerance,
      list(chacha_key_bytes),
      list(chacha_nonce_bytes),
  )
  ```

- The spreading sequence passed to the despreader must be the same as the one used by the spreader. With the provided GRC blocks, both sides independently regenerate the same sequence from `(sequence_length, variance, seed)`; in Python you can share the exact list of floats.

Together, `kgdss_spreader_cc` and `kgdss_despreader_cc` implement a keyed, Gaussian-distributed spread-spectrum layer that can be dropped around an existing complex symbol stream, as long as both ends share the same ChaCha20 key/nonce and spreading parameters.

---

## Connecting gr-linux-crypto and SOQPSK (TX/RX chains)

This section describes how to wire **gr-linux-crypto** (keyring/key source) and **gr-qradiolink** (SOQPSK modulator/demodulator) to the Keyed GDSS spreader and despreader.

### Getting keys into the GDSS blocks (gr-linux-crypto)

The GDSS spreader and despreader take **key and nonce as constructor parameters** (fixed for the flowgraph run). They do not read keys from a stream. To use keys stored with gr-linux-crypto and the Linux kernel keyring:

1. **Before the session (e.g. in a startup script or control application):**
   - Obtain the ECDH shared secret (e.g. via gr-linux-crypto ECDH or GnuPG + `get_shared_secret_from_gnupg` from gr-k-gdss).
   - Derive session keys: `keys = derive_session_keys(ecdh_shared_secret)` (gr-k-gdss Python).
   - Store them in the keyring: `ids = store_session_keys(keys)` (uses keyctl or gr-linux-crypto KeyringHelper).
   - Build the GDSS nonce for this session: `nonce = gdss_nonce(session_id, tx_seq)` (gr-k-gdss).

2. **When building the flowgraph:**
   - Load the GDSS masking key from the keyring: `gdss_key = load_gdss_key(ids["gdss_masking"])` (gr-k-gdss Python; key ID from step 1).
   - Pass `gdss_key` (32 bytes) and `nonce` (12 bytes) into the Keyed GDSS Spreader and Despreader. In **GRC** you must encode them as **hex strings** (64 hex chars for key, 24 for nonce) in the block parameters `chacha_key` and `chacha_nonce`. In **Python** flowgraphs you pass `list(gdss_key)` and `list(nonce)` to `kgdss_spreader_cc` / `kgdss_despreader_cc`.

3. **Using gr-linux-crypto blocks:**
   - gr-linux-crypto provides **Kernel Keyring Source** (e.g. `linux_crypto_kernel_keyring_source` or `kernel_keyring_source`), which can read a key from the kernel keyring by key ID. That block typically outputs key material (e.g. as a stream or message) for use by other blocks. Because the GDSS blocks expect key/nonce at **construction time**, you cannot connect the keyring source output directly to the spreader/despreader. Use the keyring source in one of these ways:
     - **Option A:** Run a small Python script that calls `load_gdss_key(key_id)` and then builds the flowgraph (e.g. with `gnuradio.eng_notation` and `kgdss`), passing the loaded bytes and `gdss_nonce(...)` into the block constructors.
     - **Option B:** In GRC, use a **Variable** or **Id** to hold the key and nonce as hex strings. Set those variables from an external process that reads the keyring (e.g. a helper that runs at flowgraph start and writes hex to a file or uses message passing). The Keyed GDSS Spreader/Despreader parameters can reference those variables (e.g. `chacha_key` = `$key_hex`).
   - For **payload encryption** (ChaCha20-Poly1305), use gr-linux-crypto's encrypt/decrypt blocks and the `payload_enc` and `payload_nonce` keys from the same session key derivation; those are separate from the GDSS key/nonce.

### TX chain: SOQPSK modulator and Keyed GDSS Spreader

Signal flow on transmit:

1. **Bits / payload** (optional FEC, optional payload encryption with gr-linux-crypto).
2. **SOQPSK modulator** (gr-qradiolink): bits or symbols in, **complex baseband symbols out** at the symbol rate.
3. **Keyed GDSS Spreader** (gr-k-gdss): complex symbols in, **spread complex chips out** at chip rate (symbol rate x `chips_per_symbol`).
4. Optional: insert sync burst (e.g. using gr-k-gdss sync burst helpers).
5. **Channel / RF**: resample, filter, upconvert, send to SDR.

In GRC the chain looks like:

```
[Source / Packet / Stream] -> [SOQPSK Modulator] -> [Keyed GDSS Spreader] -> [Resampler / Filter / USRP Sink etc.]
```

- **SOQPSK Modulator** output: complex, symbol rate.
- **Keyed GDSS Spreader** input: complex, symbol rate (same as SOQPSK output).
- **Keyed GDSS Spreader** output: complex, chip rate. Connect this to your channel/resampler/RF sink.

Ensure the **sample rate** at the spreader output matches what the rest of your TX chain expects (symbol rate x `chips_per_symbol`). Adjust resampling or block sample rates in GRC so there are no rate mismatches.

### RX chain: Keyed GDSS Despreader and SOQPSK demodulator

Signal flow on receive:

1. **Channel / RF**: SDR source, downconvert, filter, resample to **chip rate** (same as spreader output).
2. **Keyed GDSS Despreader** (gr-k-gdss): complex chips in (chip rate), **three outputs**: (0) despread complex symbols at symbol rate, (1) lock metric (float), (2) SNR estimate (float).
3. **SOQPSK Demodulator** (gr-qradiolink): **complex symbols in** (symbol rate), bits or symbols out.
4. Optional: payload decryption, FEC decode.

In GRC the chain looks like:

```
[USRP Source / File Source etc.] -> [Resampler / Filter] -> [Keyed GDSS Despreader] -> (out 0) -> [SOQPSK Demodulator] -> [Sink / Packet]
                                                      -> (out 1) -> [Scope / Lock indicator]
                                                      -> (out 2) -> [SNR meter]
```

- **Keyed GDSS Despreader** input: complex, **chip rate** (must match the spreader's output rate and the rest of the RX chain).
- **Keyed GDSS Despreader** output 0: complex, **symbol rate**. Connect this to the **SOQPSK Demodulator** input.
- **Keyed GDSS Despreader** outputs 1 and 2: float streams for lock and SNR; connect to scopes or indicators as needed.

The SOQPSK demodulator expects complex baseband symbols at the same symbol rate and alignment as produced by the SOQPSK modulator. The despreader must use the **same** `sequence_length`, `chips_per_symbol`, `variance`, `seed`, `chacha_key`, and `chacha_nonce` as the transmitter.

### Summary

| Stage        | Block (module)        | Input           | Output                          |
|-------------|------------------------|-----------------|----------------------------------|
| TX modulate | SOQPSK Modulator      | bits/symbols   | complex, symbol rate            |
| TX spread   | Keyed GDSS Spreader   | complex, sym rate | complex, chip rate           |
| RX despread | Keyed GDSS Despreader | complex, chip rate | (0) complex sym rate, (1) lock, (2) SNR |
| RX demod    | SOQPSK Demodulator    | complex, symbol rate | bits/symbols               |

Keys and nonce are set at flowgraph build time from the keyring (e.g. via `load_gdss_key` and `gdss_nonce` in Python, or hex variables in GRC). gr-linux-crypto supplies key storage and ECDH/payload crypto; gr-qradiolink supplies SOQPSK; gr-k-gdss supplies the keyed GDSS spreader and despreader between SOQPSK and the channel.
