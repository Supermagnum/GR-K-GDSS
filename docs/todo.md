# KGDSS: Multiple Sync Burst Design

**Implementation Proposal — Noise-Mimicking Burst Cadence**

---

## 1. Purpose

This document captures the proposed design changes to extend the KGDSS synchronisation subsystem from a single sync burst to a scheduled multi-burst cadence. The primary goals are to eliminate the single-point-of-failure in receiver timing recovery, bound the maximum data loss window on a missed burst, and maintain — and strengthen — the covertness properties already established by the Gaussian-enveloped, keyed-PN burst design.

All proposed changes derive their pseudo-random schedule from key material already produced by the HKDF key derivation stage, meaning no new cryptographic primitives or additional key exchange steps are required.

The noise mimicry parameters are derived from ITU-R P.372-15, the internationally standardised model for radio noise, averaged across a representative matrix of geographic locations, times of day, seasons, and solar flux conditions. This ensures the system is universally valid rather than tuned to any specific deployment environment.

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

The raw HKDF output is mapped through a quantile transform derived from the P.372-15 baseline atmospheric noise model to produce inter-burst intervals with the correct heavy-tailed statistical shape. Both transmitter and receiver apply the identical transform, so the schedule remains deterministic and shared without any additional communication.

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

All noise mimicry parameters are derived from ITU-R P.372-15 rather than local measurements. P.372-15 provides a globally valid, empirically grounded model of atmospheric radio noise as a function of frequency, geographic location, season, and time of day, covering 10 kHz to 100 MHz. Parameters are computed as averages across a representative matrix of conditions as described in Section 4.7, ensuring the system is valid in all deployment environments rather than optimised for any single location.

### 4.1 Amplitude Envelope

Each burst retains the Gaussian amplitude envelope implemented in `gaussian_envelope` in `python/sync_burst_utils.py`. The rise and fall profile matches the statistical amplitude distribution of natural impulse noise events in HF environments. This property must not be compromised by the multi-burst extension: every burst in the schedule, regardless of its index, must pass through the same Gaussian shaping stage before transmission.

The `rise_fraction` parameter controls how much of the burst duration is consumed by the rise and fall regions. The value is derived from published sferic waveform characterisation literature rather than local measurement. Atmospheric sferics at HF frequencies typically exhibit rise times of 0.1 to 0.3 ms and decay times of 0.5 to 1.5 ms. For a 2 ms burst duration, a `rise_fraction` of 0.15 places the rise region within the lower end of the observed sferic rise time distribution and is adopted as the design value, replacing the previous default of 0.1.

### 4.2 Inter-Burst Interval Distribution

The inter-burst interval must not follow a regular pattern. A fixed cadence is trivially detectable by an observer computing event inter-arrival statistics over a long capture.

P.372-15 characterises atmospheric noise as a non-Gaussian impulsive process. The inter-event arrival time distribution of atmospheric impulse noise at HF follows a heavy-tailed form, well approximated by a Pareto distribution with shape parameter alpha between 1.5 and 2.5 depending on frequency and noise zone. The HKDF-derived pseudo-random offsets are mapped through an inverse Pareto quantile function using the P.372-15 averaged parameters to produce inter-burst intervals with the correct statistical shape.

Both transmitter and receiver apply the identical transform to the raw HKDF output, so the schedule remains deterministic and shared without any additional communication.

### 4.3 Burst Energy and Spectral Shape

Natural atmospheric impulse noise at HF occupies a broad instantaneous bandwidth with energy decaying away from the impulse spectral centre. The PN spreading already distributes burst energy across the spreading bandwidth. The chip rate and spreading factor must be chosen so that the resulting spectral occupancy matches the bandwidth of typical atmospheric noise impulses in the target band as characterised by P.372-15 and supporting sferic waveform literature.

If the chip rate is too narrow, the burst appears as a narrowband tone against a wideband noise floor. If too wide, it exceeds the channel coherence bandwidth and degrades correlation performance. The spectral shape of the transmitted burst should be validated against the P.372-15 noise spectral density profile for the target frequency before deployment.

### 4.4 Burst Duration

The 2 ms burst duration matches the typical duration of atmospheric sferic events at HF as documented in the literature and consistent with P.372-15 impulse noise characterisation. This duration is retained across all bursts in the schedule. Varying burst duration between schedule positions would introduce a detectable feature and is not recommended.

### 4.5 Per-Burst Amplitude Jitter

Real atmospheric noise events vary in amplitude from event to event. A perfectly constant-amplitude burst schedule would stand out against a noise floor where energy levels fluctuate. The Gaussian envelope handles intra-burst amplitude shaping; a pseudo-random inter-burst amplitude scaling factor is applied on top of it.

This scaling factor is derived from Key 3 or Key 4 material using a separate HKDF-Expand output with a distinct domain label, and mapped to a log-normal distribution. The log-normal parameters — mean and standard deviation in log space — are set from the P.372-15 averaged amplitude deviation statistics for the target frequency range. Both transmitter and receiver agree on the same scaling sequence, so the receiver applies the correct expected amplitude when computing its matched filter gain.

