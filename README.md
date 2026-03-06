# GR-K-GDSS
A highly experimental Cryptographically keyed GDSS proposal.

# Cryptographically Keyed GDSS — A Comparison with Standard GDSS

**Status: Unreviewed theoretical design concept**

> **Important notice:** This document was written with the assistance of an AI
> (Claude, by Anthropic). It has not been reviewed by a professional
> cryptographer, a signals intelligence specialist, or any academic with
> relevant expertise. The theoretical claims presented here are based on
> logical reasoning from published sources and should be treated with
> appropriate scepticism. Where the word *theoretical* appears, the reader
> should apply their own critical judgement. Independent expert review is
> strongly recommended before any practical application.

---

## Table of Contents

1. Background
2. What is GDSS?
3. Standard GDSS — How It Works
4. The Weakness in Standard GDSS
5. Cryptographically Keyed GDSS — The Proposed Modification
6. All Layers of Security
7. Comparison — Standard GDSS vs Keyed GDSS
8. The Nitrokey and Emergency Disposal
9. What Remains Unresolved
10. Sources and Further Reading
11. Build and Install
12. [Usage](docs/USAGE.md)
13. [Examples](examples/)
14. [Testing](docs/TESTING.md)
15. [Test results](docs/TEST_RESULTS.md)

---

## 1. Background

This document describes a proposed modification to Gaussian-Distributed
Spread-Spectrum (GDSS), a covert radio communication scheme published in
2023 by researchers at Australia's Defence Science and Technology Group.

The modification proposes replacing GDSS's internal random masking source
with a cryptographically keyed source derived from an existing GnuPG key
infrastructure. The goal is to strengthen the already strong covertness
properties of GDSS by making the masking layer cryptographically opaque
rather than merely statistically random.

The construction uses entirely open source, freely available components
and is intended to run on commodity software-defined radio (SDR) hardware.

---

## 2. What is GDSS?

GDSS — Gaussian-Distributed Spread-Spectrum — is a spread-spectrum radio
communication scheme designed for covert or Low Probability of Detection
(LPD) communications.

The core idea is that a transmitted signal should be statistically
indistinguishable from the thermal noise that exists naturally in all
electronic equipment and in the radio environment. A passive observer
scanning the radio spectrum should see nothing but the noise floor —
no carrier, no modulation signature, no signal of any kind.

The scheme was published as an open access academic paper:

> Shakeel, I.; Hilliard, J.; Zhang, W.; Rice, M.
> *Gaussian-Distributed Spread-Spectrum for Covert Communications.*
> Sensors 2023, 23(8), 4081.
> https://doi.org/10.3390/s23084081

The paper demonstrates that GDSS defeats three standard signal detection
methods: higher-order moment analysis, modulation stripping, and
cyclostationary spectral analysis — all of which reliably detect
conventional spread-spectrum signals such as DSSS.

---

## 3. Standard GDSS — How It Works

A standard radio transmission carries a signal whose structure reveals
itself to anyone listening. Even when encrypted, the signal has
identifiable features: a carrier frequency, a modulation pattern, a
defined bandwidth, and statistical properties that differ from noise.

GDSS eliminates these features through a masking process:

1. The data to be transmitted is modulated using SOQPSK (Shaped Offset
   Quadrature Phase Shift Keying), a bandwidth-efficient continuous-phase
   modulation scheme.

2. As a example,- the modulated signal is spread across a wide bandwidth using a
   spreading factor of N=256, which distributes the signal energy across
500kHz or more, and reduces its power density to below the noise floor. This
   gives the legitimate receiver 24dB of processing gain through
   despreading — the ability to recover the signal from below what any
   passive observer can detect.

3. Each chip (the fundamental unit of the spread signal) has its
   in-phase (I) and quadrature (Q) components multiplied by values drawn
   from a Gaussian distribution — the same statistical distribution as
   thermal noise. This is the masking step.

4. The result is a signal whose amplitude distribution matches thermal
   white noise to the 20th statistical moment. Standard detectors find
   nothing to distinguish it from the natural noise floor.

The masking values in the original scheme are drawn from the
transmitter's own hardware thermal noise. The receiver does not need to
know these values — it recovers the signal through despreading without
stripping the masking.

---

## 4. The Weakness in Standard GDSS

