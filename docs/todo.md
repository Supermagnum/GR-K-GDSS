# KGDSS: Sync Burst Improvements

**Implementation Proposal — Noise-Mimicking Burst Cadence and Future Enhancements**

---

## 1. Purpose

This document captures proposed improvements to the KGDSS synchronisation subsystem, ordered by implementation priority. The core change — replacing the single sync burst with a scheduled multi-burst cadence — is addressed first and is the primary deliverable. Subsequent sections describe further enhancements ranked by importance, each buildable independently on top of the core change.

---

## 2. Completed in this repository

The following items from the original Priority 1 scope have been implemented:

- Scheduled **multi-burst sync cadence** (deterministic schedule from key material).
- **Per-burst PN evolution** via `burst_index` (with backward-compatible default).
- **Per-burst amplitude scaling** derivation.
- Updated sync burst envelope default (`rise_fraction=0.15`).
- Static **P.372 baseline parameter source** in Python.
- Receiver-side **P.372 profile calibration helpers** (frequency-bin PSD alignment).
- Test coverage for the above in `test_t2_sync_burst.py` and `test_p372_receiver_profile.py`.

This document now tracks the remaining priorities.

---

## 3. Priority 2 — Real-Time Noise Floor Measurement

**Importance: high. Dependency: Priority 1**

The SDR is already running, already has the RF window open, and is already computing spectral data for despreading and correlation. Measuring the noise floor is computationally free — it is a statistical operation on samples already being processed. No additional DSP chain is required.

A running estimate of the noise floor power spectral density across the monitored RF window is computed as the median magnitude across a rolling time window. The median is used rather than the mean because it is robust against the impulse events themselves skewing the estimate upward. The result is a calibrated noise floor level in dBm per bin updated continuously during operation.

This real-time measurement supersedes P.372-15 as the primary parameter source once sufficient samples have accumulated. P.372-15 remains the cold-start fallback used during the first few seconds of a session before the local estimate is reliable. After that the live measurement takes over, providing ground truth for the current location, frequency, time of day, and ionospheric conditions rather than a global model average.

The real-time floor measurement also provides the local upper tail of the natural amplitude distribution, which is the practical power budget ceiling for burst transmission. Because the natural noise floor is never perfectly flat and natural impulse events routinely produce peaks well above the median, the transmitter has usable headroom above the median floor that is still statistically plausible. The live measurement quantifies exactly how much headroom is available at any given moment, allowing the system to use it confidently without exceeding the plausible natural amplitude range for current conditions.

The inter-arrival times and amplitudes of detected impulse events in the live measurement window also allow progressive refinement of the Pareto and log-normal distribution parameters used for schedule generation and amplitude jitter, replacing the P.372-15 averaged values with locally observed values as data accumulates.

---

## 4. Priority 3 — SQLite Noise Floor History

**Importance: medium. Dependency: Priority 2**

Timestamped noise floor measurements from the real-time estimator are written to a local SQLite database. Each row records the timestamp in UTC, centre frequency, monitoring bandwidth, median noise floor in dBm, upper tail amplitude estimate, and observed impulse event rate. A single row is approximately 50 bytes. Thousands of measurements fit in a few hundred kilobytes. The database grows slowly and imposes no meaningful storage cost.

The historical database serves several purposes. It provides a warm-start baseline at session initialisation that is better than P.372-15 for the specific deployment location, replacing the cold-start fallback with locally observed statistics from previous sessions on the same band. Over weeks of operation the local database becomes the primary parameter source for that deployment, reflecting the actual noise environment rather than a global model average.

The database also captures diurnal and seasonal variation at the deployment location. This allows the system to anticipate noise floor behaviour by time of day without waiting for live measurements to accumulate, which is particularly useful at session start.

The schema should include at minimum the following columns: timestamp (UTC integer), frequency_hz (integer), bandwidth_hz (integer), noise_floor_dbm (real), upper_tail_dbm (real), impulse_rate_per_minute (real), and session_id (text). Indexes on timestamp and frequency_hz support efficient range queries for historical lookup by band and time window.

---

## 5. Priority 4 — GPS-Assisted Dual-Site Noise Floor Exchange

**Importance: medium-low. Dependency: Priority 3 complete. Requires GPS hardware at both ends.**

If both radios are fitted with GPS receivers they already have accurate location coordinates and UTC time at no additional cost to the RF link. Each radio logs its own noise floor measurements tagged with position and timestamp into its local SQLite database as described in Priority 3.

These databases are exchanged out-of-band using the same off-air channel already used for GnuPG public key exchange at session setup. The exchange adds no RF traffic and no new protocol machinery. After exchange, both radios hold noise floor profiles for both ends of the link across multiple bands, times of day, and seasons.

The transmitter can then set burst power to be within the statistically natural amplitude range at both the transmitter location and the receiver location simultaneously, rather than only at the local end. This is a meaningful improvement over single-ended measurement in cases where the two sites have significantly different noise environments — for example a transmitter at an urban site and a receiver at a quiet rural site. Without the exchange the transmitter would set power based on its own noisy local floor and potentially transmit above the natural ceiling at the quiet receiver end. With the exchange it knows the receiver's local statistics and can calibrate accordingly.

The GPS position data also enables future use of P.372-15 in a targeted mode — computing the noise model for the specific receiver location rather than averaging across the full matrix — further refining the parameter set for the actual deployment geometry.

The interface boundary for this enhancement is well-defined: the SQLite schema from Priority 3, a simple merge procedure for combining two databases, and the existing out-of-band exchange channel. None of the core burst design is affected.

---

## 6. Open Questions

- What is the oscillator drift rate of the target receiver hardware under operational temperature conditions? This sets the hard upper bound on the inter-burst interval and should be measured under realistic conditions rather than taken from the datasheet alone.
- Should the burst count per session be fixed or itself derived from key material? A key-derived burst count adds one more unpredictable parameter for an observer but complicates session lifecycle management.
- Should missed bursts trigger any protocol-level event, or should the flywheel operate silently? Silent operation is more covert; flagging missed bursts enables diagnostic monitoring.
- What is the upper HF frequency limit above which the P.372-15 atmospheric noise model produces a natural event rate so low that any additional burst event is statistically anomalous? This defines the maximum operating frequency for the atmospheric mimicry approach and should be computed from the P.372-15 quiet-site conservative constraint.
- Should the averaging matrix be extended to include man-made noise contributions from P.372-15 Section 3 for urban deployment scenarios, or should the design remain conservative by using atmospheric noise alone as the universal mimicry target?
- At what point in the real-time measurement accumulation window is the local estimate considered reliable enough to replace the P.372-15 cold-start fallback? A minimum sample count or minimum elapsed time threshold needs to be defined.
- How much overhead will sharing rf noise measurements need? 
