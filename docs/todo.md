# KGDSS: Multiple Sync Burst Design

**Implementation Proposal — Noise-Mimicking Burst Cadence**

---

## 1. Purpose

This document captures the proposed design changes to extend the KGDSS synchronisation subsystem from a single sync burst to a scheduled multi-burst cadence. The primary goals are to eliminate the single-point-of-failure in receiver timing recovery, bound the maximum data loss window on a missed burst, and maintain — and strengthen — the covertness properties already established by the Gaussian-enveloped, keyed-PN burst design.

All proposed changes derive their pseudo-random schedule from key material already produced by the HKDF key derivation stage, meaning no new cryptographic primitives or additional key exchange steps are required.

---

## 2. Background and Problem Statement

### 2.1 Current Architecture

The current session uses a single 2 ms synchronisation burst at session start. The burst is designed for covertness: its PN spreading sequence is derived from Key 3 (sync_pn), its timing offset within a known search window is derived from Key 4 (sync_timing), and its amplitude envelope is shaped with a Gaussian rise and fall to mimic natural impulse noise.

This design is cryptographically sound and statistically well-disguised. The receiver cannot lock without the session keys, and a passive observer cannot distinguish the burst from atmospheric noise by amplitude profile alone.

### 2.2 The Single-Burst Failure Mode

A single sync burst is a single point of failure. If the receiver misses the burst due to interference, deep fading, a scheduling conflict in the GNU Radio flow graph, or a transient hardware underrun, the consequences cascade as follows.

- Frame synchronisation is lost immediately. The receiver does not know where symbol boundaries lie.
- The LDPC decoder receives a misaligned bit stream. Belief propagation iterates on a scrambled combination of two adjacent codewords and fails to converge.
- All subsequent frames are unrecoverable until the receiver re-acquires timing from another source.
- With only one burst in the session, there is no other source. Re-acquisition requires either a protocol-level session restart or a blind correlation scan, both of which are operationally disruptive and potentially observable.

---

## 3. Proposed Design: Scheduled Multi-Burst Cadence

### 3.1 Core Principle

Rather than a single burst at session start, the transmitter emits a pseudo-random sequence of sync bursts throughout the session lifetime. Both transmitter and receiver derive the identical schedule deterministically from Key 4 (sync_timing), so no additional signalling is needed to convey burst timing. The receiver always knows when to look; an observer never does.

### 3.2 Schedule Derivation

The function `derive_sync_schedule` in `python/sync_burst_utils.py` is extended from returning a single timing offset to returning an ordered list of offsets. The derivation uses HKDF-Expand with Key 4 as the input key material, the session identifier as context, and a burst index counter as a domain separator suffix.

Each burst offset is drawn pseudo-randomly within a configurable window. Both the window duration and the number of bursts per window are parameters. The burst index counter increments monotonically, ensuring each offset in the schedule is independently derived and unpredictable without the key.

The `session_key_derivation` module requires no structural change. The `sync_timing` subkey it already returns is passed directly into the extended `derive_sync_schedule` call.

### 3.3 Per-Burst PN Sequence Evolution

In the current design, the same PN sequence derived once from Key 3 is used for every burst. With multiple bursts, reusing the identical sequence across all of them creates a weak correlation: an observer who accumulates enough radio captures and aligns them correctly could potentially detect the recurring pattern, even if individual bursts are buried in noise.

To eliminate this, the PN sequence is evolved per burst. The `derive_sync_pn_sequence` function is extended to accept a `burst_index` parameter. The derivation appends the burst index to the HKDF domain label, producing a unique PN seed per burst. Each burst therefore presents a different spreading sequence to the channel, eliminating any cross-burst correlation an observer could exploit.

The change is backward-compatible: `burst_index` defaults to zero, so the existing single-burst behaviour is preserved without modification to callers that do not pass the parameter.

### 3.4 Receiver Recovery Behaviour

The receiver maintains a flywheel — an internal timing estimate extrapolated from the last successfully decoded burst. Between bursts, the flywheel drifts at a rate determined by the local oscillator stability. When the next burst position arrives, the receiver opens a correlation window around the predicted arrival time and attempts to lock on the expected PN sequence for that burst index.

If the burst is detected, timing is corrected and the flywheel is reset. If the burst is missed, the flywheel continues. The maximum desynchronisation is bounded: in the worst case the receiver misses every burst in a run, but once it catches any subsequent burst it re-locks immediately. The LDPC decoder receives clean, correctly aligned frames again from that point onward.