Standard GDSS has one structural vulnerability: **the masking is random
but not secret.**

The algorithm is published and open. An adversary who captures the
transmitted IQ samples knows the masking values follow a Gaussian
distribution, even if they do not know the specific values. In principle,
with sufficient captured data and processing time, they could attempt to
characterise the masking statistically.

More practically, the synchronisation burst — a brief transmission needed
to establish timing between transmitter and receiver — uses a
conventional DSSS structure. In the standard design, this burst uses a
fixed or session-independent spreading sequence, transmitted at regular
or predictable intervals. A patient adversary recording radio traffic
over time could identify recurring burst patterns across sessions,
establishing that a communication relationship exists at that frequency,
even without decoding any content.

This is a traffic analysis vulnerability, not a content vulnerability —
but in operational contexts, confirming that communication is occurring
at all can be as valuable to an adversary as reading the content.

---

## 5. Cryptographically Keyed GDSS — The Proposed Modification

The modification replaces the internal random masking source with a
cryptographically keyed pseudo-random source. The masking values are
no longer drawn from hardware thermal noise — they are derived from a
ChaCha20 keystream, converted to Gaussian-distributed values using a
Box-Muller transform.

The key is derived from a BrainpoolP256r1 Elliptic Curve
Diffie-Hellman (ECDH) key exchange using pre-existing GnuPG keys.

### Key Derivation

Both the transmitter and receiver hold each other's GnuPG public keys,
exchanged off-air through the GnuPG web of trust. At session start:

```
Transmitter: own private key + receiver's public key → ECDH shared secret
Receiver:    own private key + transmitter's public key → ECDH shared secret
```

Both arrive at an identical shared secret without transmitting it.
This shared secret is fed into HKDF (a standard key derivation function,
RFC 5869) with domain separation, producing four independent 32-byte
subkeys:

| Subkey | Purpose |
|--------|---------|
| Key 1 | ChaCha20-Poly1305 payload encryption |
| Key 2 | ChaCha20 GDSS masking keystream |
| Key 3 | Sync burst PN sequence |
| Key 4 | Sync burst timing offset schedule |

### What Changes

The receiver now strips the masking using the identical keystream before
despreading, rather than despreading through the masking. This changes
the original design's elegant receiver-ignorance property — the receiver
now needs the key — but in exchange, the masking becomes
cryptographically opaque.

### The Sync Burst

The 2ms synchronisation burst is redesigned to mimic natural static
spikes in the radio environment:

- The PN spreading sequence is derived from Key 3 — unique per session,
  unknown to anyone without the session key
- The burst timing is randomised using Key 4 — the burst arrives at an
  unpredictable offset within a search window that both ends know
- A Gaussian amplitude envelope is applied so the burst's rise and fall
  profile resembles natural impulse noise rather than a keyed signal

---

## 6. All Layers of Security

The full stack provides multiple independent layers of protection.
Each layer is described below with its purpose and the standard it
relies on.

---

### Layer 1 — SOQPSK Modulation

**What it does:** SOQPSK (Shaped Offset Quadrature Phase Shift Keying)
is a continuous-phase, bandwidth-efficient modulation scheme. Its
near-constant envelope makes it well-suited to nonlinear power
amplifiers and reduces out-of-band emissions.

**Security contribution:** The continuous phase means there are no
abrupt transitions that reveal modulation structure to a passive
observer. It is the foundation on which the spreading and masking
layers operate.

---

### Layer 2 — GDSS Spreading and Masking

**What it does:** The modulated signal is spread across a wide bandwidth
(N=256 spreading factor, approximately 500kHz at typical chip rates) and
each chip is masked with Gaussian-distributed values derived from the
session key via ChaCha20 and Box-Muller transform.

**Security contribution:**

- Signal power is distributed across 500kHz or more,- at levels below the noise
  floor — approximately 24dB below detectable threshold for a passive
  observer without the spreading code
- The amplitude distribution of the transmitted signal matches thermal
  white noise statistically
- Higher-order moment detectors, cyclostationary analysers, and
  modulation stripping detectors all return null results
- The masking is cryptographically keyed — an adversary cannot strip
  the masking without the session key, even knowing the full algorithm

