# GR-K-GDSS Usage

This document describes how to use the keyed GDSS blocks (spreader, despreader, and key injector), their inputs and outputs, and how to connect them with gr-linux-crypto and SOQPSK (gr-qradiolink) for TX/RX.

---

## Block API summary

All three blocks are in GRC under category **KGDSS / DSSS**.

| Block | Stream inputs | Stream outputs | Message inputs | Message outputs | Main parameters |
|-------|----------------|----------------|----------------|-----------------|-----------------|
| **Keyed GDSS Spreader** (`kgdss_spreader_cc`) | 1 complex (symbol rate) | 1 complex (chip rate) | `set_key` (optional) | none | sequence_length, chips_per_symbol, variance, seed, chacha_key, chacha_nonce |
| **Keyed GDSS Despreader** (`kgdss_despreader_cc`) | 1 complex (chip rate) | 3: complex (symbols), float (lock), float (SNR dB) | `set_key` (optional) | none | spreading_sequence, chips_per_symbol, correlation_threshold, timing_error_tolerance, chacha_key, chacha_nonce |
| **Keyed GDSS Key Injector** (`kgdss_key_injector`) | none | none | `trigger` (optional), `shared_secret` (optional) | `key_out` | keyring_id, shared_secret_hex, session_id, tx_seq |

**Spreader / Despreader message input `set_key`:** PMT dict with `"key"` (u8vector 32 bytes) and `"nonce"` (u8vector 12 bytes). Until a key is set, the spreader outputs zeros and the despreader outputs zeros on all stream ports. Connect **Key Injector** output `key_out` to both blocks' `set_key` input.

**Despreader status (query in Python after flowgraph runs):** `get_sync_state()`, `is_locked()`, `get_snr_estimate()`, `get_last_soft_metric()`, `get_frequency_error()`.

---

## Keyed GDSS blocks

The core of this OOT module is three blocks:

- `kgdss_spreader_cc` (GRC: **Keyed GDSS Spreader**)
- `kgdss_despreader_cc` (GRC: **Keyed GDSS Despreader**)
- `kgdss_key_injector` (GRC: **Keyed GDSS Key Injector**)

Both must be configured with **matching parameters and the same ChaCha20 key/nonce pair** for a given session. Key and nonce can be set at construction time or at runtime via the **set_key** message port.

**set_key message port:** Both blocks have a message input port `set_key`. When a message arrives (PMT dict with keys `"key"` and `"nonce"`, each a u8vector of 32 and 12 bytes), the block updates its internal ChaCha20 context and resets the keystream counter. Until a key is set (either at construction or via message), the block outputs zeros. This allows key material to stay in the kernel keyring until the moment it is needed and supports re-keying without restarting the flowgraph.

### `kgdss_spreader_cc` (Keyed GDSS Spreader)

- **Stream input:** One complex stream (`complex`), at the symbol rate. Each sample is a complex baseband symbol (e.g. QPSK/pi/4-DQPSK/OFDM subcarrier symbol) before spreading.
- **Stream output:** One complex stream (`complex`), at `chips_per_symbol` times the input rate. Each input symbol is expanded into `chips_per_symbol` complex chips.
- **Message input:** `set_key` (optional). When present, a PMT dict with `"key"` (u8vector 32 bytes) and `"nonce"` (u8vector 12 bytes). Connect from Key Injector `key_out` or GDSS Set Key Source `set_key_out`.
- **Message outputs:** None.

The real and imaginary parts of each chip are multiplied by keyed Gaussian mask values derived from:
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

- **Stream input:** One complex stream (`complex`), at the chip rate (output of the spreader after the channel).
- **Stream outputs:**
  - **Output 0** (Despread Symbols): complex stream (`complex`). Recovered symbols at the original symbol rate; should match the pre-spreader symbols within channel/noise limits.
  - **Output 1** (Lock Status): float stream (`float`). Per-symbol lock metric; near 1.0 when locked, near 0.0 when not.
  - **Output 2** (SNR Estimate (dB)): float stream (`float`). Per-symbol SNR estimate from despreading correlation and noise.
- **Message input:** `set_key` (optional). PMT dict with `"key"` (u8vector 32 bytes) and `"nonce"` (u8vector 12 bytes). Connect from Key Injector `key_out` or GDSS Set Key Source `set_key_out`.
- **Message outputs:** None.

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

### `kgdss_key_injector` (Keyed GDSS Key Injector)

Provides the GDSS key and nonce to the spreader and despreader via the `set_key` message port. Key material comes from session key derivation (keyring or shared secret); no manual key bytes.

- **Stream inputs:** None.
- **Stream outputs:** None.
- **Message inputs:**
  - `trigger` (optional): When any message is received, the block re-sends the current key message on `key_out`. Not required for normal use; the key is sent once when the flowgraph starts.
  - `shared_secret` (optional): When a message with a 32-byte u8vector body is received, the block derives key and nonce from it and publishes the set_key message on `key_out`. Use when key material is supplied by another block (e.g. from gr-linux-crypto).
