# GR-K-GDSS Usage

This document describes how to use the keyed GDSS spreader and despreader blocks, their inputs and outputs, and how to connect them with gr-linux-crypto and SOQPSK (gr-qradiolink) for TX/RX.

---

## Keyed GDSS spreader and despreader blocks

The core of this OOT module is a pair of keyed GDSS blocks:

- `kgdss_spreader_cc` (GRC: **Keyed GDSS Spreader**)
- `kgdss_despreader_cc` (GRC: **Keyed GDSS Despreader**)

Both must be configured with **matching parameters and the same ChaCha20 key/nonce pair** for a given session. Key and nonce can be set at construction time or at runtime via the **set_key** message port.

**set_key message port:** Both blocks have a message input port `set_key`. When a message arrives (PMT dict with keys `"key"` and `"nonce"`, each a u8vector of 32 and 12 bytes), the block updates its internal ChaCha20 context and resets the keystream counter. Until a key is set (either at construction or via message), the block outputs zeros. This allows key material to stay in the kernel keyring until the moment it is needed and supports re-keying without restarting the flowgraph.

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

**Recommended: set_key message port and key_injector**

The cleanest approach is to key the blocks at runtime via the **set_key** message port, using the **key_injector** Python block. Key material then travels as bytes through GNU Radio's message system and can stay in the kernel keyring until the key_injector derives and sends it; the flowgraph can be re-keyed without restart.

1. Build the spreader and despreader with **empty key and nonce** (e.g. in Python pass `b""` and `b""` so the blocks wait for a set_key message).
2. Add a **key_injector** block (gr-k-gdss Python): `key_injector(shared_secret, session_id, tx_seq)`. It derives the GDSS key and nonce and formats them as a PMT message.
3. Connect **key_injector.key_out** to the **set_key** message port of both the spreader and the despreader (use a message copy or duplicate connection if your flowgraph API supports it).
4. At flowgraph start, either connect a message strobe (one-shot) to **key_injector.trigger**, or call **key_injector.inject()** once after `tb.start()` to send the key.

```
[Message Strobe / trigger] --> [key_injector] key_out --> set_key (spreader)
                                    |                --> set_key (despreader)
```

Key injector (Python):

```python
from gnuradio import kgdss

# ECDH shared secret (e.g. from keyring or get_shared_secret_from_gnupg)
shared_secret = ...  # bytes, at least 32 bytes
injector = kgdss.key_injector(shared_secret, session_id=0, tx_seq=1)
# Connect injector.key_out to spreader.set_key and despreader.set_key (message ports)
# Then: injector.inject()  # or use trigger port with a message strobe
```

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

**gr-linux-crypto Kernel Keyring Source block**

- The gr-linux-crypto block module (**gnuradio.linux_crypto**) provides `kernel_keyring_source(key_id, auto_repeat)`, which outputs key bytes as a **stream** (one byte per sample). The GDSS spreader/despreader need key+nonce as a **single set_key message** (PMT dict). So you cannot connect the Kernel Keyring Source stream output directly to the set_key port. To use the keyring with GDSS either: (1) use **key_injector** with a `shared_secret` obtained in Python (e.g. from ECDH or from `load_gdss_key` + manual nonce), or (2) load the GDSS key in Python with `load_gdss_key(int(key_id))`, build the set_key PMT dict (key 32 bytes, nonce 12 bytes), and send it once to the set_key ports.

**Package names**

- **gr_linux_crypto** (Python package): `KeyringHelper`, `CryptoHelpers`, `GNURadioCryptoUtils`. Use for ECDH, HKDF (if needed), and keyring helpers.
- **gnuradio.linux_crypto** (GNU Radio block module, from gr-linux-crypto): `kernel_keyring_source`, ECIES blocks, etc. Use for flowgraph blocks that read keys from the keyring as a stream.

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
