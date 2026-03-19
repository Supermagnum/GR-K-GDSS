# GR-K-GDSS Usage

This document describes how to use the keyed GDSS blocks (spreader, despreader, and key injector), their inputs and outputs, and how to connect them with gr-linux-crypto and SOQPSK (gr-qradiolink) for TX/RX.

---

## Table of Contents

- [Block API summary](#block-api-summary)
- [Python helper functions](#python-helper-functions)
  - [Session key derivation and keyring](#session-key-derivation-and-keyring)
  - [Sync burst utilities](#sync-burst-utilities)
- [Keyed GDSS blocks](#keyed-gdss-blocks)
  - [kgdss_spreader_cc (Keyed GDSS Spreader)](#kgdss_spreader_cc-keyed-gdss-spreader)
  - [kgdss_despreader_cc (Keyed GDSS Despreader)](#kgdss_despreader_cc-keyed-gdss-despreader)
  - [kgdss_key_injector (Keyed GDSS Key Injector)](#kgdss_key_injector-keyed-gdss-key-injector)
  - [Sync burst timing and epoch window](#sync-burst-timing-and-epoch-window)
- [Connecting gr-linux-crypto and SOQPSK (TX/RX chains)](#connecting-gr-linux-crypto-and-soqpsk-txrx-chains)
  - [Getting keys into the GDSS blocks (automated, no manual entry)](#getting-keys-into-the-gdss-blocks-automated-no-manual-entry)
  - [gr-linux-crypto compatibility](#gr-linux-crypto-compatibility)
  - [Compatibility with gr-linux-crypto](#compatibility-with-gr-linux-crypto)
  - [ECIES key store: missing JSON or empty callsigns/groups](#ecies-key-store-missing-json-or-empty-callsignsgroups)
  - [TX chain: SOQPSK modulator and Keyed GDSS Spreader](#tx-chain-soqpsk-modulator-and-keyed-gdss-spreader)
- [RX chain: Keyed GDSS Despreader and SOQPSK demodulator](#rx-chain-keyed-gdss-despreader-and-soqpsk-demodulator)
- [DC spike and IQ imbalance (real SDR hardware)](#dc-spike-and-iq-imbalance-real-sdr-hardware)
- [Summary](#summary)

---

## Block API summary

All three blocks are in GRC under category **KGDSS / DSSS**.

| Block | Stream inputs | Stream outputs | Message inputs | Message outputs | Main parameters |
|-------|----------------|----------------|----------------|-----------------|-----------------|
| **Keyed GDSS Spreader** (`kgdss_spreader_cc`) | 1 complex (symbol rate) | 1 complex (chip rate) | `set_key` (optional) | none | sequence_length, chips_per_symbol, variance, seed, chacha_key, chacha_nonce |
| **Keyed GDSS Despreader** (`kgdss_despreader_cc`) | 1 complex (chip rate) | 3: complex (symbols), float (lock), float (SNR dB) | `set_key` (optional) | none | spreading_sequence, chips_per_symbol, correlation_threshold, timing_error_tolerance, chacha_key, chacha_nonce |
| **Keyed GDSS Key Injector** (`kgdss_key_injector`) | none | none | `trigger` (optional), `shared_secret` (optional) | `key_out` | keyring_id, shared_secret_hex, session_id, tx_seq |

**Spreader / Despreader message input `set_key`:** PMT dict with `"key"` (u8vector 32 bytes) and `"nonce"` (u8vector 12 bytes). Until a key is set, the spreader outputs zeros and the despreader outputs zeros on all stream ports. Connect **Key Injector** output `key_out` to both blocks' `set_key` input.

**Despreader status (query in Python after flowgraph runs):** `get_sync_state()` (returns `kgdss_sync_state` enum), `is_locked()`, `get_snr_estimate()`, `get_last_soft_metric()`, `get_frequency_error()`. The `kgdss_sync_state` enum values indicate sync/lock state of the despreader.

---

## Python helper functions

The module exposes Python helpers (not GNU Radio blocks) for session key derivation, keyring storage, and sync burst generation. Import with `from gnuradio import kgdss` or `import gnuradio.kgdss as kgdss`.

### Session key derivation and keyring

| Function | Purpose |
|----------|---------|
| **`derive_session_keys(ecdh_shared_secret, salt=None)`** | Derive session subkeys from the ECDH shared secret via HKDF-SHA256. Returns a dict with 32-byte keys: `"payload_enc"`, `"gdss_masking"`, `"sync_pn"`, `"sync_timing"`. Use `gdss_masking` for the spreader/despreader; `sync_pn` and `sync_timing` for sync burst helpers. |
| **`store_session_keys(keys)`** | Store a dict of name -> 32-byte key bytes in the Linux kernel keyring. Prefers `keyctl` (raw bytes); falls back to gr-linux-crypto KeyringHelper when keyctl is unavailable. Returns dict of name -> keyring key ID (string). Use the ID for `gdss_masking` with `load_gdss_key(int(id))`. |
| **`load_gdss_key(keyring_id)`** | Load the 32-byte GDSS masking key from the keyring by key ID (integer). Use the ID returned by `store_session_keys` for `"gdss_masking"`. Raises if the key is not 32 bytes or keyring is unavailable. |
| **`get_shared_secret_from_gnupg(my_private_pem, peer_public_pem)`** | Perform ECDH with BrainpoolP256r1 keys (PEM bytes). Returns raw shared secret; pass to `derive_session_keys()`. Requires gr-linux-crypto CryptoHelpers. |
| **`gdss_nonce(session_id, tx_seq)`** | Build the 12-byte nonce for the GDSS ChaCha20 masking keystream. Arguments: `session_id` (int), `tx_seq` (int). Returns 12 bytes (4-byte session_id big-endian + 8-byte tx_seq big-endian). Must match on TX and RX. |
| **`gdss_sync_burst_nonce(session_id)`** | Return the 12-byte nonce for sync-burst keyed masking. Use with `gdss_masking` when calling `apply_keyed_gaussian_mask` so the sync burst keystream is distinct from the data keystream. |
| **`payload_nonce(session_id, tx_seq)`** | Build the 96-bit nonce for payload ChaCha20-Poly1305 AEAD (e.g. gr-linux-crypto payload encryption). Format: prefix + session_id + tx_seq. Use with `payload_enc` from `derive_session_keys`. |
| **`keyring_available()`** | Return True if the keyring helper (keyctl or gr-linux-crypto KeyringHelper) is available. |
| **`keyring_import_error()`** | Return the exception message if keyring import failed, or None. Useful to report why keyring is unavailable. |

### Sync burst utilities

| Function | Purpose |
|----------|---------|
| **`derive_sync_schedule(master_key, session_id, window_ms=50)`** | Returns a callable `get_offset(epoch_ms)` that maps a nominal epoch (ms) to a burst offset in **[-window_ms, +window_ms]** ms. Use key `sync_timing` from `derive_session_keys`. Placement is deterministic for TX/RX, unpredictable to observers. See **Sync burst timing and epoch window** below for details. |
| **`derive_sync_pn_sequence(master_key, session_id, chips=10000)`** | Derive a session-unique pseudo-noise sequence for sync bursts. Uses `sync_pn` from `derive_session_keys`. Returns a float32 array of length `chips` with values +1.0 or -1.0 (BPSK-like). TX and RX get the same sequence for the same key and session_id. |
| **`gaussian_envelope(samples, rise_fraction=0.1)`** | Apply a Gaussian-shaped amplitude envelope to a burst (reduces sidelobes). `samples`: complex or real array; `rise_fraction`: fraction of length for rise/fall (default 0.1). Returns the array multiplied by the envelope (unity in center, ramps at edges). |
| **`apply_keyed_gaussian_mask(burst, gdss_key, nonce, variance=1.0)`** | Apply the same keyed Gaussian masking to a sync burst as used for GDSS data (ChaCha20 + Box-Muller). The burst becomes statistically indistinguishable from the GDSS waveform so a passive observer cannot tell sync from data or noise. Use `gdss_sync_burst_nonce(session_id)` for `nonce` so the sync keystream does not overlap the data keystream. See **Sync burst keyed masking** below. |
| **`gdss_sync_burst_nonce(session_id)`** | Returns the 12-byte nonce for sync-burst masking (session key derivation). Use with `gdss_masking` key when calling `apply_keyed_gaussian_mask` so the sync burst uses a keystream distinct from the data keystream. |

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

### Sync burst timing and epoch window

The optional **sync burst** (a short DSSS burst used for timing alignment) uses Python helpers in `gnuradio.kgdss` (or `sync_burst_utils`): `derive_sync_schedule`, `derive_sync_pn_sequence`, and `gaussian_envelope`. These are not GNU Radio blocks; you use them in your own logic or flowgraph code to decide when and where to insert a burst.

**How placement inside the epoch window is defined**

- **`derive_sync_schedule(master_key, session_id, window_ms=50)`** returns a callable **`get_offset(epoch_ms)`**.
- **Epoch** is a nominal time index in **milliseconds** (e.g. milliseconds since session start). You choose what values of `epoch_ms` correspond to “sync opportunities” (see below).
- **Window:** The parameter **`window_ms`** is the half-width of the offset window in ms. The burst’s **offset** (in ms) is in the range **[-window_ms, +window_ms]** relative to that nominal epoch time.
- **Placement:** For a given `epoch_ms`, the offset is computed deterministically from the session key (HMAC-SHA256 of `master_key` and `session_id` with domain `"sync-timing-v1"`), then ChaCha20 indexed by `epoch_ms` produces a value mapped into **[-window_ms, +window_ms]**. So TX and RX, with the same key and session_id, get the same offset for each epoch; different sessions get different patterns. **To an observer without the key, the placement is unpredictable** (they see only that bursts fall somewhere in the window); **TX and RX stay in agreement** because they both compute the same offset from the shared secret.

**How often sync bursts occur**

- **gr-k-gdss does not define the sync burst rate.** The schedule only maps “epoch index” -> “offset in window”. Your **application or protocol** decides how often there is a sync epoch (e.g. every 10 s, every 60 s) and what `epoch_ms` to pass (e.g. 0, 10000, 20000, …). So the **frequency of sync bursts is an application choice**, not fixed by the module.
- Burst **duration** (e.g. 2 ms) and **window** (e.g. +/-50 ms) are parameters you use when generating the burst and calling `get_offset`; the **period between bursts** is whatever your design uses for epoch spacing.

**Sync burst keyed masking (indistinguishable from GDSS data)**

Without masking, a sync burst is a recognizable DSSS waveform (chip-rate, BPSK-like), which can reveal to a passive observer that a transmission is occurring even if content stays protected. To avoid that, **apply the same keyed Gaussian masking to the sync burst as to the data** using `apply_keyed_gaussian_mask`. Then the burst has the same Gaussian-noise-like statistics as the GDSS data waveform and does not stand out against the noise floor. Timing remains hidden by the ChaCha20-derived offset from `derive_sync_schedule`; only the burst waveform itself is masked.

Recommended flow for generating a keyed sync burst:

1. Derive the PN sequence with `derive_sync_pn_sequence(sync_pn_key, session_id, chips)`.
2. Shape the burst (e.g. cast to complex, apply `gaussian_envelope`).
3. Call `apply_keyed_gaussian_mask(burst, gdss_masking_key, gdss_sync_burst_nonce(session_id), variance=1.0)`.
4. Scale the result so its power matches the surrounding GDSS or noise floor (e.g. same RMS as data), then insert it at the offset given by `derive_sync_schedule`.

Use `gdss_sync_burst_nonce(session_id)` (not the data nonce) so the sync-burst ChaCha20 keystream is separate from the data keystream. The receiver inverts the mask with the same key and nonce, then correlates with the known PN to detect the burst.

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
   - **shared_secret** message port: Connect a block that sends the ECDH shared secret once (at least 32 bytes; see **ECDH shared secret length** below); key_injector derives and sends set_key when the message arrives.
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

**Shamir's Secret Sharing (gr-linux-crypto):** For K-of-N quorum decryption (e.g. at least K recipients must cooperate to decrypt), use gr-linux-crypto's `encrypt_shamir(plaintext, recipients, curve)` and `decrypt_shamir(...)` / `get_share_from_shamir_block(...)`. Low-level APIs: `split(secret, threshold_k, num_shares_n, prime, curve)`, `reconstruct(shares, prime, secret_length, curve)`, `create_shamir_backed_key(...)`, `reconstruct_session_key(shares, prime, curve)`. Max secret size is 31 / 47 / 63 bytes for P256 / P384 / P512. A session key reconstructed with `reconstruct_session_key` can be passed to `derive_session_keys` (e.g. as the ECDH shared secret) or used with the key injector if it is 32 bytes (e.g. from `create_shamir_backed_key`). See [GLOSSARY.md](GLOSSARY.md#shamirs-secret-sharing).

### gr-linux-crypto compatibility

gr-k-gdss is designed to work with gr-linux-crypto for key storage and ECDH. Use the following to keep behaviour and key handling compatible.

**Where to get `shared_secret` for key_injector**

- **From gr-linux-crypto ECDH (Brainpool):** Use `gr_linux_crypto.CryptoHelpers.brainpool_ecdh(private_key, peer_public_key)` to obtain the ECDH shared secret (bytes). Pass that as `shared_secret` into `kgdss.key_injector(shared_secret, session_id, tx_seq)`. The Brainpool keys come from `CryptoHelpers.generate_brainpool_keypair()` or `load_brainpool_*_key(pem_data)`.
- **From GnuPG / PEM:** Use `kgdss.get_shared_secret_from_gnupg(my_private_key_pem, peer_public_key_pem)`, which uses gr-linux-crypto’s `CryptoHelpers` under the hood when available.

**ECDH shared secret length (Brainpool curve sizes)**

gr-linux-crypto and other ECDH implementations can use different Brainpool curves; the raw shared secret length in bytes equals the curve size (e.g. P256r1 gives 32 bytes, P384r1 gives 48 bytes, P512r1 gives 64 bytes). gr-k-gdss behaves as follows:

| Curve (bits) | Shared secret (bytes) | key_injector constructor | key_injector shared_secret message | derive_session_keys (HKDF) |
|--------------|------------------------|--------------------------|------------------------------------|----------------------------|
| 160, 192, 224 | 20, 24, 28 | Rejected: requires at least 32 bytes | Ignored (payload &lt; 32 bytes) | Would accept; not used by key_injector |
| 256 (P256r1) | 32 | Supported; full secret used | Supported; full secret used | Full entropy used |
| 320, 384, 512 | 40, 48, 64 | Supported; full secret used | Supported; full secret used | Full entropy used |

- **Minimum 32 bytes:** The key_injector requires at least 32 bytes so that HKDF has sufficient input; curves with shared secrets shorter than 32 bytes (160, 192, 224 bits) are not supported.
- **Longer secrets:** For 32-byte and longer secrets, the full byte string is passed to HKDF; no truncation. Use 256-bit or larger curves (e.g. BrainpoolP256r1, P384r1, P512r1) for best practice.

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

GR-K-GDSS is designed to work with [gr-linux-crypto](https://github.com/gnuradio/gr-linux-crypto) (Python package `gr_linux_crypto`) for key derivation and optional kernel keyring storage. Compatibility has been verified against the current gr-linux-crypto Python package: `KeyringHelper`, `CryptoHelpers`, `CallsignKeyStore`, `MultiRecipientECIES`, `HPKEBrainpool`, Shamir helpers (`split`, `reconstruct`, `create_shamir_backed_key`, `reconstruct_session_key`, etc.), `nitrokey_bridge` (`decrypt_with_card`, `get_keygrip_from_key_id`), `fips_status`, `secure_zero`, and BSI algorithm boundary (`check_algorithm_compliance`, `require_bsi_approved`, `list_approved_algorithms`). GR-K-GDSS only requires `KeyringHelper` and `CryptoHelpers`; the rest are optional for payload encryption and key management. The same shared secret and HKDF usage (full secret, info `gdss-chacha20-masking-v1`, salt, nonce format) are used so that gr-linux-crypto's GDSS Set Key Source and GR-K-GDSS key injector derive the same GDSS key and nonce for a given session.

**Required gr-linux-crypto APIs**

- **CryptoHelpers** (for ECDH and PEM key loading): `load_brainpool_private_key`, `load_brainpool_public_key`, `brainpool_ecdh`. Used by `get_shared_secret_from_gnupg()` in `session_key_derivation`.
- **KeyringHelper** (optional, for keyring store/load): `add_key`, `read_key`. Used by `store_session_keys()` and `load_gdss_key()` when keyctl is not available.

**Import paths**

GR-K-GDSS tries, in order: `gr_linux_crypto`, `gr_linux_crypto.keyring_helper`, `gr_linux_crypto.crypto_helpers`, `gr_linux_crypto.python.*`, `gnuradio.linux_crypto*`, and (when `GR_LINUX_CRYPTO_DIR` is set) `keyring_helper` / `crypto_helpers` from the gr-linux-crypto `python/` directory. This matches gr-linux-crypto installed via CMake (files under `gr_linux_crypto/`) or run from source with `GR_LINUX_CRYPTO_DIR` pointing at the gr-linux-crypto repo root. If the package root fails to import (e.g. a new optional dependency), set `GR_LINUX_CRYPTO_DIR` to the gr-linux-crypto source directory so GR-K-GDSS can load `keyring_helper` and `crypto_helpers` from the `python/` folder.

**Keyring and keyctl**

- For **GDSS key storage and load**, raw 32-byte keys must be stored in the keyring. gr-linux-crypto’s `KeyringHelper.add_key` stores a **path string** in the key, not the key bytes, so `load_gdss_key()` cannot recover a 32-byte key from keys stored that way.
- **Recommended:** Install **keyutils** so that `keyctl` is on PATH. GR-K-GDSS then uses `keyctl padd` to store raw key bytes and `keyctl read` to load them; `store_session_keys()` and `load_gdss_key()` work correctly.
- If keyctl is not available, `store_session_keys()` and `load_gdss_key()` still use `KeyringHelper`, but keys stored via `KeyringHelper.add_key` will not be usable for GDSS (load will raise because the keyring value is not 32 bytes). Use keyctl for GDSS key round-trip.
- `KeyringHelper()` in gr-linux-crypto requires keyctl (keyutils) to be present; otherwise it raises. GR-K-GDSS turns that into a clear error suggesting to install keyutils.

### ECIES key store: missing JSON or empty callsigns/groups

When using gr-linux-crypto's Brainpool ECIES multi-recipient encrypt block (e.g. in the tx_example_kgdss flowgraph), keys are resolved from **key_store_path** (JSON file) and/or the **kernel keyring**. When the JSON file or the callsigns list is missing or empty, the module **falls back to encrypting to all available public keys** (from the file and the keyring). Only when there are no keys at all does encryption fail.

**Fallback: encrypt to all available keys**  
If **callsigns** is empty (or not set), the block uses **all available recipient callsigns**: those in the key store file (callsign-to-PEM or keygrip), those in the kernel keyring (e.g. `callsign:W1ABC`), and group members that have a resolvable key (so a file with only groups still allows "encrypt to all" when the members' keys are in the keyring). Missing or empty JSON, or empty callsigns, therefore results in "encrypt to all available" as long as at least one key exists in the file or keyring.

**No JSON file (path missing or file does not exist)**  
The key store loads an empty set from the file; it does not raise. Recipient keys come from the keyring when **use_keyring** is true. With **callsigns** empty, the block encrypts to all keyring callsigns (fallback). If there are no keyring keys either, there are no recipients and encryption fails (Python API raises; C++ block may output nothing).

**JSON file exists but is empty `{}`**  
Same as above: no keys from the file; keyring is used for the fallback when callsigns are empty.

**JSON file has only groups (e.g. `{"net1": ["W1ABC", "W2ABC"]}`) and no callsign-to-PEM entries**  
Only the key store’s *callsign* list is used for “encrypt to all”; group names are not public keys. Group members that have a key in the keyring are included in "all available". With **callsigns** empty, the block encrypts to all such members; the fallback still works when members' keys are only in the keyring. To encrypt explicitly for a group, resolve the group to a callsign list (e.g. `CallsignKeyStore.get_group("net1")`) and pass it as **callsigns**. Passing a group name as a callsign (e.g. `["net1"]`) fails because group names are not public keys.

**Callsigns empty and no keys in store (file + keyring)**  
Only in this case does encryption fail: Python API raises *"No recipients: provide a non-empty callsign list or add keys to the key store."*; the C++ block may output nothing.

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

### DC spike and IQ imbalance (real SDR hardware)

The **Keyed GDSS Spreader** and **Keyed GDSS Despreader** do **not** implement correction for RTL-SDR-style **DC spikes** or **IQ imbalance**. Those effects come from the analog front end and tuner, not from the GDSS algorithm. You must handle them in the **RF / channel part** of your GNU Radio flowgraph (or by tuning/calibration outside GNU Radio).

#### DC spike (strong energy at 0 Hz)

Many low-cost SDRs (including typical RTL-SDR dongles) show a **large component at exactly DC** in complex baseband: local oscillator leakage and related imperfections. If your **wanted signal is centered at 0 Hz**, that spike sits on top of the signal and can **corrupt demodulation** (similar problems are common for APRS and other DC-centered modes on such hardware).

**How to account for it in practice:**

1. **Tune off DC (often the best approach):** Set the RF frequency or IF offset so the **signal of interest is not at DC** (e.g. a few tens or hundreds of kHz away). The despreader and downstream blocks then see the signal **offset** in baseband; your resampling and carrier recovery (if any) must match how you shifted the spectrum.
2. **DC blocking / high-pass filtering:** Insert GNU Radio blocks such as **DC Block** (real or complex, depending on your chain) or a **high-pass filter** with a very low cutoff **before** the despreader, after the source and any mandatory low-pass anti-alias filtering. Trade-off: you **remove or attenuate true DC**, which can leave a **notch** at 0 Hz in displays and slightly distort any energy that really sits on DC.
3. **Avoid stacking DC-sensitive stages:** If you already use a strong DC block, check that symbol timing and SNR estimates still behave as expected; extreme settings can affect slow drift or very narrowband signals.

The **test and plot scripts** in this repository subtract mean or drop the DC bin for **visualization only**; that is not a substitute for a proper receive chain on live hardware.

#### IQ imbalance (gain and phase mismatch on I and Q)

Real receivers rarely have **perfect I/Q matching**. Slight **gain imbalance** and **phase error** (not exactly 90 degrees between I and Q) create a **mirror image** of the spectrum: energy leaks across positive/negative frequency. Near DC, the mirror can fold **close to the desired signal** and **reduce SNR**.

**How to account for it in practice:**

1. **Hardware / driver calibration:** Some sources and drivers expose **IQ balance** or correction; use them when available.
2. **GNU Radio correction blocks:** For sources without built-in correction, consider blocks such as **IQ Balance** (correcting amplitude/phase imbalance on complex streams) in the path **after** the SDR source and **before** the despreader, tuned on a known test signal or calibration procedure.
3. **System margin:** If correction is imperfect, plan for **extra SNR margin** and validate lock/SNR on your hardware.

For interpretation of **recorded** IQ with mirrors and spurs near DC, see the real-noise spectrum notes in [TEST_RESULTS.md](TEST_RESULTS.md) and [TESTING.md](TESTING.md).

### Summary

| Stage        | Block (module)        | Input           | Output                          |
|-------------|------------------------|-----------------|----------------------------------|
| TX modulate | SOQPSK Modulator      | bits/symbols   | complex, symbol rate            |
| TX spread   | Keyed GDSS Spreader   | complex, sym rate | complex, chip rate           |
| RX despread | Keyed GDSS Despreader | complex, chip rate | (0) complex sym rate, (1) lock, (2) SNR |
| RX demod    | SOQPSK Demodulator    | complex, symbol rate | bits/symbols               |

Keys and nonce are set at flowgraph build time from the keyring (e.g. via `load_gdss_key` and `gdss_nonce` in Python, or hex variables in GRC). gr-linux-crypto supplies key storage and ECDH/payload crypto; gr-qradiolink supplies SOQPSK; gr-k-gdss supplies the keyed GDSS spreader and despreader between SOQPSK and the channel.
