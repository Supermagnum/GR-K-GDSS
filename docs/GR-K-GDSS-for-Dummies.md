# GR-K-GDSS for Dummies

A plain-language guide to what this project does, why it exists, and how the pieces fit together. **No prior radio knowledge or mathematics is required** to follow this page.

*(The phrase "for Dummies" is used here in the everyday sense of "in simple terms." It is not affiliated with any published book series.)*

---

## First things first: read this

This software is **experimental**. The ideas are written up in a technical preprint, but they have **not** been checked by a professional cryptographer or a signals-intelligence expert. Treat every claim as **interesting, not proven**.

Documentation and code were written with **AI assistance**. Use your own judgement. Do not rely on this for life-safety or in places where getting caught could cause harm, without independent expert review.

---

## What problem is this trying to solve?

Sometimes people need to **send radio messages** in a way that is hard to **notice** or **analyse**. Classic radio often has a clear "signature": a tone, a pattern, or a spike on a screen that says "someone is transmitting here."

**Gaussian-Distributed Spread-Spectrum (GDSS)** is a published approach where the transmitted energy is made to **look like ordinary radio noise** to many standard detectors. The project **GR-K-GDSS** builds on that idea and adds **cryptographic keying**: the random-looking "mask" that shapes the signal is derived from **keys** the users share, not only from a built-in noise source.

So in one sentence: **GR-K-GDSS is a design (and this repository is code) for radio that tries to stay statistically noise-like on the air, while the fine details of that noise are controlled by secret keys.**

---

## The big picture: what happens to your message?

You can imagine a **chain** from microphone or data to antenna, and back on the receive side:

1. **Your content** (for example voice processed by a vocoder, or encrypted data) becomes a **digital stream** suitable for the radio chain.
2. **Encryption** (via related projects such as **gr-linux-crypto**) can protect the **payload** so that even if someone captured bits, they would still face cryptographic protection.
3. **Modulation** turns that stream into a radio waveform. In this stack, **SOQPSK** (from **gr-qradiolink**) is the kind of modulation used in the reference design.
4. **Spreading and masking (GR-K-GDSS)** take that waveform and **spread** it across a wider slice of spectrum, applying **Gaussian masking** so that the transmitted chips resemble **thermal noise** in many statistical tests.
5. The **antenna** radiates. On the other side, a receiver runs the steps in reverse: **despread**, **demodulate**, **decrypt**, play out audio or data.

You do **not** need to know the names of those blocks to understand the idea: **encrypt the payload, make the radio layer look like noise, share keys so only your partner can undo the masking.**

---

## What does "keyed" actually mean here?

In **standard GDSS**, masking uses randomness that is **statistically** like noise. In **keyed GDSS**, the same *kind* of output is aimed for, but the random-looking chip values are driven by **cryptographic keystream** (here built from modern primitives such as **ChaCha20** and key derivation via **HKDF** from a shared secret). That means:

- Without the **session key**, an eavesdropper should not be able to **predict** the masking.
- **Synchronisation bursts** (needed to find each other on the air) can be **per-session** and **keyed**, so they do not repeat the same obvious pattern every time the radio is used.

So "keyed" is about **unpredictability under cryptography**, not about "more volume."

---

## What this project **is**

- A **GNU Radio** out-of-tree module (**gr-k-gdss**) with blocks such as a **keyed spreader**, **keyed despreader**, and helpers for **keys** and **sync**.
- **Python helpers** for deriving subkeys, building nonces, and handling sync-burst behaviour in line with the design.
- **Tests and simulations** that check statistical behaviour and illustrate performance in **simplified** channel models (those are **simulations**, not a guarantee of real-world performance).

---

## What this project **is not**

- **Not** a finished product you can deploy without understanding the stack.
- **Not** a guarantee of invisibility. **Power** still matters: a directional antenna can still see **energy** coming from a direction even when the **content** looks like noise. Short transmissions and **movement** are part of the operational story; see the main [README](../README.md) section on power level, noise floor, and direction finding.
- **Not** legal advice. Radio regulations vary by country; **you** are responsible for compliance.

---

## How the repositories fit together (simple view)

| Piece | Role in plain words |
|-------|---------------------|
| **GR-K-GDSS** (this repo) | Spreading, masking, despreading, sync helpers tied to the GDSS design. |
| **gr-linux-crypto** | Cryptographic building blocks: key agreement, payload encryption, key storage hooks. |
| **gr-qradiolink** | SOQPSK modem pieces used in the reference transmit/receive path. |
| **GNU Radio** | The framework that connects blocks into a flowgraph (graph of signal processing). |

You can go deeper when you are ready: [USAGE.md](USAGE.md) for block-level detail, [TESTING.md](TESTING.md) for how tests are run, [GLOSSARY.md](GLOSSARY.md) for terms, and the [preprint PDF](../paper/kgdss_paper.pdf) for the full technical narrative.

---

## Who is this for?

The main [README](../README.md) describes the author's background and intended audiences (experimenters, journalists in difficult environments, humanitarian contexts, researchers). This guide does not repeat that; it only points you there.

---

## Summary

- **GR-K-GDSS** adds **cryptographic keying** to **noise-like spread-spectrum** radio ideas.
- The **goal** is stronger covertness against many **statistical** detectors, not a free pass against **physics** (energy, direction, timing).
- The **code** is real; the **security claims** need **independent review** before high-stakes use.

When you want detail, switch from this page to the [main README](../README.md) and [USAGE.md](USAGE.md).
