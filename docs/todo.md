# KGDSS: Sync Burst Improvements

**Implementation Proposal — Noise-Mimicking Burst Cadence and Future Enhancements**

---

## 1. Purpose

This document captures proposed improvements to the KGDSS synchronisation subsystem, ordered by implementation priority. The core change — replacing the single sync burst with a scheduled multi-burst cadence — is addressed first and is the primary deliverable. Subsequent sections describe further enhancements ranked by importance, each buildable independently on top of the core change.

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

## 3. Priority 1 — Scheduled Multi-Burst Cadence

This is the primary change. It must be implemented before any subsequent enhancement. Everything else in this document builds on the multi-burst foundation.

### 3.1 Core Principle

Rather than a single burst at session start, the transmitter emits a pseudo-random sequence of sync bursts throughout the session lifetime. Both transmitter and receiver derive the identical schedule deterministically from Key 4 (sync_timing), so no additional signalling is needed to convey burst timing. The receiver always knows when to look; an observer never does.

### 3.2 Schedule Derivation

The function `derive_sync_schedule` in `python/sync_burst_utils.py` is extended from returning a single timing offset to returning an ordered list of offsets. The derivation uses HKDF-Expand with Key 4 as the input key material, the session identifier as context, and a burst index counter as a domain separator suffix.

Each burst offset is drawn pseudo-randomly within a configurable window. Both the window duration and the number of bursts per window are parameters. The burst index counter increments monotonically, ensuring each offset in the schedule is independently derived and unpredictable without the key.

The raw HKDF output is mapped through a Pareto quantile transform derived from the ITU-R P.372-15 baseline atmospheric noise model to produce inter-burst intervals with the correct heavy-tailed statistical shape. Both transmitter and receiver apply the identical transform, so the schedule remains deterministic and shared without any additional communication.

The `session_key_derivation` module requires no structural change. The `sync_timing` subkey it already returns is passed directly into the extended `derive_sync_schedule` call.

### 3.3 Per-Burst PN Sequence Evolution

In the current design, the same PN sequence derived once from Key 3 is used for every burst. With multiple bursts, reusing the identical sequence creates a weak correlation: an observer who accumulates enough radio captures and aligns them correctly could potentially detect the recurring pattern even if individual bursts are buried in noise.

To eliminate this, the PN sequence is evolved per burst. The `derive_sync_pn_sequence` function is extended to accept a `burst_index` parameter. The derivation appends the burst index to the HKDF domain label, producing a unique PN seed per burst. Each burst therefore presents a different spreading sequence to the channel, eliminating any cross-burst correlation an observer could exploit.

The change is backward-compatible: `burst_index` defaults to zero, so the existing single-burst behaviour is preserved without modification to callers that do not pass the parameter.

### 3.4 Receiver Recovery Behaviour

The receiver maintains a flywheel — an internal timing estimate extrapolated from the last successfully decoded burst. Between bursts, the flywheel drifts at a rate determined by the local oscillator stability. When the next burst position arrives, the receiver opens a correlation window around the predicted arrival time and attempts to lock on the expected PN sequence for that burst index.

If the burst is detected, timing is corrected and the flywheel is reset. If the burst is missed, the flywheel continues. The maximum desynchronisation is bounded: in the worst case the receiver misses every burst in a run, but once it catches any subsequent burst it re-locks immediately. The LDPC decoder receives clean, correctly aligned frames again from that point onward.

This is a fundamentally different failure mode from the single-burst case. Loss is bounded to the frames between two adjacent burst positions rather than potentially the entire remaining session.

### 3.5 Noise Mimicry Requirements

The expanded burst schedule introduces more transmit events, which increases the statistical surface area available to a passive observer. Each design decision must be evaluated not only for its synchronisation benefit but for its impact on RF signature.

All noise mimicry parameters are derived from ITU-R P.372-15, the internationally standardised model for atmospheric radio noise covering 10 kHz to 100 MHz. Parameters are computed as averages across a representative matrix of conditions described in Section 3.6, ensuring the system is valid across all deployment environments rather than optimised for any single location.

**Amplitude envelope** — each burst retains the Gaussian amplitude envelope implemented in `gaussian_envelope` in `python/sync_burst_utils.py`. The `rise_fraction` parameter is set to 0.15, derived from published sferic waveform literature showing HF atmospheric sferics exhibit rise times of 0.1 to 0.3 ms and decay times of 0.5 to 1.5 ms. This replaces the previous default of 0.1.

**Inter-burst interval distribution** — the inter-burst interval must not follow a regular pattern. The HKDF-derived offsets are mapped through an inverse Pareto quantile function with shape parameter alpha between 1.5 and 2.5, consistent with the P.372-15 characterisation of HF atmospheric noise inter-event arrival times.

**Burst energy and spectral shape** — the chip rate and spreading factor must be chosen so that the resulting spectral occupancy matches the bandwidth of typical atmospheric noise impulses in the target band. The spectral shape of the transmitted burst should be validated against the P.372-15 noise spectral density profile for the target frequency before deployment.