**Theoretical note:** Whether ChaCha20-derived Gaussian values (via
Box-Muller) are truly indistinguishable from hardware thermal noise
under all possible detection methods has not been formally verified.
This is an open question that requires expert cryptographic and signals
analysis review.

---

### Layer 3 — LDPC Forward Error Correction

**What it does:** Low Density Parity Check (LDPC) coding at rate 1/2
adds redundancy that allows the receiver to recover from transmission
errors. Block lengths of 576, 1152, or 2304 bits are supported.

**Security contribution:** Not a security layer directly, but it
recovers the approximately 2dB SNR penalty that GDSS masking introduces
relative to standard DSSS, allowing reliable communication deeper in
the noise floor.

---

### Layer 4 — ChaCha20-Poly1305 Payload Encryption

**What it does:** The payload data is encrypted using ChaCha20-Poly1305,
an Authenticated Encryption with Associated Data (AEAD) construction
standardised in RFC 8439.

**Security contribution:**

- ChaCha20 provides 256-bit symmetric encryption. It is designed by
  Daniel Bernstein with no involvement of NSA-influenced standards.
- Poly1305 provides a message authentication tag covering the entire
  ciphertext. Any modification, injection, or replay of the transmitted
  data causes authentication to fail at the receiver before decryption
  begins.
- Computationally infeasible to break with current or foreseeable
  classical computing.
- Resistant to timing side-channel attacks by design.

---

### Layer 5 — BrainpoolP256r1 Key Exchange

**What it does:** Elliptic Curve Diffie-Hellman (ECDH) key agreement
using the BrainpoolP256r1 curve, providing approximately 128 bits of
security against the best known classical attacks.

**Security contribution:**

- BrainpoolP256r1 is a BSI-standardised curve (German Federal Office
  for Information Security) developed without NSA involvement, avoiding
  the controversy surrounding NIST curves.
- Both sides compute the same shared secret independently from each
  other's public keys — the secret is never transmitted.
- Man-in-the-middle attacks are defeated by the GnuPG web of trust
  authentication layer beneath it — an attacker cannot substitute a
  fake public key that carries valid signatures from known keyholders.

---

### Layer 6 — GnuPG Web of Trust

**What it does:** GnuPG manages the public key infrastructure. Keys
are signed by known contacts who have verified the keyholder's identity
in person, building a chain of trust.

**Security contribution:**

- Identity authentication — a transmission cannot be forged by someone
  who has not physically met the legitimate keyholder and had their key
  signed.
- Key exchange happens entirely off-air, before any transmission.
- Standard GnuPG key servers distribute and synchronise public keys.
- Revocation certificates allow compromised keys to be invalidated.

---

### Layer 7 — Linux Kernel Keyring Storage

**What it does:** Session keys derived from the ECDH exchange are
stored in the Linux kernel keyring rather than in user-space files or
application memory.

**Security contribution:**

- Keys are protected by the kernel and inaccessible to user-space
  processes without authorisation.
- Keys are cleared from memory automatically when the associated
  hardware token is removed.

---

### Layer 8 — Nitrokey Hardware Security Module

**What it does:** The GnuPG private key is stored on a Nitrokey
hardware security device rather than on the computer's storage.

**Security contribution:**

- The private key never leaves the hardware device.
- All cryptographic operations requiring the private key are performed
  on the device itself.
- The device is PIN-protected with a minimum recommended PIN length of
  5 characters (alphanumeric).
- If the device is removed, all cached key material is immediately
  cleared from the computer's memory.
- Nitrokey supports firmware updates, allowing new cryptographic
  algorithms to be added without replacing hardware.

---

### Layer 9 — Operational Security

**What it does:** Movement, traffic discipline, and communication
practice that complement the technical stack.

**Security contribution:**

- Moving operators deny a passive observer the stable baseline
  measurements needed to detect noise floor anomalies
- Minimum transmission duration reduces the opportunity for any
  collection system to accumulate statistics
- Short, infrequent transmissions limit the value of any single
  intercept even in the unlikely event of detection
- These operational measures compound the technical protections —
  each layer independently raises the cost of detection or intercept

---

## 7. Comparison — Standard GDSS vs Keyed GDSS

All ratings are on a scale of 0–10. They assume correct implementation,
appropriate operational discipline, and moving operators with minimum
traffic. They do not represent a formal security evaluation.