- **Message output:** `key_out`. Carries a PMT dict with `"key"` (u8vector 32 bytes) and `"nonce"` (u8vector 12 bytes). Connect `key_out` to the `set_key` message input of both the Keyed GDSS Spreader and the Keyed GDSS Despreader (use a message copy/duplicate if your flowgraph supports it).

**Parameters:**

- `keyring_id` (int): Keyring key ID for the gdss_masking key (from `store_session_keys`). Set to 0 to use `shared_secret_hex` instead.
- `shared_secret_hex` (string): 64 hexadecimal characters (32 bytes) when `keyring_id` is 0. Ignored when `keyring_id` > 0.
- `session_id` (int): Session identifier; must match on TX and RX.
- `tx_seq` (int): Transmission sequence number; must match on TX and RX.

**Usage:** Add the block, set either `keyring_id` or `shared_secret_hex` (with `keyring_id` = 0), set `session_id` and `tx_seq` to match the other side. Connect `key_out` to `set_key` on both the spreader and the despreader. No trigger connection is needed; the key is sent when the flowgraph starts.

Together, `kgdss_spreader_cc`, `kgdss_despreader_cc`, and `kgdss_key_injector` implement a keyed, Gaussian-distributed spread-spectrum layer: the key injector feeds key/nonce to both ends, and the spreader/despreader handle the symbol stream as long as both ends share the same ChaCha20 key/nonce and spreading parameters.

---

## Connecting gr-linux-crypto and SOQPSK (TX/RX chains)

This section describes how to wire **gr-linux-crypto** (keyring/key source) and **gr-qradiolink** (SOQPSK modulator/demodulator) to the Keyed GDSS spreader and despreader.

### Getting keys into the GDSS blocks (automated, no manual entry)

The ChaCha20 key and nonce are always provided from session key derivation; the user does not enter key or nonce manually. Use the **set_key** message port and a key source block so that key material is derived (or loaded from keyring) and sent automatically when the flowgraph starts.

**Recommended: key_injector (gr-k-gdss)**

1. Build the spreader and despreader with **empty key and nonce** (e.g. in Python pass `b""` and `b""` so the blocks wait for a set_key message).
2. Add a **key_injector** block (gr-k-gdss). Provide key material in one of three ways:
   - **keyring_id** (int): Load the GDSS masking key from the kernel keyring. One-time setup: run ECDH, `derive_session_keys`, `store_session_keys` (with keyctl), then use the returned key id. No key bytes in the flowgraph.
   - **shared_secret** (bytes at construction): ECDH shared secret; key_injector derives the GDSS key and nonce via HKDF.
   - **shared_secret** message port: Connect a block that sends the 32-byte shared secret once (e.g. from gr-linux-crypto); key_injector derives and sends set_key when the message arrives.
3. Connect **key_injector.key_out** to the **set_key** message port of both the spreader and the despreader.
4. No trigger needed: key_injector sends the set_key message automatically when the flowgraph starts.

```
[key_injector] key_out --> set_key (spreader)
       |                --> set_key (despreader)
```

Key injector (Python) examples:

```python
from gnuradio import kgdss

# Option A: key from keyring (zero manual key entry; run store_session_keys once with keyctl)
injector = kgdss.key_injector(keyring_id=12345, session_id=1, tx_seq=0)

# Option B: shared secret at construction (e.g. from ECDH or get_shared_secret_from_gnupg)
shared_secret = ...  # bytes, at least 32
injector = kgdss.key_injector(shared_secret=shared_secret, session_id=1, tx_seq=0)

# Connect injector.key_out to spreader.set_key and despreader.set_key (message ports)
# Key is sent automatically on flowgraph start.
```

**Alternative: gr-linux-crypto GDSS Set Key Source**

If you use gr-linux-crypto, add the **GDSS Set Key Source** block (category [gr-linux-crypto]/GDSS). Set shared secret as 64 hex chars (or from ECDH output), session_id and tx_seq. Connect **set_key_out** to the set_key port of the spreader and despreader. The message is sent once when the flowgraph starts. For zero manual entry use key_injector with keyring_id instead.

**Alternative: key at construction**

You can still pass key and nonce at construction (32 and 12 bytes). In **GRC** encode them as hex in `chacha_key` and `chacha_nonce`. In **Python** pass the bytes. If you pass empty key/nonce, the block outputs zeros until it receives a valid set_key message.

**Payload encryption** (ChaCha20-Poly1305) remains separate: use gr-linux-crypto's encrypt/decrypt blocks with `payload_enc` and `payload_nonce` from the same session key derivation.

### gr-linux-crypto compatibility

gr-k-gdss is designed to work with gr-linux-crypto for key storage and ECDH. Use the following to keep behaviour and key handling compatible.

**Where to get `shared_secret` for key_injector**

