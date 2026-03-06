# Technical Terms Index

Definitions of technical terms and acronyms used in the GR-K-GDSS documentation and codebase.

---

## Table of Contents

- [AEAD](#aead)
- [Box-Muller transform](#box-muller-transform)
- [ChaCha20](#chacha20)
- [Chip / chips per symbol](#chip--chips-per-symbol)
- [Covert communications](#covert-communications)
- [Despreader](#despreader)
- [ECDH](#ecdh)
- [GDSS](#gdss)
- [GRC](#grc)
- [HKDF](#hkdf)
- [IQ (I and Q)](#iq-i-and-q)
- [Key injector](#key-injector)
- [Keyed GDSS](#keyed-gdss)
- [Keystream](#keystream)
- [Keyring (Linux kernel keyring)](#keyring-linux-kernel-keyring)
- [keyctl](#keyctl)
- [LPD](#lpd)
- [Nonce](#nonce)
- [OOT module](#oot-module)
- [PN sequence](#pn-sequence)
- [Session key derivation](#session-key-derivation)
- [set_key (message port)](#set_key-message-port)
- [SOQPSK](#soqpsk)
- [Spreader](#spreader)
- [Spreading sequence](#spreading-sequence)
- [Standard GDSS](#standard-gdss)
- [Sync burst](#sync-burst)

---

## AEAD

**Authenticated Encryption with Associated Data.** An encryption mode that provides both confidentiality and integrity (authentication). In this project, payload encryption uses ChaCha20-Poly1305 AEAD (e.g. via gr-linux-crypto). The ciphertext is authenticated so that tampering can be detected.

---

## Box-Muller transform

A method to convert uniformly distributed random numbers into normally (Gaussian) distributed numbers. GR-K-GDSS uses it to turn the ChaCha20 keystream (uniform bytes) into Gaussian-distributed mask values for the spreader, so the transmitted signal is statistically indistinguishable from Gaussian noise.

---

## ChaCha20

A stream cipher that produces a pseudorandom keystream from a 256-bit key and a 96-bit nonce. GR-K-GDSS uses ChaCha20 to generate the masking values for the GDSS spreader (after conversion via Box-Muller to Gaussian). The same key and nonce must be used on transmitter and receiver.

---

## Chip / chips per symbol

A **chip** is one sample of the spread signal at the spreading (chip) rate. **Chips per symbol** is the spreading factor: each input symbol is expanded into this many chips. For example, with `chips_per_symbol = 256`, one symbol becomes 256 complex chip samples. The chip rate is the symbol rate multiplied by chips per symbol.

---

## Covert communications

Radio communications designed to avoid detection by passive observers. The transmitted signal is made to look like background noise (e.g. thermal noise) so that spectrum analysis or energy detection does not reveal that a transmission is taking place. GDSS is a covert spread-spectrum scheme.

---

## Despreader

The receive-side block that reverses spreading: it correlates the incoming chip-rate signal with the same spreading sequence and key-derived mask used by the spreader, then outputs symbol-rate complex samples. In GR-K-GDSS the block is `kgdss_despreader_cc` (Keyed GDSS Despreader). It requires the same key, nonce, and parameters as the spreader to recover the payload.

---

## ECDH

**Elliptic Curve Diffie-Hellman.** A key-agreement protocol where two parties derive a shared secret from their private key and the other party’s public key. GR-K-GDSS uses ECDH (e.g. Brainpool P-256) to obtain a shared secret; that secret is then fed into HKDF for session key derivation (payload encryption key, GDSS masking key, sync keys, etc.).

---

## GDSS

**Gaussian-Distributed Spread-Spectrum.** A spread-spectrum radio scheme designed for covert (LPD) communications. The transmitted signal is made to look statistically like Gaussian noise so that passive observers cannot distinguish it from the noise floor. The original design uses an internal random source for masking; keyed GDSS replaces that with a cryptographically keyed source (ChaCha20 + Box-Muller).

---

## GRC

**GNU Radio Companion.** The graphical editor for building GNU Radio flowgraphs. Block parameters and connections are edited in GRC; the flowgraph can be exported to Python. The GR-K-GDSS blocks (spreader, despreader, key injector) appear in GRC under the KGDSS / DSSS category.

---

## HKDF

**HMAC-based Key Derivation Function.** A standard way to derive one or more cryptographic keys from a shared secret (e.g. from ECDH). GR-K-GDSS uses HKDF-SHA256 to derive session subkeys: payload encryption, GDSS masking, sync PN, and sync timing from the ECDH shared secret.

---

## IQ (I and Q)

**In-phase and Quadrature.** The two components of a complex baseband signal. I is the real part, Q is the imaginary part. IQ files (e.g. `.cf32`) store complex samples as interleaved float32 (I, Q, I, Q, ...). Analysis of GDSS often checks that I and Q have similar statistics (mean near zero, symmetric variance, Gaussian-like distribution).

---

## Key injector

A GR-K-GDSS block (`kgdss_key_injector`) that supplies the GDSS key and nonce to the spreader and despreader. It can load the key from the Linux kernel keyring (by key ID), from an ECDH shared secret given at construction, or from a message port. It outputs a `set_key` message so that key material is not hardcoded in the flowgraph.

---

## Keyed GDSS

The GR-K-GDSS variant of GDSS where the masking is driven by a cryptographic key (and nonce) instead of an internal random source. Only a receiver with the same key and nonce can despread the signal. This reduces cross-session correlation and strengthens covertness compared to standard GDSS.

---

## Keystream

The stream of pseudorandom bytes (or bits) produced by a stream cipher such as ChaCha20. In keyed GDSS, the keystream is converted to Gaussian values (Box-Muller) and used to mask the spread symbols so the output looks like noise.

---

## Keyring (Linux kernel keyring)

A kernel facility for storing keys and other security-sensitive data. GR-K-GDSS can store session-derived keys (e.g. the GDSS masking key) in the keyring via `store_session_keys` and later load them with `load_gdss_key` so that key material is not kept in process memory longer than needed. Requires `keyctl` (keyutils) for full support.

---

## keyctl

Command-line and API interface to the Linux kernel keyring. Used by GR-K-GDSS to store and read keys (e.g. `keyctl padd`, `keyctl read`). If `keyctl` is not available or the process cannot access the keyring (e.g. in a sandbox), the keyring round-trip tests and key-injector keyring mode may be unavailable.

---

## LPD

**Low Probability of Detection.** A property of covert communications: an adversary scanning the spectrum has low probability of detecting that a transmission is present. GDSS is designed for LPD by making the waveform statistically similar to thermal noise.

---

## Nonce

**Number used once.** A value that must be unique for each encryption or keystream use with the same key. In GR-K-GDSS, the GDSS masking uses a 12-byte nonce (e.g. from `gdss_nonce(session_id, tx_seq)`). The sync burst uses a separate nonce (`gdss_sync_burst_nonce(session_id)`) so that sync and data keystreams do not overlap.

---

## OOT module

**Out-of-Tree module.** A GNU Radio module that is not part of the core GNU Radio repository. GR-K-GDSS is an OOT module: it is built and installed separately and provides blocks (spreader, despreader, key injector) and Python helpers to the rest of the flowgraph.

---

## PN sequence

**Pseudo-Noise sequence.** A deterministic sequence that looks random (e.g. balanced +1/-1 symbols). In GR-K-GDSS, the sync burst uses a key-derived PN sequence so that only a receiver with the same key can correlate and detect the burst. The sequence is derived per session (e.g. via `derive_sync_pn_sequence`).

---

## Session key derivation

The process of deriving multiple subkeys (payload encryption, GDSS masking, sync PN, sync timing) from a single shared secret (e.g. ECDH output) using HKDF. GR-K-GDSS uses `derive_session_keys()` so that one ECDH exchange yields all keys needed for a session; keys are domain-separated to avoid reuse across purposes.

---

## set_key (message port)

A message input port on the keyed GDSS spreader and despreader. When the block receives a PMT dict with `"key"` (32-byte u8vector) and `"nonce"` (12-byte u8vector), it updates its internal ChaCha20 context and uses that for masking. The key injector (or gr-linux-crypto GDSS Set Key Source) typically connects to this port so keys are injected at runtime rather than at block construction.

---

## SOQPSK

**Shaped Offset QPSK.** A bandwidth-efficient modulation used for the symbol stream before spreading. In the GR-K-GDSS workflow, the payload is modulated with SOQPSK (e.g. via gr-qradiolink), then the complex symbols are spread and masked by the keyed GDSS spreader. On receive, the despreader outputs symbol-rate complex samples that are fed into the SOQPSK demodulator.

---

## Spreader

The transmit-side block that takes symbol-rate complex symbols, expands each symbol into multiple chips using a spreading sequence, and multiplies by a keyed Gaussian mask. The output is chip-rate complex samples that look like Gaussian noise. In GR-K-GDSS the block is `kgdss_spreader_cc` (Keyed GDSS Spreader).

---

## Spreading sequence

The base sequence (e.g. Gaussian-distributed, of length `sequence_length`) that is used to expand one symbol into many chips. In keyed GDSS this sequence is combined with the ChaCha20-derived mask so that the effective spreading is key-dependent and the waveform is opaque without the key.

---

## Standard GDSS

The original GDSS design that uses an internal (non-keyed) random source for the Gaussian masking. Standard GDSS is statistically noise-like but can exhibit high cross-session correlation (e.g. sync bursts from different sessions correlate), which keyed GDSS reduces by making the mask key-dependent.

---

## Sync burst

A short, keyed burst (e.g. PN sequence with Gaussian envelope) inserted into the transmission so the receiver can detect timing and lock. In keyed GDSS the sync burst is masked with the same family of keyed Gaussian masking (using a dedicated nonce) so that it is also noise-like and does not leak key or session information across sessions.