This is a fundamentally different failure mode from the single-burst case. Loss is bounded to the frames between two adjacent burst positions rather than potentially the entire remaining session.

---

## 4. Noise Mimicry Requirements

The expanded burst schedule introduces more transmit events, which increases the statistical surface area available to a passive observer. Each design decision must therefore be evaluated not only for its synchronisation benefit but for its impact on RF signature. The following requirements govern the noise-mimicry properties of the multi-burst system.

### 4.1 Amplitude Envelope

Each burst retains the Gaussian amplitude envelope implemented in `gaussian_envelope` in `python/sync_burst_utils.py`. The rise and fall profile matches the statistical amplitude distribution of natural impulse noise events in HF and VHF radio environments. This property must not be compromised by the multi-burst extension: every burst in the schedule, regardless of its index, must pass through the same Gaussian shaping stage before transmission.

The `rise_fraction` parameter controls how much of the burst duration is consumed by the rise and fall regions. The current default of 0.1 is appropriate for mimicking short atmospheric impulses. This value should be verified against measured atmospheric noise samples from the intended operating band before finalising. If measured rise times differ significantly, `rise_fraction` must be adjusted to match — a synthetic burst with a markedly different rise profile than real noise is a detectable artefact.

### 4.2 Inter-Burst Interval Distribution

The inter-burst interval — the time between consecutive burst positions in the schedule — must not follow a regular pattern. A fixed cadence such as one burst every 30 seconds would be trivially detectable by an observer computing the power spectral density of event inter-arrival times over a long capture.

The schedule derivation must produce inter-burst intervals drawn from a distribution that matches observed natural noise event statistics for the target band. For HF atmospheric noise, inter-event intervals follow a heavy-tailed distribution, not a uniform one. The HKDF-derived pseudo-random offsets should be mapped through an appropriate quantile function — such as an inverse exponential or Pareto transform — to produce inter-burst intervals with the correct statistical shape.

Both transmitter and receiver apply the identical transform to the raw HKDF output, so the schedule remains deterministic and shared without any additional communication.

### 4.3 Burst Energy and Spectral Shape

Natural impulse noise events in HF bands typically occupy a broad instantaneous bandwidth and have energy that decays rapidly with frequency offset from the impulse centre. The PN spreading already distributes the burst energy across the spreading bandwidth, which is a positive property. However, the chip rate and spreading factor must be chosen so that the resulting spectral occupancy matches the bandwidth of typical atmospheric noise impulses in the target band.

If the chip rate is too narrow, the burst will appear as a narrowband tone against a wideband noise floor — an anomalous signature. If it is too wide, it may exceed the coherence bandwidth of the channel and degrade correlation performance. These parameters should be validated against representative noise captures from the target band before deployment.

### 4.4 Burst Duration

The 2 ms burst duration is already chosen to match common atmospheric noise spike durations. This duration should be retained across all bursts in the schedule. Varying burst duration between schedule positions would introduce a detectable feature and is not recommended.

### 4.5 Per-Burst Amplitude Jitter

Real atmospheric noise events vary in amplitude from burst to burst. A perfectly constant-amplitude burst schedule would stand out against measured noise floors where energy levels fluctuate. The Gaussian envelope already handles intra-burst amplitude shaping; a small pseudo-random inter-burst amplitude scaling factor should be applied on top of it.

This scaling factor is derived from Key 3 or Key 4 material using a separate HKDF-Expand output with a distinct domain label, and mapped to a plausible amplitude range. The target distribution is log-normal, with parameters matched to measured noise amplitude statistics for the target band. Both transmitter and receiver agree on the same scaling sequence, so the receiver can apply the correct expected amplitude when computing its matched filter gain.

### 4.6 Required Statistical Tests

Before deployment, the burst schedule must pass a set of statistical tests against a null hypothesis of natural noise.

- Inter-arrival time distribution: Kolmogorov-Smirnov test against the target noise model. The schedule should not be distinguishable from a noise process at a significance level appropriate to the intended detection adversary.
- Amplitude distribution across bursts: log-normal fit quality against measured noise amplitude histograms from the target band.
- Spectral flatness within each burst: the in-band power spectral density of the PN-spread burst should match the spectral shape of broadband impulse noise, not a flat or peaked tone.
- Cross-correlation across burst indices: verify that PN sequences derived for burst_index N and burst_index M have cross-correlation below the expected noise floor for all tested pairs.

---

## 5. Code Change Surface

### 5.1 Files Requiring Changes

`python/sync_burst_utils.py` — primary change file.