**Delta** in the tables below is the difference (Keyed GDSS minus Standard GDSS). A positive delta means keyed GDSS scores higher on that aspect; zero means no change. The comparison is supported by the [IQ file analysis](docs/TESTING.md#iq-test-file-generation-and-analysis): cross-session sync burst correlation shows roughly 9x lower correlation for keyed GDSS than for standard GDSS, and keyed GDSS output passes the same noise-like statistical tests as synthetic Gaussian noise. The small residual cross-session correlation (~0.11) seen in keyed GDSS in the test suite is a simulation artifact; in a real channel it would be lower and is not considered exploitable.

### Detection Resistance

| Aspect | Standard GDSS | Keyed GDSS | Delta | Notes |
|--------|--------------|------------|-------|-------|
| Passive signal detection | 7 | 7 | 0 | Both look like thermal noise |
| Cyclostationary analysis | 8 | 8 | 0 | Both defeat it |
| Moments-based detection | 8 | 8 | 0 | Both defeat it |
| Modulation stripping | 8 | 8 | 0 | Both defeat it |
| Sync burst detection | 4 | 8 | +4 | Largest single improvement |
| Traffic pattern analysis | 5 | 8 | +3 | Session-unique keystreams |
| Noise floor elevation | 5 | 6 | +1 | Movement helps both |
| Direction finding | 5 | 5 | 0 | Physics — neither solves this |
| **Overall** | **6** | **7.5** | **+1.5** | |

### Decryption / Content Recovery Resistance

| Aspect | Standard GDSS | Keyed GDSS | Delta | Notes |
|--------|--------------|------------|-------|-------|
| Payload decryption | 9 | 9 | 0 | Identical — ChaCha20-Poly1305 |
| Masking strip attack | 4 | 9 | +5 | Critical difference |
| Statistical masking recovery | 5 | 9 | +4 | Keyed masking closes this |
| Forward secrecy | 7 | 9 | +2 | Past sessions protected |
| Key compromise blast radius | 6 | 8 | +2 | HKDF domain separation |
| **Overall** | **6** | **9** | **+3** | |

### Jamming Resistance

| Aspect | Standard GDSS | Keyed GDSS | Delta | Notes |
|--------|--------------|------------|-------|-------|
| Broadband noise jamming | 6 | 6 | 0 | N=256 processing gain — identical |
| Targeted carrier jamming | 8 | 8 | 0 | No visible carrier in either |
| Protocol-aware jamming | 5 | 7 | +2 | Unpredictable sync timing |
| Sync burst jamming | 4 | 7 | +3 | Random timing defeats targeting |
| Replay jamming | 5 | 7 | +2 | Session-unique keys reject replays |
| **Overall** | **5.5** | **7** | **+1.5** | |

### Summary

| Category | Standard GDSS | Keyed GDSS | Delta |
|----------|--------------|------------|-------|
| Detection resistance | 6 | 7.5 | +1.5 |
| Decryption resistance | 6 | 9 | +3 |
| Jamming resistance | 5.5 | 7 | +1.5 |
| **Overall** | **6** | **7.8** | **+1.8** |

The most significant improvement is decryption resistance. The keyed
masking converts the physical obscurity layer from statistical to
cryptographic, meaning the entire stack now rests on computational
hardness at every level rather than statistical properties at the bottom
and cryptographic properties at the top.

---

## 8. The Nitrokey, PIN Protection, and Emergency Disposal

The private key for the GnuPG key exchange is stored on a Nitrokey
hardware security device. This section covers all protection layers
the Nitrokey provides.

### PIN Protection

The Nitrokey requires a PIN before it will perform any cryptographic
operation. The recommended minimum PIN length is 5 alphanumeric
characters. This has two important consequences:

- A locked device that falls into an adversary's hands is immediately
  useless — they cannot use it to derive session keys or decrypt
  captured traffic without the PIN
- After a configurable number of incorrect PIN attempts (default: 3
  user PIN attempts, followed by a limited number of admin PIN
  attempts), the device permanently bricks itself and destroys the
  key material automatically

This means physical seizure of a locked, inactive Nitrokey is a dead
end for an adversary without any action required from the operator.
The auto-brick behaviour converts a wrong-PIN attack into permanent
key destruction.

**What the PIN does not protect against:**

When the device is inserted, unlocked, and actively in use, the PIN
is not in play. During an active session, session keys are held in the
Linux kernel keyring (not in user-space memory), but a sophisticated
adversary with physical access to a running, unlocked computer could
potentially extract session key material from memory. The PIN
protects the device at rest, not during active operation.

### Physical Disposal

Because the private key never leaves the device, the Nitrokey can be
physically destroyed in an emergency — breaking, crushing, burning,
or discarding it — which immediately and permanently eliminates the
private key.

Without the private key, an adversary cannot:
- Derive the session key for any past or future transmission
- Strip the GDSS masking from any captured IQ recordings
- Decrypt any captured payload data

This provides a last-resort means of cryptographic sanitisation that
requires no software access, no network connectivity, and no technical
knowledge to execute. The action is immediate and irreversible.

### Layered Key Compromise Resistance

| Scenario | Protection | Outcome for adversary |
|----------|-----------|----------------------|
| Device seized while locked | PIN + auto-brick after failed attempts | Key inaccessible, no action needed from operator |
| Device seized while unlocked/active | PIN not in play; session keys in kernel keyring | Potential exposure of active session only |
| Device seized; operator compelled to reveal PIN | Physical disposal before surrender | Key permanently destroyed |
| Device destroyed before seizure | Key gone with device | All past sessions unrecoverable |

**Important notes on disposal:**

- Disposing of one Nitrokey does not affect copies of the private key
  stored elsewhere. For full cryptographic sanitisation, all copies
  must be destroyed or revoked.
- A GnuPG revocation certificate should be uploaded to key servers
  after disposal if circumstances allow, to prevent the public key
  being used to impersonate the operator in future.

### Forward Secrecy — A Known Limitation

The GnuPG keys used for ECDH in this design are static long-term keys.
This means the design does **not** provide cryptographic forward
secrecy in the formal sense.

**What this means in practice:**

True forward secrecy (as implemented in TLS 1.3) generates a fresh
ephemeral keypair for every session, derives the session key, and
then immediately and permanently destroys the ephemeral private key.
Even if the long-term identity key is later compromised, past session
keys cannot be reconstructed and past sessions cannot be decrypted.

This design does not do that. If an adversary:

1. Records all radio traffic over an extended period, and
2. Later obtains the long-term GnuPG private key

They could retroactively derive all historical session keys and decrypt
all recorded sessions.

**However**, because key exchange in this design is entirely off-air
(public keys are exchanged in person through the GnuPG web of trust,
never over the radio channel), there is nothing to intercept on-air.
The harvest-now-decrypt-later threat therefore reduces to a single
question: *can the adversary obtain the long-term private key?*

The PIN protection, auto-brick behaviour, and physical disposal option
all address this directly. Nitrokey destruction before key seizure
renders all recorded historical sessions permanently unrecoverable —
which is the closest this design achieves to forward secrecy, through
operational means rather than cryptographic means.

**A formal forward secrecy modification would be:**

Use the long-term GnuPG keys only to authenticate an additional
ephemeral ECDH exchange. Both sides generate a fresh ephemeral
keypair at session start, exchange ephemeral public keys (signed with
their long-term keys to prevent impersonation), derive the session
key from the ephemeral shared secret, and immediately destroy the
ephemeral private key. Compromise of the long-term key would then
allow impersonation of future sessions but not decryption of past
ones. This modification has not been implemented in the current
design and is noted here as a recommended improvement for a future
revision.


---

## 9. What Remains Unresolved

The following questions have not been answered by expert review and
represent areas where the theoretical reasoning may be incomplete or
incorrect:

**Forward secrecy:**
This design uses static long-term GnuPG keys and does not implement
cryptographic forward secrecy. An adversary who records all radio
traffic and later obtains the long-term private key could retroactively
decrypt all historical sessions. Because key exchange is entirely
off-air, the practical risk is bounded by the security of the
Nitrokey and its PIN — but the architectural limitation remains. A
future revision should implement ephemeral ECDH authenticated by the
long-term keys, as described in Section 8.

**Box-Muller statistical properties:**
ChaCha20 produces uniformly distributed output. Box-Muller converts
pairs of uniform values into Gaussian-distributed values. Whether the
resulting output is truly indistinguishable from hardware thermal noise
under all possible detection methods — including methods not yet
considered — is an open question.

**Prior art:**
It is not known whether cryptographically keyed GDSS masking has been
proposed or implemented before. If prior art exists, it may identify
weaknesses in this construction that are not apparent from first
principles.

**Formal security proof:**
No formal security proof exists for this construction. The reasoning is
based on the properties of the individual components and their logical
combination, not on a mathematical proof of security.

**Quantum computing:**
BrainpoolP256r1 ECDH is vulnerable to Shor's algorithm on a
sufficiently powerful quantum computer. No such computer exists at
present, but this represents a long-term vulnerability of the key
exchange layer. ChaCha20-Poly1305 is considered quantum-resistant at
its current key size (Grover's algorithm reduces its effective security
from 256 bits to 128 bits, which remains adequate).

**Body of evidence:** The keyed GDSS construction produces output that is
statistically indistinguishable from Gaussian noise across all standard
detection metrics (mean, variance symmetry, kurtosis, skewness,
autocorrelation); see [Testing](docs/TESTING.md) and the IQ file analysis
there. Combined with the gr-linux-crypto NIST CAVP validation results
below, this is a meaningful body of evidence to present alongside the
design document.

**Implementation quality:**
The gr-linux-crypto module has an extensive test suite (413 passed,
31 skipped, 0 failed as of 2025-11-16). Cryptographic correctness has
been validated at multiple levels:

- **NIST CAVP test vectors:** AES-128-GCM 4/4 passing (100%),
  AES-256-GCM 4/4 passing (100%), RFC 8439 ChaCha20-Poly1305 3/3
  passing (100%), including full AAD (Additional Authenticated Data)
  support
- **Google Wycheproof vectors:** BrainpoolP256r1/P384r1/P512r1 ECDH
  validated against 2,534+ vectors; ECDSA validated against 475+
  vectors per curve — Wycheproof specifically targets subtle
  implementation bugs that basic compliance testing misses
- **BSI TR-03111 compliance:** 20/20 tests passed (curve parameters,
  key generation, ECDH, ECDSA, security levels)
- **Fuzzing:** 805+ million executions via LibFuzzer with
  AddressSanitizer and UndefinedBehaviorSanitizer — zero crashes,
  zero memory errors
- **CBMC formal verification:** 23/23 memory safety checks passed on
  the core encryption path (bounds checking, pointer safety)
- **Timing side-channel (dudect):** Authentication tag comparison and
  encryption timing both tested at ~17.5 million measurements each;
  maximum t-statistic 2.30 (threshold is 5) — no timing leakage
  detected
- **Cross-validation:** Compatible with OpenSSL 3.x and the Python
  cryptography library; OpenSSL CLI interoperability confirmed

The module is noted by its author as AI-generated code not reviewed
by professional programmers. The validation results above significantly
raise confidence beyond a typical unreviewed codebase, but they do not
substitute for a full independent code audit. The module is explicitly
not FIPS-140 certified, not evaluated for government or military use,
and is recommended by its author for amateur radio, experimental, and
research applications. It is built on top of OpenSSL and the Python
cryptography library, both of which use FIPS-140 validated backends.

---

## 10. Sources and Further Reading

**GDSS original paper (open access):**
Shakeel, I.; Hilliard, J.; Zhang, W.; Rice, M.
Gaussian-Distributed Spread-Spectrum for Covert Communications.
Sensors 2023, 23(8), 4081.
https://doi.org/10.3390/s23084081

**ChaCha20-Poly1305:**
Nir, Y.; Langley, A. RFC 8439 — ChaCha20 and Poly1305 for IETF Protocols.
https://www.rfc-editor.org/rfc/rfc8439

**BrainpoolP256r1:**
Lochter, M.; Merkle, J. RFC 5639 — Elliptic Curve Cryptography (ECC)
Brainpool Standard Curves and Curve Generation.
https://www.rfc-editor.org/rfc/rfc5639

**HKDF:**
Krawczyk, H.; Eronen, P. RFC 5869 — HMAC-based Extract-and-Expand
Key Derivation Function (HKDF).
https://www.rfc-editor.org/rfc/rfc5869

**GnuPG:**
https://www.gnupg.org

**GNU Radio:**
https://www.gnuradio.org

**gr-qradiolink (GNU Radio OOT module):**
https://github.com/Supermagnum/gr-qradiolink

**gr-linux-crypto (GNU Radio OOT module):**
https://github.com/Supermagnum/gr-linux-crypto

**gr-linux-crypto test results (NIST CAVP, Wycheproof, BSI TR-03111, fuzzing, dudect):**
https://github.com/Supermagnum/gr-linux-crypto/blob/master/tests/TEST_RESULTS.md

**Nitrokey:**
https://www.nitrokey.com

---

## 11. Build and Install

This repository contains a GNU Radio out-of-tree (OOT) module that implements the keyed GDSS spreader and despreader blocks, plus Python helpers for key derivation and sync burst utilities.

WARNING!   ITS HIGLY EXPERIMENTAL.  USE AT YOUR OWN RISK ! 

### Where to find what (documentation and file roles)

| What you need | Where it is |
|---------------|-------------|
| **Block API and Python helpers** (spreader, despreader, key injector; session key derivation, sync burst functions) | **[docs/USAGE.md](docs/USAGE.md)** — Block I/O and parameters, helper function reference, gr-linux-crypto/SOQPSK wiring, sync epoch window. |
| **Unit tests** (what each test file does, how to run) | **[docs/TESTING.md](docs/TESTING.md)** — Test suites T1/T2/T3 and cross-layer; per-test description; IQ file generation and analysis. |
| **Test results** (pytest and IQ analysis output) | **[docs/TEST_RESULTS.md](docs/TEST_RESULTS.md)** |
| **Example flowgraph** (TX with Codec2, ECIES, SOQPSK, GDSS) | **[examples/](examples/)** — `tx_example_kgdss.grc` and verification; see [examples/VERIFICATION_REPORT.md](examples/VERIFICATION_REPORT.md). |
| **C++ block implementation** (spreader/despreader logic) | **lib/** — `kgdss_spreader_cc_impl.cc`, `kgdss_despreader_cc_impl.cc`; headers in **include/gnuradio/kgdss/**. |
| **Python helpers** (key derivation, keyring, sync burst) | **python/** — `session_key_derivation.py`, `key_injector.py`, `sync_burst_utils.py`; API details in [docs/USAGE.md](docs/USAGE.md). |
| **GRC block definitions** | **grc/** — `kgdss_spreader_cc.block.yml`, `kgdss_despreader_cc.block.yml`, `kgdss_key_injector.block.yml`. |
| **Unit test scripts** | **tests/** — `test_t1_spreader_despreader.py`, `test_t2_sync_burst.py`, `test_t3_key_derivation.py`, `test_cross_layer.py`; described in [docs/TESTING.md](docs/TESTING.md). |
| **IQ test file generator and analyser** | **tests/generate_iq_test_files.py** (builds 01–13 and metadata), **tests/analyse_iq_files.py** (PASS/FAIL checks), **tests/plot_iq_comparison.py** (plots); see [docs/TESTING.md](docs/TESTING.md). |
| **Quick test run** | **tests/README.md** — Run commands; keyring/sandbox notes. |
| **Python bindings** (C++ blocks to Python) | **python/bindings/** — `kgdss_spreader_cc_python.cc`, `kgdss_despreader_cc_python.cc`, `kgdss_python.cc`; expose spreader/despreader and `kgdss_sync_state` to `gnuradio.kgdss`. |
| **Build system** | **CMakeLists.txt** (top level), **lib/CMakeLists.txt**, **python/CMakeLists.txt**, **python/bindings/CMakeLists.txt**, **grc/CMakeLists.txt**, **include/gnuradio/kgdss/CMakeLists.txt** — build and install the C++ library, Python package, and GRC blocks. |

**Usage documentation** is in **[docs/USAGE.md](docs/USAGE.md)**. There you will find:
- **Block API:** stream and message inputs/outputs, parameters, and usage for the three GNU Radio blocks (Keyed GDSS Spreader, Despreader, Key Injector), plus how to connect gr-linux-crypto and SOQPSK for TX/RX.
- **Python helper functions:** session key derivation and keyring (`derive_session_keys`, `store_session_keys`, `load_gdss_key`, `get_shared_secret_from_gnupg`, `gdss_nonce`, `payload_nonce`, `keyring_available`, `keyring_import_error`) and sync burst utilities (`derive_sync_schedule`, `derive_sync_pn_sequence`, `gaussian_envelope`). These are documented in the "Python helper functions" section; the blocks are documented in the "Keyed GDSS blocks" section.

### Examples

The **[examples/](examples/)** directory contains a ready-made GNU Radio Companion flowgraph:

- **tx_example_kgdss.grc** — A TX (transmit) example that wires: Audio Source (microphone) -> resampler -> Codec2 encoder -> Brainpool ECIES Multi-Recipient Encrypt (gr-linux-crypto) -> byte-to-bit unpack -> SOQPSK modulator (gr-qradiolink) -> Keyed GDSS Spreader -> Null Sink. The **Keyed GDSS Key Injector** block supplies key and nonce from the kernel keyring (variable `keyring_id`) and connects its message port to the spreader's `set_key` input. Replace the Null Sink with an osmocom or UHD Sink for real hardware output. Generate and run the flowgraph with `grcc tx_example_kgdss.grc` then `python3 tx_example_kgdss.py`. See [examples/VERIFICATION_REPORT.md](examples/VERIFICATION_REPORT.md) for verification steps.

**Brainpool ECIES parameters in the example:** gr-linux-crypto supports reading recipient public keys from the **kernel keyring** or from a JSON file. **key_store_path** is optional: leave it empty to use the keyring. Add recipient public keys to the keyring with `keyctl add user "callsign:W1ABC" "$(cat pubkey.pem)"` or from Python with `CallsignKeyStore(...).add_public_key(callsign, public_key_pem)`; the ECIES block then looks up keys by description `callsign:CALLSIGN`. Alternatively set **key_store_path** to a JSON file path for file-based store (see gr-linux-crypto docs). **callsigns** is the comma-separated list of recipient callsigns (e.g. `"ALICE,BOB"`); keys are resolved from the keyring or from the JSON file. If callsigns is empty, the block does not encrypt for any recipients.

### Dependencies

- **GNU Radio** 3.10 or newer (with development headers and Python bindings)
- **libsodium** (preferred) or **OpenSSL** (for ChaCha20 in the C++ blocks)
- **pybind11** (for Python bindings to the C++ blocks)
- **gr-linux-crypto** — install and build this module first; the Python helpers depend on it for `KeyringHelper` and `CryptoHelpers`
- **gr-qradiolink** — optional; provides the original GDSS blocks and SOQPSK; useful for reference and flowgraph examples
- **Python:** `pycryptodome`, `cryptography`, `numpy` (for the Python helpers and tests)

On Debian/Ubuntu you can install build dependencies and libsodium with:

```bash
sudo apt install build-essential cmake libgnuradio-dev libvolk-dev \
  libsodium-dev pkg-config python3-dev python3-numpy pybind11-dev
```

### Build

From the top level of this repository:

```bash
mkdir build
cd build
cmake .. -DCMAKE_INSTALL_PREFIX=/usr
make -j$(nproc)
```

If CMake reports that libsodium was not found, it will fall back to OpenSSL; ensure `libssl-dev` is installed in that case.

### Install

After a successful build:

```bash
sudo make install
sudo ldconfig
```

This installs the library, headers, Python package (`gnuradio.kgdss`), and GRC block descriptors. Ensure **gr-linux-crypto** is already installed so that the Python helpers can import it at runtime.

### Tests

Unit tests are in the `tests/` directory. Run them after installing the module (and gr-linux-crypto, for key derivation and cross-layer tests):

```bash
export PYTHONPATH="/usr/local/lib/python3.12/dist-packages:$PYTHONPATH"
pytest tests/ -v
```

- **[docs/TESTING.md](docs/TESTING.md)** — Full test inventory, how to run tests, and expected results (30 passed when keyctl and dependencies are available).
- **[docs/TEST_RESULTS.md](docs/TEST_RESULTS.md)** — Recorded pytest and IQ file analysis results (30 unit tests passed, 29 IQ checks passed).
- **tests/README.md** — Quick run instructions and per-suite notes; keyring round-trip is skipped if the Linux kernel keyring or `keyctl` is not available.

---

*This document was produced with AI assistance (Claude, Anthropic) and
has not been reviewed by a professional cryptographer or signals
intelligence specialist. It describes a theoretical design concept.
Nothing in this document constitutes professional cryptographic,
legal, or operational security advice.*