### 4.6 Required Statistical Tests

Before deployment, the burst schedule must pass a set of statistical tests against a null hypothesis of natural atmospheric noise consistent with P.372-15.

- Inter-arrival time distribution: Kolmogorov-Smirnov test against the Pareto model derived from P.372-15 averaged parameters. The schedule should not be distinguishable from a natural noise process at a significance level appropriate to the intended detection adversary.
- Amplitude distribution across bursts: log-normal fit quality against the P.372-15 amplitude deviation model for the target frequency.
- Spectral flatness within each burst: the in-band power spectral density of the PN-spread burst should match the spectral shape of broadband impulse noise consistent with P.372-15, not a flat or peaked tone.
- Cross-correlation across burst indices: verify that PN sequences derived for burst_index N and burst_index M have cross-correlation below the expected noise floor for all tested pairs.
- Conservative constraint compliance: no inter-burst interval in the schedule is shorter than the minimum event inter-arrival time derived from the P.372-15 quiet-site design constraint.

### 4.7 P.372-15 Averaging Matrix

The noise mimicry parameters are not derived from a single P.372-15 scenario but from an average computed across a representative matrix of locations, times of day, seasons, and solar flux conditions. This produces a baseline that is valid across all realistic deployment environments rather than optimised for any single one.

The conservative end of the averaged distribution — the quietest location, time, season, and solar flux combination — is used as the design constraint. This ensures the burst schedule is statistically plausible even in the most benign noise environment the system might encounter, since a schedule that appears natural in a noisy urban environment may appear anomalous in a quiet rural one.

**Geographic locations**

A minimum of six representative locations spanning the ITU-R P.372-15 noise zones are included in the average. The suggested set covers a northern European rural site, a mid-latitude North American rural site, a tropical coastal site, a mid-latitude southern hemisphere site, an equatorial site, and a high-latitude Arctic or sub-Arctic site. These span the full range of atmospheric noise zones defined in P.372-15 from the quietest high-latitude zones to the noisiest equatorial and tropical zones.

**Time of day**

P.372-15 divides the day into four six-hour blocks: 0000 to 0600, 0600 to 1200, 1200 to 1800, and 1800 to 2400 local time. All four blocks are included in the average. The 0000 to 0600 block typically yields the highest atmospheric noise at HF due to enhanced skywave propagation of distant lightning-generated sferics. The 1200 to 1800 block typically yields the lowest. The design constraint is taken from the quietest block across the quietest location, giving the minimum natural event rate the burst schedule must remain plausible against.

**Seasons**

P.372-15 provides separate noise estimates for four seasons. All four are included in the average. Atmospheric noise is generally highest in summer due to greater global thunderstorm activity and lowest in winter at high latitudes. The winter quiet-site daytime scenario defines the minimum event rate constraint used for schedule parameterisation.

**Solar flux and ionospheric conditions**

Solar activity affects HF propagation and therefore the received intensity of distant atmospheric noise at any given location. Three solar flux index levels are used in the average: low representing solar minimum conditions with a solar flux index below 80, medium representing moderate activity with a solar flux index between 100 and 150, and high representing solar maximum with a solar flux index above 150. Under low solar flux, D-layer absorption is reduced and nighttime skywave propagation is enhanced, increasing the received sferic rate from distant sources. Under high solar flux, daytime absorption increases and the received sferic rate from distant sources decreases. Both extremes are represented in the average to ensure the model spans the full range of realistic ionospheric conditions.

The computed average across the full matrix produces the nominal parameter set used for the burst schedule and amplitude jitter model. The minimum across the matrix produces the conservative design constraint against which all schedule parameters and statistical tests are validated.

---

## 5. Code Change Surface

### 5.1 Files Requiring Changes

`python/sync_burst_utils.py` — primary change file.

- Extend `derive_sync_schedule` to return an ordered list of timing offsets rather than a single scalar. Add the inter-burst interval Pareto quantile transform using P.372-15 averaged parameters. Add a configurable `n_bursts` parameter.
- Extend `derive_sync_pn_sequence` to accept a `burst_index` parameter, appending it to the HKDF domain label to produce a unique PN seed per burst. Default `burst_index=0` preserves backward compatibility.
- Add a per-burst amplitude scaling derivation function using HKDF-Expand with a distinct domain label, returning a log-normally distributed scaling factor sequence parameterised from P.372-15.
- Add a P.372-15 parameter loader that reads the precomputed averaged noise statistics from a static configuration file and exposes them to the schedule and amplitude derivation functions.

`tests/test_t2_sync_burst.py` — new test cases covering schedule length, no-collision between burst offsets, inter-burst interval distribution shape against the P.372-15 Pareto model, conservative constraint compliance, per-burst PN uniqueness, backward compatibility of `burst_index=0`, amplitude scaling factor determinism, and amplitude distribution shape against the P.372-15 log-normal model.

`python/p372_baseline.py` — new module. Encapsulates the P.372-15 averaged parameter computation. Reads the averaging matrix definition, computes Fa values for each matrix cell using the P.372-15 formula, and returns the averaged and minimum-case parameter sets for use by the schedule and amplitude derivation functions. This module is the single authoritative source for all noise model parameters in the system.