- Extend `derive_sync_schedule` to return an ordered list of timing offsets rather than a single scalar. Add the inter-burst interval quantile transform for noise-statistics matching. Add a configurable `n_bursts` parameter.
- Extend `derive_sync_pn_sequence` to accept a `burst_index` parameter, appending it to the HKDF domain label to produce a unique PN seed per burst. Default `burst_index=0` preserves backward compatibility.
- Add a per-burst amplitude scaling derivation function using HKDF-Expand with a distinct domain label, returning a log-normally distributed scaling factor sequence.

`tests/test_t2_sync_burst.py` — new test cases covering schedule length, no-collision between burst offsets, inter-burst interval distribution shape, per-burst PN uniqueness, backward compatibility of `burst_index=0`, and amplitude scaling factor determinism.

### 5.2 Files Requiring No Changes

`python/session_key_derivation.py` — no structural change required. The `sync_timing` subkey it already returns is passed into the extended `derive_sync_schedule` signature by the caller. The `derive_session_keys` function output is unchanged.

`lib/kgdss_spreader_cc_impl.cc` and `lib/kgdss_despreader_cc_impl.cc` — both operate on the chip stream and are agnostic to burst count and schedule. Burst injection and detection occur in the Python flow graph layer above them.

`include/gnuradio/kgdss/kgdss_spreader_cc.h` and `kgdss_despreader_cc.h` — public API surface is unchanged.

`python/bindings/` — no new methods are exposed to Python. The C++ block interface is unchanged.

---

## 6. Parameter Selection Guidance

### 6.1 Burst Count and Cadence

The number of bursts per session window and the window duration together determine the maximum desynchronisation interval. Choosing these values involves a three-way tradeoff between recovery latency, channel occupancy, and covertness.

A shorter cadence gives lower recovery latency and less flywheel drift but produces more transmit events that must individually pass statistical scrutiny. A longer cadence is easier to disguise statistically but allows more drift and a wider potential loss window if multiple consecutive bursts are missed.

A recommended starting point is a mean inter-burst interval of 20 to 60 seconds with a heavy-tailed jitter distribution. This should be validated against the expected oscillator drift rate of the receiver hardware and the observed inter-event statistics of atmospheric noise in the target band.

### 6.2 Flywheel Stability Bound

The receiver flywheel extrapolates timing between bursts using its local oscillator. The allowable inter-burst interval is bounded above by the oscillator drift rate multiplied by the maximum timing error the LDPC decoder and despreader can tolerate without a sync correction. This must be computed for the actual receiver hardware before the cadence schedule is finalised.

### 6.3 Correlation Search Window

At each scheduled burst position, the receiver opens a correlation search window around the predicted arrival time. The window must be wide enough to cover oscillator drift accumulated since the last burst, but narrow enough to avoid false lock on ambient noise. The window half-width should be set to approximately three standard deviations of the expected drift distribution for the hardware in use.

---

## 7. Test Plan Additions

The following test cases are added to `tests/test_t2_sync_burst.py`.

- **Schedule determinism** — same inputs produce an identical schedule on transmitter and receiver across platforms and Python versions.
- **Schedule length** — the returned offset list contains exactly the requested number of bursts.
- **No inter-burst collisions** — no two burst positions in the schedule overlap within one burst duration of each other.
- **Interval distribution shape** — KS test of inter-burst intervals against the target heavy-tailed noise inter-event model.
- **Per-burst PN uniqueness** — the PN sequence for burst_index N is distinct from burst_index M for all tested pairs.
- **Backward compatibility** — `burst_index=0` produces the same PN sequence as the current single-burst implementation.
- **Amplitude scaling determinism** — per-burst amplitude scaling factors are identical on transmitter and receiver for the same key material.
- **Amplitude distribution shape** — log-normal fit quality of the amplitude scaling sequence against the target noise amplitude model.

---

## 8. Open Questions

- What is the measured inter-event interval distribution of atmospheric noise in the target operating band? This determines the quantile transform applied to HKDF output for schedule generation and cannot be assumed from general literature alone.
- What is the oscillator drift rate of the target receiver hardware? This sets the hard upper bound on the inter-burst interval.
- Should the burst count per session be fixed or itself derived from key material? A key-derived burst count adds one more unpredictable parameter for an observer but complicates session lifecycle management.
- Should missed bursts trigger any protocol-level event, or should the flywheel operate silently? Silent operation is more covert; flagging missed bursts enables diagnostic monitoring.
- Does the Gaussian envelope `rise_fraction` default of 0.1 match measured atmospheric noise rise times in the target band? If not, what value should replace it?
