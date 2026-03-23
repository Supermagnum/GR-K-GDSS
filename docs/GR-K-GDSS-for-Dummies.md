# GR-K-GDSS for Dummies

A plain-language guide to what this project does, why it exists, and how the pieces fit together. **No prior radio knowledge or mathematics is required** to follow this page.

*(The phrase "for Dummies" is used here in the everyday sense of "in simple terms." It is not affiliated with any published book series.)*

---

## First things first: read this

This software is **experimental**. The ideas are written up in a technical preprint, but they have **not** been checked by a professional cryptographer or a signals-intelligence expert. Treat every claim as **interesting, not proven**.

Documentation and code were written with **AI assistance**. Use your own judgement. Do not rely on this for life-safety or in places where getting caught could cause harm, without independent expert review.

---

## What problem is this trying to solve?

Radio noise has always been around us. Some of it comes from nature: lightning, the Sun, the wider galaxy. Some is man-made: computers, phone chargers, industrial equipment, and countless other devices. Receivers are used to a background that is messy, random-looking, and often ignored.

In everyday listening, that background is the **hiss** you hear when you tune an analogue radio **between stations**. Engineers often call that kind of broad, featureless hiss **white noise** (or noise that behaves similarly in the receiver).

**Spread spectrum** means taking a signal and **stretching or smearing** its energy across a **wide band** of frequencies (for example around a megahertz or more, depending on design), instead of concentrating it in a narrow peak. On a **spectrum analyser**, a wideband noise-like signal can look like a **raised, fuzzy band** across that span, while ordinary stations still show up as **narrow, distinct peaks**. The idea behind this codebase and method is to **shape the broadened transmission so it sits in that fuzzy noise floor** and is **hard to pick out** from everything else that already looks like noise.

That addresses the first hurdle: **detection**. If someone still isolates energy or captures data, they hit a second hurdle: the **payload is strongly encrypted**. Recovering plaintext without the **session keys** should remain impractical, **provided users follow sound key-handling practice** (no shared passwords in chat, no keys on sticky notes, and so on). Poor operational choices can undo strong cryptography; the maths cannot fix human mistakes.

**What if a transmission could mimic that ever-present noise closely enough that many standard detectors treat it as uninteresting background?** And **what if that mimicry were tied to strong, open, reviewable cryptography**, so that only someone with the right keys could undo the masking and recover the payload?

That combination is the motivation behind this work. In practice, people sometimes need to **send radio messages** that are hard to **notice** or **analyse** with ordinary tools. Conventional transmissions often have an obvious signature: a steady tone, a repeating pattern, or a spike on a spectrum display that says "someone is transmitting here."

**Gaussian-Distributed Spread-Spectrum (GDSS)** is a published approach in which transmitted energy is shaped so it **resembles ordinary radio noise** under many statistical tests. **GR-K-GDSS** extends that idea with **cryptographic keying**: the fine structure of the noise-like waveform is driven by **secret keys** shared between legitimate users, not only by a local random or thermal-noise source inside the transmitter.

In one sentence: **GR-K-GDSS is a design (this repository is reference code) for radio that aims to stay statistically noise-like on the air, while the details of that noise are controlled by shared secret keys and open cryptographic primitives.**

---

## The big picture: what happens to your message?

Think of a simple **chain** from microphone or data file to antenna, and the reverse chain on receive:

1. **Content** (for example voice through a vocoder, or data) becomes a **digital stream** for the radio chain.
2. **Payload encryption** (for example via **gr-linux-crypto**) can protect the bits so that intercepting the stream still leaves an adversary facing proper cryptography.
3. **Modulation** turns that stream into a radio waveform. In the reference stack, **SOQPSK** from **gr-qradiolink** is used.
4. **Spreading and masking (GR-K-GDSS)** widen the signal in frequency and apply **Gaussian masking** so that, in many tests, the transmitted chips look like **thermal noise**.
5. The **antenna** radiates. The receiver **despreads**, **demodulates**, and **decrypts** to recover audio or data.

You do not need the jargon to grasp the idea: **encrypt the payload, make the over-the-air waveform look like noise, and share keys so only your partner can reverse the masking.**

---

## What does "keyed" actually mean here?

In **standard GDSS**, masking is **statistically** noise-like. In **keyed GDSS**, a similar **appearance** is targeted, but the chip-level masking is produced from a **cryptographic keystream** (here based on primitives such as **ChaCha20** and **HKDF** from a shared secret). So:

- Without the **session key**, an eavesdropper should not be able to **predict** the masking.
- **Synchronisation bursts** can be **per-session** and **keyed**, so they do not repeat the same obvious pattern every time the radio is used.

**Keyed** means **cryptographic unpredictability**, not "turn the volume up."

---

## What this project **is**

- A **GNU Radio** out-of-tree module (**gr-k-gdss**): **keyed spreader**, **keyed despreader**, and support for **keys** and **sync**.
- **Python helpers** for subkey derivation, nonces, and sync-burst behaviour aligned with the design.
- **Tests and simulations** that check statistics and show behaviour in **simplified** channel models. Those are **software experiments**, not a warranty for every real channel.

---

## What this project **is not**

- **Not** a turnkey product: you still need to understand the stack and your threat model.
- **Not** invisibility against physics. **Power and direction** still matter: a sensitive receiver pointed the right way can still see **energy** even when the **waveform** looks like noise. Short transmissions and **movement** matter; see the main [README](../README.md) on power level, noise floor, and direction finding.
- **Not** legal advice. Radio rules differ by country and band; **you** are responsible for compliance.

---

## How the repositories fit together (simple view)

| Piece | Role in plain words |
|-------|---------------------|
| **GR-K-GDSS** (this repo) | Spreading, masking, despreading, sync helpers for the keyed GDSS design. |
| **gr-linux-crypto** | Cryptographic building blocks: key agreement, payload encryption, key storage hooks. |
| **gr-qradiolink** | SOQPSK modem pieces used in the reference transmit/receive path. |
| **GNU Radio** | The framework that wires blocks into a flowgraph (signal-processing graph). |

When you want more depth: [USAGE.md](USAGE.md) (blocks and helpers), [TESTING.md](TESTING.md) (how to run tests), [GLOSSARY.md](GLOSSARY.md) (terms), and the [preprint PDF](../paper/kgdss_paper.pdf) (full technical story).

---

## Who is this for?

The main [README](../README.md) describes the author's background and who the work is aimed at (experimenters, journalists in hostile environments, humanitarian use, researchers). This page does not repeat that; it only points you there.

---

## Summary

- **GR-K-GDSS** adds **cryptographic keying** to **noise-like spread-spectrum** radio ideas.
- The aim is stronger resistance to many **statistical** detectors, not immunity to **physics** (energy, bearing, timing).
- The **code** is real and inspectable; **security claims** still need **independent expert review** before high-stakes use.

For detail, continue with the [main README](../README.md) and [USAGE.md](USAGE.md).