- **From gr-linux-crypto ECDH (Brainpool):** Use `gr_linux_crypto.CryptoHelpers.brainpool_ecdh(private_key, peer_public_key)` to obtain the ECDH shared secret (bytes). Pass that as `shared_secret` into `kgdss.key_injector(shared_secret, session_id, tx_seq)`. The Brainpool keys come from `CryptoHelpers.generate_brainpool_keypair()` or `load_brainpool_*_key(pem_data)`.
- **From GnuPG / PEM:** Use `kgdss.get_shared_secret_from_gnupg(my_private_key_pem, peer_public_key_pem)`, which uses gr-linux-crypto’s `CryptoHelpers` under the hood when available.

**Keyring: storing and loading GDSS keys**

- **gr-linux-crypto `KeyringHelper.add_key`** stores the key payload via a temp file; the keyring payload is the *filename* string, not the key bytes. So `KeyringHelper.read_key(key_id)` returns that path, not the key material. Do **not** use `KeyringHelper.add_key` for GDSS key material if you need to read raw key bytes later.
- **gr-k-gdss** uses `keyctl padd` (pipe) in `store_session_keys()` so the keyring payload is the actual key bytes. Use `kgdss.store_session_keys(keys)` to store derived keys and `kgdss.load_gdss_key(key_id)` to read the 32-byte GDSS masking key. Run in a context where `keyctl read` is allowed (e.g. normal terminal); in restricted environments `load_gdss_key` may fail and key_injector or constructor keying should use keys obtained elsewhere (e.g. ECDH in process).

**gr-linux-crypto blocks for GDSS**

- **GDSS Set Key Source** (gr_linux_crypto): Outputs the set_key PMT message. Set shared secret (64 hex chars), session_id, tx_seq; connect set_key_out to set_key of spreader and despreader. Key/nonce are derived automatically; message sent on flowgraph start.
- **Kernel Keyring Source** (gnuradio.linux_crypto) outputs key bytes as a **stream**, not a set_key message. Do not connect it directly to set_key. Use **key_injector** with keyring_id (gr-k-gdss) or **GDSS Set Key Source** (gr-linux-crypto) instead.

**Package names**

- **gr_linux_crypto** (Python package): `KeyringHelper`, `CryptoHelpers`, `GNURadioCryptoUtils`. Use for ECDH, HKDF (if needed), and keyring helpers.
- **gnuradio.linux_crypto** (GNU Radio block module, from gr-linux-crypto): `kernel_keyring_source`, ECIES blocks, etc. Use for flowgraph blocks that read keys from the keyring as a stream.

### Compatibility with gr-linux-crypto

GR-K-GDSS is designed to work with [gr-linux-crypto](https://github.com/gnuradio/gr-linux-crypto) (Python package `gr_linux_crypto`) for key derivation and optional kernel keyring storage.

**Required gr-linux-crypto APIs**

- **CryptoHelpers** (for ECDH and PEM key loading): `load_brainpool_private_key`, `load_brainpool_public_key`, `brainpool_ecdh`. Used by `get_shared_secret_from_gnupg()` in `session_key_derivation`.
- **KeyringHelper** (optional, for keyring store/load): `add_key`, `read_key`. Used by `store_session_keys()` and `load_gdss_key()` when keyctl is not available.

**Import paths**

GR-K-GDSS tries, in order: `gr_linux_crypto`, `gr_linux_crypto.keyring_helper`, `gr_linux_crypto.crypto_helpers`, `gr_linux_crypto.python.*`, `gnuradio.linux_crypto*`, and (when `GR_LINUX_CRYPTO_DIR` is set) `keyring_helper` / `crypto_helpers` from the gr-linux-crypto `python/` directory. This matches gr-linux-crypto installed via CMake (files under `gr_linux_crypto/`) or run from source with `GR_LINUX_CRYPTO_DIR` pointing at the gr-linux-crypto repo root.

**Keyring and keyctl**

- For **GDSS key storage and load**, raw 32-byte keys must be stored in the keyring. gr-linux-crypto’s `KeyringHelper.add_key` stores a **path string** in the key, not the key bytes, so `load_gdss_key()` cannot recover a 32-byte key from keys stored that way.
- **Recommended:** Install **keyutils** so that `keyctl` is on PATH. GR-K-GDSS then uses `keyctl padd` to store raw key bytes and `keyctl read` to load them; `store_session_keys()` and `load_gdss_key()` work correctly.
- If keyctl is not available, `store_session_keys()` and `load_gdss_key()` still use `KeyringHelper`, but keys stored via `KeyringHelper.add_key` will not be usable for GDSS (load will raise because the keyring value is not 32 bytes). Use keyctl for GDSS key round-trip.
- `KeyringHelper()` in gr-linux-crypto requires keyctl (keyutils) to be present; otherwise it raises. GR-K-GDSS turns that into a clear error suggesting to install keyutils.

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