**Burst duration** — the 2 ms burst duration matches the typical duration of atmospheric sferic events at HF and is retained across all bursts in the schedule. Varying burst duration between positions would introduce a detectable feature.

**Per-burst amplitude jitter** — a pseudo-random inter-burst amplitude scaling factor is applied on top of the Gaussian envelope, derived from key material using a separate HKDF-Expand output with a distinct domain label. The scaling factor follows a log-normal distribution with parameters set from P.372-15 averaged amplitude deviation statistics. Both transmitter and receiver agree on the same scaling sequence.

**Power and the noise floor** — the natural HF noise floor is never perfectly flat. Natural impulse events routinely produce peaks 10 to 30 dB above the median floor. A burst that exceeds the median floor is not anomalous provided it sits within the plausible tail of the natural amplitude distribution for the band and conditions. This gives the transmitter meaningful power headroom above the median floor while remaining statistically natural, which is important for closing the link over distance. The usable headroom is bounded by the upper tail of the natural amplitude distribution rather than the median floor, and varies with band, time of day, and atmospheric conditions.

### 3.6 P.372-15 Averaging Matrix

Noise mimicry parameters are computed as an average across a representative matrix of locations, times of day, seasons, and solar flux conditions rather than from any single scenario. The conservative end of the distribution — the quietest combination — is used as the design constraint, ensuring the burst schedule is statistically plausible even in the most benign noise environment the system might encounter.

**Geographic locations** — a minimum of six locations spanning the P.372-15 noise zones: a northern European rural site, a mid-latitude North American rural site, a tropical coastal site, a mid-latitude southern hemisphere site, an equatorial site, and a high-latitude Arctic or sub-Arctic site.

**Time of day** — all four P.372-15 six-hour blocks: 0000 to 0600, 0600 to 1200, 1200 to 1800, and 1800 to 2400 local time. The 0000 to 0600 block typically yields the highest atmospheric noise. The 1200 to 1800 block yields the lowest and defines the quiet-time design constraint.

**Seasons** — all four seasons. Winter at high-latitude quiet sites defines the minimum event rate constraint used for schedule parameterisation.

**Solar flux** — three levels: low representing solar minimum with solar flux index below 80, medium between 100 and 150, and high above 150 representing solar maximum. Both extremes are included to span the full range of realistic ionospheric conditions.

The computed average across the full matrix produces the nominal parameter set. The minimum across the matrix produces the conservative design constraint used for all schedule parameterisation and statistical validation.

### 3.7 Code Changes

`python/sync_burst_utils.py` — primary change file. Extend `derive_sync_schedule` to return an ordered list of offsets with Pareto quantile transform and configurable `n_bursts` parameter. Extend `derive_sync_pn_sequence` to accept `burst_index` parameter with default of zero for backward compatibility. Add per-burst amplitude scaling derivation function returning a log-normally distributed sequence parameterised from P.372-15. Add P.372-15 parameter loader reading precomputed averaged statistics from a static configuration file.

`python/p372_baseline.py` — new module. Single authoritative source for all noise model parameters. Computes Fa values across the averaging matrix and returns averaged and minimum-case parameter sets.

`tests/test_t2_sync_burst.py` — new test cases covering schedule length, no inter-burst collisions, interval distribution shape against P.372-15 Pareto model, conservative constraint compliance, per-burst PN uniqueness, backward compatibility of `burst_index=0`, amplitude scaling determinism, amplitude distribution shape, and P.372-15 parameter loader determinism.

`python/session_key_derivation.py`, `lib/kgdss_spreader_cc_impl.cc`, `lib/kgdss_despreader_cc_impl.cc`, `include/gnuradio/kgdss/`, and `python/bindings/` — no changes required.

### 3.8 Parameter Selection

The mean inter-burst interval must be no shorter than the minimum natural impulse event inter-arrival time from the P.372-15 conservative constraint. A recommended starting point is 30 to 90 seconds mean interval with Pareto-distributed jitter. This must be validated against the oscillator drift rate of the receiver hardware.

For the B210/B220 with its on-board 26 MHz TCXO at approximately 2 ppm, timing drift over a 90 second inter-burst interval must be verified against the despreader's timing tolerance. An external GPSDO reference reduces drift to sub-ppb and substantially relaxes the upper bound on inter-burst interval.

At each scheduled burst position, the receiver opens a correlation search window around the predicted arrival time. The window half-width should be set to approximately three standard deviations of the expected drift distribution for the hardware in use.

---

## 4. Priority 2 — Real-Time Noise Floor Measurement

**Importance: high. Dependency: Priority 1 complete.**

The SDR is already running, already has the RF window open, and is already computing spectral data for despreading and correlation. Measuring the noise floor is computationally free — it is a statistical operation on samples already being processed. No additional DSP chain is required.

A running estimate of the noise floor power spectral density across the monitored RF window is computed as the median magnitude across a rolling time window. The median is used rather than the mean because it is robust against the impulse events themselves skewing the estimate upward. The result is a calibrated noise floor level in dBm per bin updated continuously during operation.

