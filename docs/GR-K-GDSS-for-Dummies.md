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

### What does "−20 dB below the noise floor" mean?

Engineers measure how strong a signal is **relative to the background hiss** in **decibels (dB)**. Decibels are a **ratio on a log scale**, not a volume knob with absolute watts written on it.

Rough guide for power in the same receiver bandwidth:

| Relative level | Rough meaning |
|----------------|---------------|
| **0 dB** | Signal power equals the noise power (same "loudness" as the hiss). |
| **−10 dB** | Signal has about **1/10** the power of the noise. |
| **−20 dB** | Signal has about **1/100** the power of the noise. |
| **+10 dB** | Signal has about **10×** the power of the noise (easy to see as a spike). |

So **"−20 dB below the noise floor"** means: in that band, your transmission carries only about **one percent** as much power as the natural (or man-made) background noise the receiver already sees. On a typical spectrum display it does **not** stick up as a bright peak; it is **buried in the fuzzy baseline**.

**Everyday analogy:** imagine the noise floor as the steady hush of a busy café. A strong narrowband radio station is like someone standing on a chair and shouting — everyone notices. A signal at **−20 dB** is more like a quiet conversation two tables away while the room noise is a hundred times louder: you might not realise anyone is talking unless you already know *where* to listen and *how* to filter the room out.