### 5.2 Files Requiring No Changes

`python/session_key_derivation.py` — no structural change required. The `sync_timing` subkey it already returns is passed into the extended `derive_sync_schedule` signature by the caller. The `derive_session_keys` function output is unchanged.

`lib/kgdss_spreader_cc_impl.cc` and `lib/kgdss_despreader_cc_impl.cc` — both operate on the chip stream and are agnostic to burst count and schedule. Burst injection and detection occur in the Python flow graph layer above them.

`include/gnuradio/kgdss/kgdss_spreader_cc.h` and `kgdss_despreader_cc.h` — public API surface is unchanged.

`python/bindings/` — no new methods are exposed to Python. The C++ block interface is unchanged.

---

## 6. Parameter Selection Guidance

### 6.1 Burst Count and Cadence

The number of bursts per session window and the window duration together determine the maximum desynchronisation interval. Choosing these values involves a three-way tradeoff between recovery latency, channel occupancy, and covertness.

A shorter cadence gives lower recovery latency and less flywheel drift but produces more transmit events that must individually pass statistical scrutiny against the P.372-15 baseline. A longer cadence is easier to disguise statistically but allows more drift and a wider potential loss window if multiple consecutive bursts are missed.

The mean inter-burst interval must be no shorter than the minimum natural impulse event inter-arrival time computed from the P.372-15 conservative design constraint — the quietest location, season, time of day, and solar flux combination in the averaging matrix. Using a shorter interval would make the burst cadence statistically anomalous in quiet environments even if unremarkable in busy ones.

A recommended starting point derived from P.372-15 lower-bound conditions is a mean inter-burst interval of 30 to 90 seconds with Pareto-distributed jitter. This should be validated against the oscillator drift rate of the receiver hardware before finalising.

### 6.2 Flywheel Stability Bound

The receiver flywheel extrapolates timing between bursts using its local oscillator. The allowable inter-burst interval is bounded above by the oscillator drift rate multiplied by the maximum timing error the LDPC decoder and despreader can tolerate without a sync correction. This must be computed for the actual receiver hardware before the cadence schedule is finalised.

For the B210/B220 with its on-board 26 MHz TCXO at approximately 2 ppm, the expected timing drift over a 90 second inter-burst interval at HF sample rates must be verified against the despreader's timing tolerance. An external GPSDO reference reduces drift to sub-ppb and substantially relaxes the inter-burst interval upper bound.

### 6.3 Correlation Search Window

At each scheduled burst position, the receiver opens a correlation search window around the predicted arrival time. The window must be wide enough to cover oscillator drift accumulated since the last burst, but narrow enough to avoid false lock on ambient noise. The window half-width should be set to approximately three standard deviations of the expected drift distribution for the hardware in use.

---

## 7. Test Plan Additions

The following test cases are added to `tests/test_t2_sync_burst.py`.

- **Schedule determinism** — same inputs produce an identical schedule on transmitter and receiver across platforms and Python versions.
- **Schedule length** — the returned offset list contains exactly the requested number of bursts.
- **No inter-burst collisions** — no two burst positions in the schedule overlap within one burst duration of each other.
- **Interval distribution shape** — KS test of inter-burst intervals against the Pareto model derived from P.372-15 averaged parameters.
- **Conservative constraint compliance** — no inter-burst interval in the schedule is shorter than the minimum derived from the P.372-15 quiet-site design constraint.
- **Per-burst PN uniqueness** — the PN sequence for burst_index N is distinct from burst_index M for all tested pairs.
- **Backward compatibility** — `burst_index=0` produces the same PN sequence as the current single-burst implementation.
- **Amplitude scaling determinism** — per-burst amplitude scaling factors are identical on transmitter and receiver for the same key material.
- **Amplitude distribution shape** — log-normal fit quality of the amplitude scaling sequence against the P.372-15 averaged amplitude deviation model.
- **P.372-15 parameter loader** — averaged and minimum-case parameter sets are deterministic and consistent across platforms and Python versions.

---

## 8. Open Questions

- What is the oscillator drift rate of the target receiver hardware under operational temperature conditions? This sets the hard upper bound on the inter-burst interval and should be measured under realistic conditions rather than taken from the datasheet alone.
- Should the burst count per session be fixed or itself derived from key material? A key-derived burst count adds one more unpredictable parameter for an observer but complicates session lifecycle management.
- Should missed bursts trigger any protocol-level event, or should the flywheel operate silently? Silent operation is more covert; flagging missed bursts enables diagnostic monitoring.
- What is the upper HF frequency limit above which the P.372-15 atmospheric noise model produces a natural event rate so low that any additional burst event is statistically anomalous? This defines the maximum operating frequency for the atmospheric mimicry approach and should be computed explicitly from the P.372-15 quiet-site conservative constraint across the averaging matrix.
- Should the averaging matrix be extended to include man-made noise contributions from P.372-15 Section 3 for urban deployment scenarios, or should the design remain conservative by using atmospheric noise alone as the universal mimicry target?