This real-time measurement supersedes P.372-15 as the primary parameter source once sufficient samples have accumulated. P.372-15 remains the cold-start fallback used during the first few seconds of a session before the local estimate is reliable. After that the live measurement takes over, providing ground truth for the current location, frequency, time of day, and ionospheric conditions rather than a global model average.

The real-time floor measurement also provides the local upper tail of the natural amplitude distribution, which is the practical power budget ceiling for burst transmission. Because the natural noise floor is never perfectly flat and natural impulse events routinely produce peaks well above the median, the transmitter has usable headroom above the median floor that is still statistically plausible. The live measurement quantifies exactly how much headroom is available at any given moment, allowing the system to use it confidently without exceeding the plausible natural amplitude range for current conditions.

The inter-arrival times and amplitudes of detected impulse events in the live measurement window also allow progressive refinement of the Pareto and log-normal distribution parameters used for schedule generation and amplitude jitter, replacing the P.372-15 averaged values with locally observed values as data accumulates.

---

## 5. Priority 3 — SQLite Noise Floor History

**Importance: medium. Dependency: Priority 2 complete.**

Timestamped noise floor measurements from the real-time estimator are written to a local SQLite database. Each row records the timestamp in UTC, centre frequency, monitoring bandwidth, median noise floor in dBm, upper tail amplitude estimate, and observed impulse event rate. A single row is approximately 50 bytes. Thousands of measurements fit in a few hundred kilobytes. The database grows slowly and imposes no meaningful storage cost.

The historical database serves several purposes. It provides a warm-start baseline at session initialisation that is better than P.372-15 for the specific deployment location, replacing the cold-start fallback with locally observed statistics from previous sessions on the same band. Over weeks of operation the local database becomes the primary parameter source for that deployment, reflecting the actual noise environment rather than a global model average.

The database also captures diurnal and seasonal variation at the deployment location. This allows the system to anticipate noise floor behaviour by time of day without waiting for live measurements to accumulate, which is particularly useful at session start.

The schema should include at minimum the following columns: timestamp (UTC integer), frequency_hz (integer), bandwidth_hz (integer), noise_floor_dbm (real), upper_tail_dbm (real), impulse_rate_per_minute (real), and session_id (text). Indexes on timestamp and frequency_hz support efficient range queries for historical lookup by band and time window.

---

## 6. Priority 4 — GPS-Assisted Dual-Site Noise Floor Exchange

**Importance: medium-low. Dependency: Priority 3 complete. Requires GPS hardware at both ends.**

If both radios are fitted with GPS receivers they already have accurate location coordinates and UTC time at no additional cost to the RF link. Each radio logs its own noise floor measurements tagged with position and timestamp into its local SQLite database as described in Priority 3.

These databases are exchanged out-of-band using the same off-air channel already used for GnuPG public key exchange at session setup. The exchange adds no RF traffic and no new protocol machinery. After exchange, both radios hold noise floor profiles for both ends of the link across multiple bands, times of day, and seasons.

The transmitter can then set burst power to be within the statistically natural amplitude range at both the transmitter location and the receiver location simultaneously, rather than only at the local end. This is a meaningful improvement over single-ended measurement in cases where the two sites have significantly different noise environments — for example a transmitter at an urban site and a receiver at a quiet rural site. Without the exchange the transmitter would set power based on its own noisy local floor and potentially transmit above the natural ceiling at the quiet receiver end. With the exchange it knows the receiver's local statistics and can calibrate accordingly.

The GPS position data also enables future use of P.372-15 in a targeted mode — computing the noise model for the specific receiver location rather than averaging across the full matrix — further refining the parameter set for the actual deployment geometry.

The interface boundary for this enhancement is well-defined: the SQLite schema from Priority 3, a simple merge procedure for combining two databases, and the existing out-of-band exchange channel. None of the core burst design is affected.

---

## 7. Open Questions

- What is the oscillator drift rate of the target receiver hardware under operational temperature conditions? This sets the hard upper bound on the inter-burst interval and should be measured under realistic conditions rather than taken from the datasheet alone.
- Should the burst count per session be fixed or itself derived from key material? A key-derived burst count adds one more unpredictable parameter for an observer but complicates session lifecycle management.
- Should missed bursts trigger any protocol-level event, or should the flywheel operate silently? Silent operation is more covert; flagging missed bursts enables diagnostic monitoring.
- What is the upper HF frequency limit above which the P.372-15 atmospheric noise model produces a natural event rate so low that any additional burst event is statistically anomalous? This defines the maximum operating frequency for the atmospheric mimicry approach and should be computed from the P.372-15 quiet-site conservative constraint.
- Should the averaging matrix be extended to include man-made noise contributions from P.372-15 Section 3 for urban deployment scenarios, or should the design remain conservative by using atmospheric noise alone as the universal mimicry target?
- At what point in the real-time measurement accumulation window is the local estimate considered reliable enough to replace the P.372-15 cold-start fallback? A minimum sample count or minimum elapsed time threshold needs to be defined.
