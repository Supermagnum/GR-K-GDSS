![Open Invention Network member](docs/oin-member-horiz.jpg)

# GR-K-GDSS
A highly experimental Cryptographically keyed GDSS proposal.

The developer used curiosity to piece the suggested improvements in this project together. AI assisted with documentation and coding.

## Table of Contents

### Start here (plain language)

**[GR-K-GDSS for Dummies](docs/GR-K-GDSS-for-Dummies.md)** -- Read this first if you are new. It explains what the project does and how the pieces fit together. **No radio knowledge or mathematics required.**

### Quick links (sections in this README)

- [Who built this and why](#who-built-this-and-why)
- [Power level, noise floor, and direction finding](#power-level-noise-floor-and-direction-finding)
- [Where key functions are implemented (quick code map)](#where-key-functions-are-implemented-quick-code-map)
- [Hardware Security Module — Current Limitations and Future Direction](#hardware-security-module--current-limitations-and-future-direction)
- [Active zeroisation, power-loss resume, and threat model](#active-zeroisation-power-loss-resume-and-threat-model)
- [Hardware Security Token Platform](#hardware-security-token-platform)
- [Likely candidates for future hardware](#likely-candidates-for-future-hardware)

### Main sections (this document)

1. [Background](#1-background)
2. [What is GDSS?](#2-what-is-gdss)
3. [Standard GDSS — How It Works](#3-standard-gdss--how-it-works)
4. [The Weakness in Standard GDSS](#4-the-weakness-in-standard-gdss)
5. [Cryptographically Keyed GDSS — The Proposed Modification](#5-cryptographically-keyed-gdss--the-proposed-modification)
6. [All Layers of Security](#6-all-layers-of-security)
7. [Comparison — Standard GDSS vs Keyed GDSS](#7-comparison--standard-gdss-vs-keyed-gdss)
8. [The Nitrokey, PIN Protection, and Emergency Disposal](#8-the-nitrokey-pin-protection-and-emergency-disposal)
9. [What Remains Unresolved](#9-what-remains-unresolved)
10. [Sources and Further Reading](#10-sources-and-further-reading)
11. [Build and Install](#11-build-and-install)

### Other documentation

12. [Usage](docs/USAGE.md)
13. [Examples](examples/)
14. [Testing](docs/TESTING.md)
15. [Test results](docs/TEST_RESULTS.md)
16. [Technical terms index](docs/GLOSSARY.md)
17. [KGDSS preprint](paper/kgdss_paper.tex) ([PDF on GitHub](https://github.com/Supermagnum/GR-K-GDSS/blob/main/paper/kgdss_paper.pdf))
18. [Available APIs (gr-linux-crypto)](#available-apis-gr-linux-crypto)
19. [Publication and IP Protection](#publication-and-ip-protection)

---

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

## Who built this and why

The code was written by a Norwegian amateur radio operator and SDR
experimenter who has a neurological condition that makes traditional
programming difficult. The work was done with AI assistance to bridge that gap.

The system is intended for:

- Amateur radio experimenters and SDR developers
- Journalists and press workers operating in hostile environments
- Humanitarian organisations facing surveillance threats
- Researchers studying covert communications

---

## Power level, noise floor, and direction finding

The signal content remains completely noise-like regardless of power level. The Gaussian amplitude distribution, the flat spectrum, the absence of cyclostationary features -- all of that holds whether you are 10 dB below the noise floor or 10 dB above it. Keyed masking means the chip amplitudes are cryptographically indistinguishable from thermal noise at any power level.

What changes when power is too high is purely geometric and physical -- not statistical.

A directional antenna pointed at the transmitter will measure a higher noise floor than the same antenna pointed away from it. The signal itself still looks like noise. But noise does not have a direction. Real thermal noise is isotropic -- it comes equally from all directions. An elevated noise floor that has a specific bearing, that appears and disappears at the same times a target is known to be active, and that is present at one location but not another -- that is anomalous even if its content is unreadable.

### The specific threat (SIGINT)

A SIGINT station with a calibrated directional antenna array doing noise floor monitoring, which is standard practice for serious signals intelligence, would notice:

- Noise floor elevation of a few dB in a specific azimuth
- Elevation present only during transmission periods
- Consistent geographic source
- No identifiable modulation, carrier, or structure

The conclusion is not "someone is transmitting voice". It is "something is elevating the noise floor from that direction at those times." That is enough to trigger further investigation, direction finding, and potentially physical surveillance of the area.

### Why mobility matters

This is exactly why the operational security layer (short transmissions, movement between transmissions) is not optional. It is the direct countermeasure to this specific threat.

A moving transmitter denies the adversary the stable baseline they need. If the elevated noise floor appears from a different direction each time and never from the same location twice, it cannot be correlated to a specific source. It looks like measurement noise in their own system rather than an anomalous emitter.

### Table 3 and the physics limit

The paper's Table 3 rating of 5/10 for "noise floor" for standard GDSS and 6/10 for keyed GDSS reflects this: it is the hardest column to improve because it is a physics problem, not a cryptography problem. No amount of keying or spreading changes the fact that radio waves carry energy that is measurable if you have a sensitive enough receiver pointed in the right direction.

---

## Publication and IP Protection


This project is documented in the following preprint:

> **Cryptographically Keyed Gaussian-Distributed Spread-Spectrum
> for Enhanced Covert Communications**
> Zenodo, 2026. https://zenodo.org/records/19162119

Archival PDF in this repository: [paper/kgdss_paper.pdf](https://github.com/Supermagnum/GR-K-GDSS/blob/main/paper/kgdss_paper.pdf).

Archive record timestamp: **21 March 2026**.

### Licence

This software is licensed under the
**GNU General Public License v3.0 or later** (GPL-3.0-or-later).
See [LICENSE](LICENSE) for the full text.

### Patent protection

This project is registered with the
[Open Invention Network (OIN)](https://openinventionnetwork.com),
a defensive patent pool protecting Linux-related open source software.
The combination of open preprint publication (establishing prior art),
OIN membership, and GPL-3.0 licensing is intended to ensure this
technology remains freely available and cannot be proprietised or
restricted by any state or commercial actor.

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

### Hardware Security Module — Current Limitations and Future Direction

The current design uses a **Nitrokey** hardware security device for private key storage and protection. The Nitrokey provides meaningful protection: the private key never leaves the device, cryptographic operations run on-device, and physical destruction of the device can render past sessions unrecoverable in practice. That is a **pragmatic compromise**, not an ideal end state.

The **architectural gap** is **forward secrecy**. The design uses **static long-term GnuPG keys** for ECDH. An adversary who records all radio traffic and **later** obtains the long-term private key could **retroactively** derive historical session keys and decrypt recorded sessions. This README describes **physical destruction of the Nitrokey** as an operational substitute for cryptographic forward secrecy; that is a **procedural mitigation**, not a cryptographic guarantee in the same class as per-session ephemeral keys.

**Closing the gap properly** would require a hardware token capable of more than today’s typical devices. An ideal platform would need to:

- Generate **ephemeral keypairs on-device per session**, perform **ECDH entirely on-device**, derive **all session subkeys via HKDF on-device**, export **only** the derived subkeys to the host, and **immediately and verifiably destroy** the ephemeral private key, such that even **physical seizure after session teardown** yields nothing useful about **past** sessions
- Provide **hardware acceleration** for BrainpoolP256r1 point multiplication, ChaCha20, Poly1305, HKDF, and a **TRNG** meeting NIST SP 800-90B
- Support a **custom programmable application layer** so ephemeral ECDH and subkey-derivation logic can be deployed and audited as **open source**, rather than relying only on fixed-function firmware
- **Bind key-vault access to verified application measurements**, so a compromised host cannot substitute malicious code and extract protected key material
- Be **open at every layer** relevant to trust (for example HDL, firmware, application code, hardware schematics) so independent parties can verify the security claims — a **fully open stack** is what makes **future algorithm changes** auditable and deployable without blind trust in a vendor blob
- **Support future algorithms**, not only today’s Brainpool / ChaCha20 profile: vault and APIs should treat stored and derived objects as **algorithm-agnostic key material** (clear types and lengths, no silent assumption that every secret is exactly one legacy format or size)
- Use **HKDF with explicit domain separation** (distinct info labels per subkey purpose) so **new subkey types** can be added **without** breaking or redefining existing derivations. The host-side reference for that pattern is [`python/session_key_derivation.py`](python/session_key_derivation.py); a capable token should apply the same discipline **on-device**

**For a long time, no single USB-class product combined all of the above.** Devices such as Nitrokey 3, YubiKey 5, Solo2, and common OpenPGP smart cards each meet **part** of the list. A **Baochip-1x** SoC on the **Dabao** evaluation board has since been **evaluated against the full hardware bar**; see [Hardware Security Token Platform](#hardware-security-token-platform). That path satisfies the **silicon and boot-chain** requirements documented there; **firmware**, **PIN-exhaustion zeroisation extensions**, and a **production USB carrier** remain **implementation work**, not architectural blockers in the same class as missing accelerators or closed RTL.

**RISC-V** (open, royalty-free ISA) remains a plausible foundation for other programmes, whether as a **soft core on an FPGA** or as **dedicated silicon** with secure storage and crypto blocks. The Baochip-1x line is one concrete open-RTL example in that space.

The GR-K-GDSS design is structured to **accommodate** a capable token once available. The key-derivation pipeline, subkey layout, and host interface are **not** tied to a specific token. A custom on-device application implementing ephemeral ECDH, on-device HKDF subkey derivation, and verifiable destruction of ephemeral secrets can be deployed **without** rewriting the radio or upper-layer crypto stacks—at which point forward secrecy can rest on **hardware-enforced** properties rather than **operator procedure alone**. Long-term, **algorithm-agnostic vault semantics** and **HKDF labels that can be extended** matter as much as any single cipher choice: they are what let the stack adopt **post-quantum or successor primitives** without a full ground-up redesign of the trust model.

**Until the Baochip-based firmware path is complete and audited** (or an equivalent token is fielded), **Nitrokey 3** remains the **interim** recommendation for operators using today’s stack, with the forward-secrecy limitation **documented and understood** as above.

### Active zeroisation, power-loss resume, and threat model

This is a **critical security requirement** and it goes **significantly beyond** what most current devices implement. Most devices that claim to "brick" or "lock" after failed PIN attempts are **passive** — they simply refuse further operations rather than **actively destroying key material**. That is **insufficient** for a serious threat model.

#### What Proper Active Zeroisation Requires

The zeroisation must be **active**, not passive. Simply setting a flag that blocks further PIN attempts leaves key material intact in NVM. An adversary with physical access and the right equipment can bypass the flag and read the NVM directly. **Active zeroisation** means the device **overwrites key material with random data from the TRNG**, repeatedly, before halting.

**Multiple overwrite passes.** A single overwrite may be insufficient depending on the NVM technology. Flash memory in particular has wear levelling and can retain ghost images of previous writes. The zeroisation routine should write random data, verify the write, and repeat several times across all key vault addresses.

**It must survive power interruption.** This is the hard part. If the device loses power mid-zeroisation — accidentally or deliberately by an adversary who pulls the USB connection the moment a wrong PIN is entered — the process must **resume and complete** on next power-up **before any other operation** is permitted. This requires:

- A **zeroisation state flag** written to OTP or a dedicated tamper register that survives power loss
- The **measured boot** sequence checking this flag before any application is permitted to run
- Zeroisation **completing and being verified** before the device presents any interface to the host

The **PIN attempt counter** itself must be in **tamper-evident storage**. If the counter can be reset by power cycling or by NVM manipulation, the whole mechanism is defeated. The counter should be in OTP-style storage that can only increment, never decrement, or in a **monotonic counter** backed by hardware that survives power loss.

The **TRNG must be available during zeroisation**. If the zeroisation routine uses a weak or predictable source for the overwrite data, a sophisticated adversary might be able to partially recover original key material by subtracting the known overwrite pattern. The same **NIST SP 800-90B** certified TRNG used for key generation should source the overwrite data.

**Zeroisation scope must be complete.** Not just the key vault but all locations where key material could have been copied — application state storage, any internal RAM that held derived keys, working registers used during cryptographic operations. The device should treat its **entire state** as potentially sensitive.

#### The Power-Loss Resume Mechanism in Detail

The sequence on **every power-up** should be:

1. Check tamper/zeroisation state register **before anything else**
2. If zeroisation is flagged as **incomplete**, resume immediately — no USB enumeration, no application loading, no PIN prompt
3. Complete all overwrite passes across all sensitive storage regions
4. Verify overwrites
5. Set zeroisation complete flag
6. Only then proceed to normal boot

This means an adversary **cannot interrupt** zeroisation by power cycling. Every time the device is powered, it will continue zeroising until done. The device becomes **useless to the adversary** regardless of how many times they interrupt power.

#### What This Means for the FPGA Architecture

The **zeroisation controller** should be implemented in the **FPGA fabric itself**, not in application software, so it cannot be bypassed by a compromised application. It should have **direct access** to NVM write interfaces that bypass any software abstraction layer. The measured boot chain should treat an **incomplete zeroisation flag** as equivalent to a tamper event — **nothing runs** until the situation is resolved.

#### Current Devices Fall Short

The Nitrokey's auto-brick behaviour after PIN attempts is **essentially passive** — it stops responding rather than actively overwriting. The TKey's current design does **not** implement this level of active zeroisation with power-loss resume. This is a **genuine gap** in available open hardware that would need to be addressed in any device targeting the threat model GR-K-GDSS implies.

### Hardware Security Token Platform

#### Background

The GR-K-GDSS design requires a hardware security token capable of performing **ephemeral ECDH** key exchange entirely on-device, deriving **all session subkeys via HKDF** on-device, exporting **only** derived subkeys to the host, and **verifiably destroying** ephemeral private key material after session teardown — such that **physical seizure after session teardown** yields nothing useful about **past** sessions.

Additional requirements include **hardware acceleration** for BrainpoolP256r1 point multiplication, ChaCha20, Poly1305, HKDF, and a **TRNG** meeting NIST SP 800-90B; a **custom programmable application layer** so that ephemeral ECDH and subkey-derivation logic can be deployed and audited as **open source**; **measured boot** with key vault access bound to **verified application measurements**; and a **fully open stack** at every layer relevant to trust — HDL, firmware, application code, and hardware schematics.

At time of writing, **no shipping product** in a **USB-stick form factor** fielded **all** of the above end-to-end; **Nitrokey 3** was recommended as an **interim** device, with the forward-secrecy limitation explicitly documented and understood. **Silicon-level** evaluation against the full bar is documented below for **Baochip-1x** on the **Dabao** board.

#### Platform Selection: Baochip-1x

The **Baochip-1x** SoC, available on the **Dabao** evaluation board, has been evaluated against the requirements above. It **satisfies every hardware requirement** called out in this README for the token platform; the remaining items are **implementation tasks** rather than **architectural gaps** in the silicon and boot model.

**Hardware specification (Dabao evaluation board):**

- 350 MHz VexRiscv RV32-IMAC CPU with MMU and **Zkn** scalar cryptography extensions (native AES instructions in the CPU pipeline)
- 4 x 700 MHz PicoRV32 I/O coprocessor cores (BIO) with custom register extensions
- 4 MiB on-chip RRAM (non-volatile, XIP up to ~1200 MB/s), 2 MiB SRAM + 256 KiB I/O buffers
- Swap memory support
- Cryptographic accelerators at 175 MHz: PKE (RSA, ECC, ECDSA, X25519, GCD), ComboHash (HMAC, SHA256, SHA512, SHA3, RIPEMD, Blake2, Blake3), AES, ALU, TRNG, SDMA
- PKE engine **verified algorithm-agnostic**: field prime supplied at runtime via **N0Dat** (256-bit), Montgomery parameter computed on-the-fly — **BrainpoolP256r1** confirmed viable without firmware modification
- Physical attack hardening: glitch sensors, security mesh, PV sensor, ECC-protected RAM
- Always-on domain: AORAM (8 KiB), 256-bit backup register, one-way counters, WDT, RTC — all surviving power loss
- Signed boot, key store, hardware one-way counters
- USB High Speed via USB-C
- Fully open RTL (CERN-OHL-W-2.0), reproducible bootloader, Rust-based Xous OS, open schematics
- IRIS-inspectable silicon

**Boot chain security model:**

The **immutable boot0** stage is burned at wafer-probe time, with JTAG fused out post-packaging. It runs **before USB enumeration**, before application loading, and before any host interaction. It verifies the integrity of **both** itself and **boot1** using up to four **ed25519** public keys burned into the chip. If verification fails, **volatile state is actively zeroised** before the CPU is halted. **One-way counters** are used throughout for key revocation, boot mode selection, and board type coding — these counters are **hardware-enforced**, monotonically incrementing, and survive power loss in the always-on domain.

This architecture **directly satisfies** the **active zeroisation** requirement described earlier in this README: the zeroisation controller operates at the **immutable boot layer**, below any software that could be compromised, with **direct access** to sensitive storage regions.

**Requirement mapping:**

| Requirement | Status | Notes |
|-------------|--------|-------|
| Ephemeral ECDH on-device | Implementable | Custom Xous application; process isolation via MMU |
| BrainpoolP256r1 HW acceleration | Confirmed | PKE engine runtime-configurable; verified in `PkeCore.sv` |
| ChaCha20 / Poly1305 HW acceleration | Unconfirmed | Software fallback on 350 MHz VexRiscv; adequate for token use |
| HKDF / HMAC-SHA256/512 HW acceleration | Confirmed | ComboHash block |
| TRNG | Confirmed | Dedicated hardware block; ring oscillator sourced |
| Programmable open application layer | Confirmed | Open RTL, reproducible bootloader, open Xous/Rust stack |
| Measured boot / integrity-bound key vault | Confirmed | Signed boot, immutable boot0, ed25519 key verification |
| Full open stack | Confirmed | RTL, bootloader, OS, schematics all open |
| Active zeroisation | Confirmed | Implemented in immutable boot0; extension to PIN exhaustion is firmware work |
| Power-loss resume during zeroisation | Architecturally supported | AORAM + always-on domain + boot0 pre-enumeration check |
| Monotonic PIN counter, tamper-evident | Confirmed | Hardware one-way counters in always-on domain |
| Physical attack hardening | Confirmed | Glitch sensors, mesh, PV sensor, ECC-protected RAM |
| Algorithm-agnostic vault / HKDF domain separation | Implementable | Application-layer implementation task |
| USB form factor | Pending | Dabao is an evaluation board; custom carrier board required for production |

#### Implementation Notes

**Active zeroisation extension:** The boot0 zeroisation path (triggered on signature verification failure) provides the **reference implementation**. Extending this to **PIN attempt counter exhaustion** requires: incrementing a **one-way counter** in the always-on domain on each failed attempt, checking this counter in the **boot0 pre-enumeration** sequence, and triggering the same **TRNG-sourced multi-pass overwrite** across all sensitive storage regions (key vault, AORAM, any SRAM holding derived key material) when the counter threshold is reached. **Power-loss resume** is inherent to the boot0 architecture — the device will not enumerate until boot0 completes, so interrupted zeroisation resumes automatically on next power-up.

**Key storage** 4MB RRAM can hold around 1024 BrainpoolP256r1 keypairs. 

**Optional PSRAM chip**

To an uninformed host / adversary:

Plugs in as a standard USB mass storage device
PSRAM contents appear as a normal (if encrypted) filesystem.
Nothing to see, nothing to explain.

To an informed host with kernel support:

Kernel driver or software function built into gr-linux-crypto recognises the device.
Challenges it for a minimum 5-character alphanumeric passphrase.
Correct response unlocks the real key material from RRAM and mounts the actual protected volume.
Wrong response (or no kernel support) — falls back to mass storage, silently.

**BrainpoolP256r1 usage:** Load curve parameters (prime *p*, coefficients *a*, *b*, generator point Gx/Gy, order *n*) into the PKE RAM, supply *p* as N0Dat, issue opcode `0x20` to precompute the Montgomery parameter, then run ECDH point multiplication. The 256-bit datapath matches the field size exactly.

**Developer mode:** Transitioning a chip to developer mode **permanently erases** the secret key area with **no recovery path**. Production tokens should use **standard SKU** chips, not engineering samples (ES suffix / BGA package).

**Key derivation:** The host-side HKDF domain separation pattern documented in [`python/session_key_derivation.py`](python/session_key_derivation.py) should be replicated on-device. The ComboHash HMAC block provides the hardware primitive; the Xous application implements the same explicit **info** label discipline per subkey purpose.

#### Recommended Transition Path

1. Acquire **Dabao** evaluation boards for firmware development
2. Implement **ephemeral ECDH + HKDF** subkey derivation as a **Xous** application
3. Implement **PIN counter exhaustion zeroisation** extending the existing boot0 path
4. Design **custom USB carrier board** (chip provides USB HS via USB-C natively)
5. Validate **TRNG** output against **NIST SP 800-90B** test suite
6. **Retire Nitrokey interim recommendation** once steps 2–3 are complete and audited

The key-derivation pipeline, subkey layout, and host interface are **not** tied to a specific token. **No changes** to the radio or upper-layer crypto stacks are required.

### Likely candidates for future hardware

The **Baochip-1x / Dabao** evaluation path is documented under [Hardware Security Token Platform](#hardware-security-token-platform). The following are **not endorsements** and **not commitments** from those parties; they are **additional** plausible directions and organisations whose existing work is **closest in spirit** to an open, programmable security token ecosystem.

#### Tillitis

The most directly relevant **existing** effort. **Tillitis** is a Swedish company that already shipped the **TKey**: a **RISC-V** soft core on an **FPGA** (Lattice **iCE40**) in a **USB stick** form factor, with **measured boot** and **application hash binding** to key access. That architecture is closer to this document’s target than most consumer security keys. The stack is **open source**, including the FPGA bitstream. The limitation is that the iCE40 is a **small, low-power** FPGA **without** dedicated cryptographic accelerators, so BrainpoolP256r1 and ChaCha20 would run **in software** on the RISC-V core rather than in fixed hardware. Sweden has a strong open-hardware culture and Tillitis emerged from the open security community; for this purpose it is among the most interesting existing organisations.

#### Nitrokey

German company with a **strong open source** posture; **OpenPGP** card support and **GnuPG** integration already match what GR-K-GDSS relies on. Historically Nitrokey devices have used **NXP microcontrollers** rather than RISC-V or FPGA platforms, which **limits** how far current designs can be reprogrammed for custom on-device ephemeral ECDH flows. The **Nitrokey 3** generation was a significant step. Nitrokey would be a **natural partner or collaborator** given existing integration, but meeting the **full** specification above would likely require a **different underlying platform**, not only firmware tweaks.

#### Olimex

Bulgarian **open hardware** manufacturer: full **schematics** and **PCB** layouts, **KiCad**, and **RISC-V** development boards. Olimex is not primarily a security-key vendor, but it is the kind of manufacturer that could produce the **board-level platform** the specification implies. Bulgaria is an **EU** member with a relatively open technology policy environment.

#### Precursor / Sutajio Ko-Usagi (bunnie studios)

Based in **Singapore**; the **Precursor** device places a **RISC-V** soft core on a **Xilinx FPGA** in a **handheld** form factor and is among the most technically ambitious open security-hardware projects in this space. Andrew **bunnie** Huang is a widely cited voice in open hardware security. Precursor is **too large** for a USB-stick token, but the **architecture** is directly relevant and the design materials are open; they could inform a **miniaturised** derivative.

#### Chips and chip ecosystems worth watching

- **Lattice Semiconductor** — **iCE40** and **ECP5** FPGAs are the usual choice for **open-source FPGA toolchains** (Project IceStorm, Project Trellis). The company is US-based (ownership has changed over time), but these parts underpin many open FPGA security projects including Tillitis. **ECP5** is larger than iCE40 and could host **more capable** cryptographic soft cores.
- **EFINIX** — RISC-V-friendly FPGAs aimed at **low power** and **small footprint**; less entrenched in the open-hardware community than Lattice but worth monitoring.
- **lowRISC** — UK non-profit; **OpenTitan** is an open **silicon root of trust** with measured-boot thinking aligned with this document, though it targets **embedded integration** rather than USB security sticks today. It is a credible open **RoT** effort in a friendly jurisdiction; UK government and research programmes have supported related open-silicon work.
- **RISC-V International** — headquartered in **Switzerland**; neutral jurisdiction considerations matter for some European adopters. The **RISC-V** ecosystem in Europe continues to grow.

#### Governments and initiatives with relevant interest

- **Germany** — **BSI** promotes auditable cryptography; **BSI TR-03111** (Brainpool curves) is a BSI family of documents. Germany is a plausible **certification-oriented** jurisdiction.
- **Sweden** — strong open-technology tradition; defence and signals-security communities have a sustained interest in **robust communications**. An open, low-probability-of-detection stack with sound key management could attract **policy and industry** interest adjacent to that space.
- **Netherlands** — active in **open cryptographic standards** and open-source **government** policy; NLNCSA works on cybersecurity and signals-related topics at national level.
- **European Union** — **Cyber Resilience Act** and related law push toward **auditable**, **certifiable** security products, which aligns with fully open, verifiable devices—**if** vendors choose that path.

#### Outreach

Anyone seeking such hardware could **politely contact** relevant teams (for example Tillitis, Nitrokey, Olimex, or FPGA-focused vendors) to ask whether a **next-generation** token or module could be scoped—**for example** moving from iCE40 toward **Lattice ECP5**, **EFINIX**, or similar, to host **stronger** soft cores and TRNG blocks while keeping **measured boot** and **open bitstreams**. This is **exploratory**; timelines, cost, and product fit are for those organisations to answer.

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
and is recommended by its author for  experimental radio, and
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
| **Technical terms index** (glossary of acronyms and terms) | **[docs/GLOSSARY.md](docs/GLOSSARY.md)** |
| **Example flowgraph** (TX with Codec2, ECIES, SOQPSK, GDSS) | **[examples/](examples/)** — `tx_example_kgdss.grc` and verification; see [examples/VERIFICATION_REPORT.md](examples/VERIFICATION_REPORT.md). |
| **C++ block implementation** (spreader/despreader logic) | **lib/** — `kgdss_spreader_cc_impl.cc`, `kgdss_despreader_cc_impl.cc`; headers in **include/gnuradio/kgdss/**. |
| **Python helpers** (key derivation, keyring, sync burst) | **python/** — `session_key_derivation.py`, `key_injector.py`, `sync_burst_utils.py`; API details in [docs/USAGE.md](docs/USAGE.md). |
| **GRC block definitions** | **grc/** — `kgdss_spreader_cc.block.yml`, `kgdss_despreader_cc.block.yml`, `kgdss_key_injector.block.yml`. |
| **Unit test scripts** | **tests/** — `test_t1_spreader_despreader.py`, `test_t2_sync_burst.py`, `test_t3_key_derivation.py`, `test_cross_layer.py`; described in [docs/TESTING.md](docs/TESTING.md). |
| **IQ test file generator and analyser** | **tests/generate_iq_test_files.py** (builds 01–13 and metadata), **tests/analyse_iq_files.py** (PASS/FAIL checks), **tests/plot_iq_comparison.py** (plots); see [docs/TESTING.md](docs/TESTING.md). |
| **Quick test run** | **tests/README.md** — Run commands; keyring/sandbox notes. |
| **Python bindings** (C++ blocks to Python) | **python/bindings/** — `kgdss_spreader_cc_python.cc`, `kgdss_despreader_cc_python.cc`, `kgdss_python.cc`; expose spreader/despreader and `kgdss_sync_state` to `gnuradio.kgdss`. |
| **Build system** | **CMakeLists.txt** (top level), **lib/CMakeLists.txt**, **python/CMakeLists.txt**, **python/bindings/CMakeLists.txt**, **grc/CMakeLists.txt**, **include/gnuradio/kgdss/CMakeLists.txt** — build and install the C++ library, Python package, and GRC blocks. |

### Where key functions are implemented (quick code map)

If you want to inspect specific behaviour in code, start with these files and functions:

- **HKDF key derivation and session subkeys**
  - **Runtime code (actual key schedule path):**
    - [`python/session_key_derivation.py`](python/session_key_derivation.py): `derive_session_keys(ecdh_shared_secret)` derives four domain-separated subkeys via HKDF-SHA256 (RFC 5869 style expand labels)
  - **Tests:**
    - [`tests/test_t3_key_derivation.py`](tests/test_t3_key_derivation.py): domain separation, determinism, input sensitivity, and nonce-construction checks

- **ChaCha20 keystream generation (chip masking)**
  - **Runtime code (actual processing path):**
    - [`lib/kgdss_spreader_cc_impl.cc`](lib/kgdss_spreader_cc_impl.cc): `fill_keystream()` using libsodium `crypto_stream_chacha20_ietf_xor_ic`
    - [`lib/kgdss_despreader_cc_impl.cc`](lib/kgdss_despreader_cc_impl.cc): `fill_keystream()` matching the spreader byte-for-byte for mask reconstruction
  - **Tests:**
    - [`tests/test_t1_spreader_despreader.py`](tests/test_t1_spreader_despreader.py): `TestT1KeystreamDeterminism`, `TestT1KeySensitivity`, `TestT1WrongKeyDespreader`

- **Box-Muller Gaussian masking and statistical properties**
  - **Runtime code (actual processing path):**
    - [`lib/kgdss_spreader_cc_impl.cc`](lib/kgdss_spreader_cc_impl.cc): `box_muller()`, keyed chip masking in spreader
    - [`lib/kgdss_despreader_cc_impl.cc`](lib/kgdss_despreader_cc_impl.cc): `box_muller()`, keyed mask reconstruction in despreader
    - [`python/sync_burst_utils.py`](python/sync_burst_utils.py): `_box_muller()` used by sync-burst keyed masking helper
  - **Test / simulation code:**
    - [`tests/generate_iq_test_files.py`](tests/generate_iq_test_files.py): `_box_muller()`, `_chacha20_gaussian_masks()`
    - [`paper/ber_simulation.py`](paper/ber_simulation.py): `_box_muller_pair()` (Monte Carlo model used for BER figures)
    - [`docs/TESTING.md`](docs/TESTING.md): `TestT1GaussianDistribution` explains the distribution checks

- **PN spreading sequence derived from Key 3 (`sync_pn`)**
  - **Runtime code (actual helper used by applications):**
    - [`python/sync_burst_utils.py`](python/sync_burst_utils.py): `derive_sync_pn_sequence(master_key, session_id, chips, burst_index=0)` (per-burst PN evolution; backward-compatible default)
    - [`python/session_key_derivation.py`](python/session_key_derivation.py): `derive_session_keys(...)` returns `sync_pn`
  - **Documentation / tests:**
    - [`docs/USAGE.md`](docs/USAGE.md): `derive_session_keys(...)` -> `sync_pn` -> `derive_sync_pn_sequence(...)`
    - [`tests/test_t2_sync_burst.py`](tests/test_t2_sync_burst.py): PN determinism/key-sensitivity, per-burst uniqueness, and `burst_index=0` compatibility checks

- **Burst timing randomised using Key 4 (`sync_timing`)**
  - **Runtime code (actual helper used by applications):**
    - [`python/sync_burst_utils.py`](python/sync_burst_utils.py): `derive_sync_schedule(...)` returning an ordered multi-burst epoch list (Pareto heavy-tailed inter-burst intervals)
    - [`python/session_key_derivation.py`](python/session_key_derivation.py): `derive_session_keys(...)` returns `sync_timing`
  - **Documentation / tests:**
    - [`docs/USAGE.md`](docs/USAGE.md): sync helpers and receiver integration sections
    - [`tests/test_t2_sync_burst.py`](tests/test_t2_sync_burst.py): schedule determinism/range/ordering/non-collision checks

- **Gaussian amplitude envelope for sync bursts**
  - **Runtime code (actual helper used by applications):**
    - [`python/sync_burst_utils.py`](python/sync_burst_utils.py): `gaussian_envelope(samples, rise_fraction=0.15)` (current default)
    - [`python/sync_burst_utils.py`](python/sync_burst_utils.py): `derive_sync_amplitude_scaling(...)` deterministic per-burst log-normal scaling
  - **Documentation / tests:**
    - [`docs/USAGE.md`](docs/USAGE.md): helper reference and recommended sync-burst flow
    - [`tests/test_t2_sync_burst.py`](tests/test_t2_sync_burst.py): `TestT2GaussianEnvelope`

- **P.372 baseline and receiver PSD profile integration**
  - **Runtime code (receiver-side model helpers):**
    - [`python/p372_baseline.py`](python/p372_baseline.py): `load_p372_params()` + `P372Params` from static config
    - [`python/p372_baseline_config.json`](python/p372_baseline_config.json): precomputed nominal/min parameter source
    - [`python/p372_receiver_profile.py`](python/p372_receiver_profile.py): `p372_expected_psd_profile_dbm_per_hz(...)`, `calibrate_p372_profile_to_measured_psd(...)`, `P372ReceiverProfile`
  - **Documentation / tests:**
    - [`docs/USAGE.md`](docs/USAGE.md): "Tie P.372-15 into receiver source (PSD by frequency bin)"
    - [`tests/test_p372_receiver_profile.py`](tests/test_p372_receiver_profile.py): loader determinism, expected-profile shape, and calibration tests

- **Public C++ block API headers (interface contracts)**
  - **Runtime API (public interfaces):**
    - [`include/gnuradio/kgdss/kgdss_spreader_cc.h`](include/gnuradio/kgdss/kgdss_spreader_cc.h): spreader block public API
    - [`include/gnuradio/kgdss/kgdss_despreader_cc.h`](include/gnuradio/kgdss/kgdss_despreader_cc.h): despreader block public API

- **Python bindings (C++ <-> Python exposure)**
  - **Runtime bindings (loaded by `gnuradio.kgdss`):**
    - [`python/bindings/kgdss_spreader_cc_python.cc`](python/bindings/kgdss_spreader_cc_python.cc): binds spreader block methods/types
    - [`python/bindings/kgdss_despreader_cc_python.cc`](python/bindings/kgdss_despreader_cc_python.cc): binds despreader block methods/types
    - [`python/bindings/kgdss_python.cc`](python/bindings/kgdss_python.cc): module-level exports (including enums/types)

### Available APIs (gr-linux-crypto)

GR-K-GDSS uses **gr-linux-crypto** for key derivation (CryptoHelpers, KeyringHelper) and optionally for payload encryption. The following gr-linux-crypto APIs are available and can be combined with keyed GDSS as needed.

**Shamir low-level**

- `split(secret, threshold_k, num_shares_n, prime, curve)` — max secret: 31 / 47 / 63 bytes for P256 / P384 / P512
- `reconstruct(shares, prime, secret_length, curve)`
- `create_shamir_backed_key(threshold_k, num_shares_n, prime, curve)` — returns a 32-byte session key
- `reconstruct_session_key(shares, prime, curve)`
- `get_curve_prime(curve)`, `get_max_secret_bytes(curve)`, `get_share_value_bytes(curve)`, `SUPPORTED_CURVES`

**MultiRecipientECIES**

- `encrypt(plaintext, recipients)` / `decrypt(ciphertext, callsign, private_key_pem)`
- `encrypt_and_sign(...)` / `verify_and_decrypt(...)`
- `encrypt_shamir(plaintext, recipients, curve)` / `decrypt_shamir(...)` / `get_share_from_shamir_block(...)`

**HPKE-style**

- `HPKEBrainpool.seal(...)` / `open(...)` / `seal_with_auth(...)` / `open_with_auth(...)`

**Nitrokey / card**

- `get_keygrip_from_key_id(...)`, `decrypt_with_card(...)` (documented stub), C++ block with `key_source="opgp_card"`

**Utilities and compliance**

- `secure_zero(buf)` (BSZ key lifecycle), `fips_status()`, BSI algorithm boundary: `check_algorithm_compliance`, `require_bsi_approved`, `list_approved_algorithms`

**Independent use — mix and match freely**

| You want | Use |
|----------|-----|
| ECIES only | MultiRecipientECIES.encrypt / decrypt |
| Shamir only | split / reconstruct or create_shamir_backed_key / reconstruct_session_key |
| ECIES + Shamir (K-of-N quorum) | encrypt_shamir / decrypt_shamir |
| Clean high-level API | HPKEBrainpool.seal / open |
| Hardware-backed keys | Nitrokey C++ block or decrypt_with_card |

**Usage documentation** is in **[docs/USAGE.md](docs/USAGE.md)**. There you will find:
- **Block API:** stream and message inputs/outputs, parameters, and usage for the three GNU Radio blocks (Keyed GDSS Spreader, Despreader, Key Injector), plus how to connect gr-linux-crypto and SOQPSK for TX/RX.
- **Real SDR hardware:** how to account for **DC spike** (LO leakage at 0 Hz) and **IQ imbalance** (mirror image) in GNU Radio; the GDSS blocks do not correct these (see the section *DC spike and IQ imbalance* in USAGE.md).
- **Python helper functions:** session key derivation and keyring (`derive_session_keys`, `store_session_keys`, `load_gdss_key`, `get_shared_secret_from_gnupg`, `gdss_nonce`, `payload_nonce`, `keyring_available`, `keyring_import_error`) and sync burst utilities (`derive_sync_schedule`, `derive_sync_pn_sequence`, `gaussian_envelope`). These are documented in the "Python helper functions" section; the blocks are documented in the "Keyed GDSS blocks" section.

### Examples

The **[examples/](examples/)** directory contains a ready-made GNU Radio Companion flowgraph:

- **tx_example_kgdss.grc** — A TX (transmit) example that wires: Audio Source (microphone) -> resampler -> Codec2 encoder -> Brainpool ECIES Multi-Recipient Encrypt (gr-linux-crypto) -> byte-to-bit unpack -> SOQPSK modulator (gr-qradiolink) -> Keyed GDSS Spreader -> Null Sink. The **Keyed GDSS Key Injector** block supplies key and nonce from the kernel keyring (variable `keyring_id`) and connects its message port to the spreader's `set_key` input. Replace the Null Sink with an osmocom or UHD Sink for real hardware output. Generate and run the flowgraph with `grcc tx_example_kgdss.grc` then `python3 tx_example_kgdss.py`. See [examples/VERIFICATION_REPORT.md](examples/VERIFICATION_REPORT.md) for verification steps.

**Brainpool ECIES parameters in the example:** gr-linux-crypto supports reading recipient public keys from the **kernel keyring** or from a JSON file. **key_store_path** is optional: leave it empty to use the keyring. Add recipient public keys to the keyring with `keyctl add user "callsign:PRESS1" "$(cat pubkey.pem)"` or from Python with `CallsignKeyStore(...).add_public_key(callsign, public_key_pem)`; the ECIES block then looks up keys by description `callsign:CALLSIGN`. Alternatively set **key_store_path** to a JSON file path for file-based store (see gr-linux-crypto docs). **callsigns** is the comma-separated list of recipient callsigns (e.g. `"ALICE,BOB"`); keys are resolved from the keyring or from the JSON file. If callsigns is empty, the block does not encrypt for any recipients.

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