**Why spreading helps:** spreading **dilutes** the same total energy over a wide band, which **lowers** the power density a passive observer sees in any narrow slice of spectrum (that is the "below the noise floor" part). The legitimate receiver, knowing the keys and spreading parameters, **despreads** and gets **processing gain** back: many chips are combined so the buried energy adds up into a usable signal for *them*, while a casual scanner still mostly sees hiss. Exact numbers depend on spreading factor and bandwidth (for example, large \(N\) can give on the order of **20 dB** of processing gain); see the main [README](../README.md) and [Power level, noise floor, and direction finding](../README.md#power-level-noise-floor-and-direction-finding).

**Important limit:** "below the noise floor" is about **looking like background in a spectrum view**, not about vanishing from physics. Enough power, a directional antenna, or long averaging can still show that **something** raised the energy from a bearing — even when the waveform still looks noise-like.

That addresses the first hurdle: **detection**. If someone still isolates energy or captures data, they hit a second hurdle: the **payload is strongly encrypted**. Recovering plaintext without the **session keys** should remain impractical, **provided users follow sound key-handling practice** (no shared passwords in chat, no keys on sticky notes, and so on). Poor operational choices can undo strong cryptography; the maths cannot fix human mistakes.

**What if a transmission could mimic that ever-present noise closely enough that many standard detectors treat it as uninteresting background?** And **what if that mimicry were tied to strong, open source, reviewable cryptography**, so that only someone with the right keys could undo the masking and recover the payload?

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

You do not need the jargon to grasp the idea: **encrypt the payload, make the over-the-air waveform look like noise, and share keys so only your partners can reverse the masking.**

---

## What does "keyed" actually mean here?

In **standard GDSS**, masking is **statistically** noise-like. In **keyed GDSS**, a similar **appearance** is targeted, but the chip-level masking is produced from a **cryptographic keystream** (here based on primitives such as **ChaCha20** and **HKDF** from a shared secret). So:

- Without the **session key**, an eavesdropper should not be able to **predict** the masking.
- **Synchronisation bursts** are now designed as a **scheduled multi-burst cadence** instead of a single one-shot burst.
- Each burst can use its own **burst index**, so PN patterns evolve per burst and do not repeat as one fixed sequence.
- Burst spacing can be irregular (heavy-tailed), making timing less predictable for outsiders while remaining deterministic for legitimate receivers.

**Keyed** means **cryptographic unpredictability**, not "turn the volume up."

### What if there is no session key?

On a **live keyed flowgraph**, the spreader and despreader **wait** for a valid
key and nonce (`set_key`). They do **not** transmit or receive useful data with
empty or guessed keys. The **key injector** only sends `set_key` after ECDH
material (keyring or shared secret) is available. There is **no on-air message**
that says "key missing." Sync-burst timing helpers need the same session
subkeys on both sides; without them, bursts will not correlate.

More detail: [README — Behaviour when no cryptographic key is present](../README.md#behaviour-when-no-cryptographic-key-is-present) and [USAGE.md](USAGE.md#behaviour-when-no-cryptographic-key-is-present).

---

## Synchronisation bursts (what they do)

Radios that look like noise still need a way for the **receiver to line up in time** with the transmitter. If the two sides are even slightly out of step, despreading and decryption fail even when both have the correct keys.

A **synchronisation burst** (sync burst) is a **short, known-looking chip sequence** the transmitter inserts so the receiver can **find timing** (and often lock) before or during the payload. Think of it as a **shared secret knock**: only partners who know the keys recognise it; everyone else should mostly hear more hiss.

In this project a sync burst is typically:

1. A **PN** (pseudo-noise) chip pattern — looks random, but is **deterministic** from the session keys.
2. Softened with a **Gaussian envelope** (fade in / fade out) so the edges are not a hard click.
3. **Keyed Gaussian-masked** like the data path, so the burst does not stand out as an obvious “sync tone” or classic DSSS spike on a spectrum display.

**What the receiver does:** with the same keys it **unmasks** the burst, **correlates** against the expected PN, and looks for a **peak**. That peak says “here is the time alignment.” Without matching keys, that peak should not appear.

API and wiring detail: [USAGE.md — Sync burst timing and multi-burst schedule](USAGE.md#sync-burst-timing-and-multi-burst-schedule). Glossary: [sync burst](GLOSSARY.md#sync-burst), [PN sequence](GLOSSARY.md#pn-sequence).

### Scheduled multi-burst cadence

Many older designs fire **one** sync burst at the start of a session. GR-K-GDSS is designed around a **schedule of several bursts over time**.

Helpers such as `derive_sync_schedule(...)` build a shared list of times (milliseconds from session start), for example:

`[1200, 4800, 9100, …]`

That list is the **cadence**: *when* each sync blast is sent.

Why several irregular bursts instead of one metronome tick?

- **Recovery:** if one burst is lost to noise or interference, later bursts still give the receiver a chance to lock.
- **Less predictability for outsiders:** gaps are often **irregular** (heavy-tailed / Pareto draws from key material), not a fixed beep-beep-beep.
- **Same map on both sides:** transmitter and receiver derive the **same** schedule from the same timing subkey and session id, so both know when to transmit and when to listen. A **flywheel** on the receiver can keep tracking expected times even if some bursts are missed.

So: **multi-burst** means many sync opportunities; **scheduled cadence** means their shared, key-derived timeline.

### Burst index

**Burst index** is simply which burst in that schedule you mean: `0`, `1`, `2`, …

For burst *i*, both ends must use the same *i* when they:

| Piece | Why the index matters |
|-------|------------------------|
| PN sequence | Each burst gets its **own** spreading pattern (patterns do not repeat as one fixed sequence forever). |
| Sync-burst mask nonce | Each burst gets its **own** ChaCha keystream (`gdss_sync_burst_nonce(session_id, burst_index=i)`), so masks are not reused across bursts. |
| Optional amplitude scaling | Each burst can have its own key-derived loudness scale. |

Example: eight scheduled epochs use indices `0` through `7`. The burst at `9100 ms` might be index `2`; TX and RX both pass `burst_index=2` when building or correlating that one.

Default `burst_index=0` keeps simple single-burst behaviour for older call sites.

### One picture

```text
time --->
  |--burst 0--|     |--burst 1--|           |--burst 2--|     ...  (payload around / between)
       ^                 ^                       ^
  index=0           index=1                 index=2
  own PN + nonce    own PN + nonce          own PN + nonce
  times come from the shared schedule (TX and RX agree)
```

**In one line:** sync bursts **align time**; the **schedule** says **when**; the **burst index** says **which** burst so patterns and masks stay unique.

---

## What this project **is**

- A **GNU Radio** out-of-tree module (**gr-k-gdss**): **keyed spreader**, **keyed despreader**, and support for **keys** and **sync**.
- **Python helpers** for subkey derivation, nonces, and sync-burst behaviour aligned with the design.
- **Receiver-side helpers** to compare measured FFT/PSD bins against a **P.372-17 integration hook** (synthetic PSD prior, not ITU §3.1.x atmospheric physics), so cold-start priors can be aligned to local receiver measurements by frequency.
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
- **"−20 dB below the noise floor"** means the transmission has roughly **1/100** the power of the background hiss in that band — buried in the fuzzy baseline for casual spectrum displays, while a keyed receiver can still recover it by despreading (see the section above).
- **Sync bursts** help the receiver **line up in time**; a **scheduled multi-burst cadence** fires several of them on a shared irregular timeline; each uses a **burst index** so PN and mask keystreams do not repeat across bursts (see [Synchronisation bursts](#synchronisation-bursts-what-they-do)).
- The receiver can combine **live PSD measurements** with the **P.372-17 hook prior** (`P372_COMPLIANCE = "none"`) to tune noise-floor assumptions per frequency bin until live estimation supersedes it (see `docs/todo.md`).
- The aim is stronger resistance to many **statistical** detectors, not immunity to **physics** (energy, bearing, timing).
- The **code** is real and inspectable; **security claims** still need **independent expert review** before high-stakes use.

For detail, continue with the [main README](../README.md) and [USAGE.md](USAGE.md).
Recorded pytest and IQ analysis output: [TEST_RESULTS.md](TEST_RESULTS.md).
How to run tests: [TESTING.md](TESTING.md).
