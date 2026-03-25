# HF Noise Baseline Recording Plan

**Purpose: Empirical characterisation of natural band noise for KGDSS sync burst mimicry parameter derivation**

---

## 1. Equipment

The FT-710 or as sdr radio with 85 metre loop antenna covers all amateur bands from 80m through 6m and is used for AM audio envelope recording or IQ files across the full HF range. The loop antenna is near resonance at 3.5 MHz, giving maximum sensitivity on the most noise-rich band, and remains effective through the mid-HF range.

The B210/B220 with AD9361 covers 70 MHz and above and is used for IQ recording at VHF and above, providing phase-coherent complex samples suitable for spectral shape and rise time analysis that AM audio cannot deliver.

There is a gap between 54 MHz (top of 6m) and 70 MHz (bottom of B210 range) that neither instrument covers. This range has no significant atmospheric impulse noise and is not operationally relevant to the characterisation effort.

---

## 2. Recording Schedule

### 2.1 FT-710 or similar Bands

Nine bands, two recordings each, ten minutes per recording. Total FT-710 recording time is 180 minutes across the full schedule.

| Band | Frequency | Day | Night | Notes |
|------|-----------|-----|-------|-------|
| 80m | 3.5 MHz | yes | yes | Highest priority. Loop near resonance. Richest sferic density. |
| 40m | 7 MHz | yes | yes | High priority. Strong day/night contrast. |
| 30m | 10 MHz | yes | yes | WARC band. Low man-made interference. Clean atmospheric sample. |
| 20m | 14 MHz | yes | yes | Atmospheric noise declining. Mixed natural and man-made impulses. |
| 17m | 18 MHz | yes | yes | Transition zone. Natural impulse rate low. |
| 15m | 21 MHz | yes | yes | Natural noise sparse. Man-made dominates. |
| 12m | 24 MHz | yes | yes | Atmospheric noise essentially absent. |
| 10m | 28 MHz | yes | yes | Thermal and man-made noise only. Solar flux relevant. |
| 6m  | 50 MHz | yes | yes | Lowest priority. Natural impulse events extremely rare. |

### 2.2 B210 Bands

IQ recordings at VHF and above for spectral characterisation where the FT-710 audio chain cannot provide RF-level detail.

| Band | Frequency | Notes |
|------|-----------|-------|
| 2m | 144 MHz | Most useful VHF amateur band within B210 range. |
| 70cm | 430 MHz | UHF reference. Noise almost entirely thermal and man-made. |

Additional frequencies above 70 MHz may be added based on candidate operating frequency selection.

---

## 3. Session Management

### 3.1 Do Not Record Everything in One Sitting

Spreading recordings across multiple days is beneficial, not merely convenient. Propagation conditions, ionospheric state, and regional thunderstorm activity vary day to day. A dataset recorded across multiple sessions reflects the natural variation in noise conditions that the burst schedule will encounter during real operation. A dataset recorded in a single session reflects only that day's conditions.

A practical split is three or four bands per session, mixing day and night recordings across bands to make efficient use of time at the radio.

### 3.2 Minimum Viable Dataset

If the full 18 FT-710 recordings prove impractical to complete, the highest-value subset is 80m, 40m, and 20m, day and night. These six recordings covering 60 minutes span the full range from noise-rich to noise-moderate HF and are sufficient to derive the core statistical models. Remaining bands can be added later.

---

## 4. Recording Procedure

### 4.1 FT-710 or similar Settings

Set the receiver to AM mode on a clear frequency within the target band. Use manual RF gain rather than AGC. Set gain so that background noise is clearly audible and present in the recording but strong impulse events are not clipping. Note the exact gain setting used — if gain varies between recordings, amplitude measurements across recordings become incomparable.

Confirm AGC is off or set to slow before starting each recording. AGC activity during recording invalidates amplitude distribution measurements because the receiver is continuously rescaling the signal.

Record audio at 48 kHz sample rate. Lower sample rates such as 8 or 16 kHz discard rise and fall detail from impulse events. 48 kHz preserves enough temporal resolution to measure impulse rise times even from the AM envelope, which feeds directly into the rise_fraction parameter validation.

### 4.2 B210 Settings

Use a fixed manual gain setting noted in the log. Apply DC offset and IQ imbalance calibration before recording and use the same calibration state for all subsequent transmission and reception in the session. Capturing baseline noise with a different calibration state than the one used for burst transmission would introduce a systematic mismatch between the synthetic burst and the noise environment it is trying to mimic.

Record at the sample rate intended for actual session use. Do not record at a higher rate and downsample later — the AD9361 analog filter chain and digital processing will shape the noise differently at different sample rates, and you want the baseline to reflect the exact hardware state of a real session.

### 4.3 File Naming Convention

Use a consistent filename format for every recording before the session begins. The following format captures all information needed to reconstruct recording conditions without relying on memory or separate notes.

YYYYMMDD-HHMM-BAND-DAY-GAIN.wav

For example: 20240315-0630-80m-DAY-32.wav

For B210 IQ files: YYYYMMDD-HHMM-144MHz-DAY-GAIN.iq

### 4.4 Conditions Log

Maintain a simple log alongside the recordings. For each recording note the date, start time in UTC, band, mode, gain setting, AGC state, weather conditions locally, and any notable propagation events such as aurora, sporadic-E, or geomagnetic storm activity. Cross-reference solar flux index from the NOAA solar data archive or a propagation resource such as DXmaps after the fact. Knowing whether a recording was made during disturbed or quiet conditions allows outlier recordings to be identified and handled appropriately during analysis.

---

## 5. What the Data Is Used For

Each measurement extracted from the recordings maps directly to one or more open parameters in the KGDSS multi-burst design document.

### 5.1 Inter-Arrival Time Distribution

Extracted from: FT-710 AM audio recordings via impulse event detection and timestamping.

Used for: Deriving the quantile transform applied to HKDF output in derive_sync_schedule. The burst schedule inter-burst intervals must be drawn from a distribution statistically indistinguishable from the natural impulse inter-arrival distribution measured on the operating band. Without this measurement the schedule uses an assumed distribution that may not match the real noise environment and could be detectable by a sufficiently patient observer.

### 5.2 Amplitude Distribution

Extracted from: FT-710 AM audio recordings via peak amplitude measurement of each detected impulse event.

Used for: Fitting the log-normal amplitude jitter model applied to per-burst scaling factors in the multi-burst design. The parameters of the log-normal distribution — mean and standard deviation in log space — are set from the measured amplitude histogram rather than assumed from literature. This ensures the per-burst amplitude variation in the transmitted schedule matches the variation a real observer would measure in the natural noise on the same band.

### 5.3 Impulse Event Rate per Band

Extracted from: FT-710 AM audio recordings, count of detected events per unit time, separately for day and night recordings.

Used for: Band selection. The band with the highest and most consistent natural impulse event rate provides the most credible cover for synthetic burst events. A band where natural impulses are rare makes each additional event statistically anomalous. Comparing event rates across all recorded bands produces a ranking that directly informs the operating frequency decision.

### 5.4 Spectral Shape of Impulse Events

Extracted from: B210 IQ recordings via short-time Fourier transform of detected impulse windows, averaged across events.

Used for: Designing the spectral shaping filter applied before the AD9361 DAC chain. The AD9361 has a steep clean roll-off that does not match the softer spectral skirt of natural atmospheric impulse noise. A GNU Radio shaping filter must be inserted to match the synthetic burst's spectral envelope to the measured natural noise spectral shape. Without this the burst may pass amplitude and timing scrutiny but fail spectral analysis.

### 5.5 Impulse Rise and Fall Times

Extracted from: B210 IQ recordings for precision measurement. FT-710 audio recordings at 48 kHz for approximate validation.

Used for: Setting the rise_fraction parameter in gaussian_envelope in python/sync_burst_utils.py. The current default of 0.1 is an estimate. The measured rise and fall times from real impulse events on the operating band replace this with an empirically grounded value. A synthetic burst with a rise profile that does not match the natural noise distribution on that band is a detectable artefact.

### 5.6 Day versus Night Variation

Extracted from: Comparison of day and night recordings across all bands.

Used for: Assessing whether a single static set of distribution parameters is sufficient or whether the burst schedule needs to adapt its statistical character between day and night operation. If day and night noise statistics differ significantly on the chosen operating band, the schedule derivation may need two parameter sets indexed by time of day, both derivable from key material.

### 5.7 Band Suitability Assessment

Extracted from: The full dataset across all bands and times.

Used for: The primary band selection decision. Bands are ranked by natural impulse event rate, consistency of statistics between day and night, spectral match achievability, and amplitude distribution shape. The band that scores best across all four criteria becomes the candidate operating frequency. Bands where the atmospheric impulse mimicry model breaks down — broadly above 20m — are flagged as requiring a different covertness strategy if operation there is required.

---

## 6. Analysis Workflow

### 6.1 Impulse Event Detection

Load each WAV file into a processing environment such as Python with SciPy and NumPy. Apply a short-time energy detector: compute the RMS energy in a sliding window and threshold above the estimated noise floor. A threshold of 3 to 4 standard deviations above the median background energy level is a practical starting point. Each threshold crossing that exceeds a minimum duration and then falls back below threshold is counted as one impulse event. Record the timestamp, peak amplitude, and duration of each detected event.

Inspect detections manually on a sample of recordings to verify the detector is capturing genuine impulse events rather than man-made carriers or receiver artefacts.

### 6.2 Inter-Arrival Time Analysis

From the timestamped event list, compute the time between consecutive events. Plot the inter-arrival time histogram. Fit candidate distributions — exponential, Pareto, log-normal — using maximum likelihood estimation. Apply a Kolmogorov-Smirnov test to assess goodness of fit for each candidate. The best-fitting distribution and its parameters become the model used in the schedule quantile transform.

Perform this analysis separately for day and night recordings on each band. If the day and night distributions differ significantly by KS test, note this for the band suitability assessment.

### 6.3 Amplitude Distribution Analysis

From the peak amplitude of each detected event, plot the amplitude histogram in log scale. Fit a log-normal distribution using maximum likelihood estimation. Record the fitted mean and standard deviation in log space. These parameters directly initialise the per-burst amplitude jitter model.

### 6.4 Spectral Shape Analysis

From B210 IQ recordings, extract windows centred on each detected impulse event. Apply a short-time Fourier transform to each window with a Hann or Gaussian taper. Average the magnitude spectra across all detected events to produce a mean spectral envelope. This envelope is the target for the GNU Radio spectral shaping filter design.

Compare the measured spectral envelope to the spectrum of an unfiltered PN-spread burst at the same chip rate. The difference between the two defines the shaping filter response needed to make the synthetic burst spectrally match the natural noise.

### 6.5 Rise and Fall Time Analysis

From B210 IQ recordings, compute the instantaneous amplitude envelope of each detected impulse event using the Hilbert transform. Measure the time from 10 percent to 90 percent of peak amplitude on the rising edge, and from 90 percent to 10 percent on the falling edge. Average these across all detected events. Convert the mean rise time to a fraction of the 2 ms burst duration to obtain the empirical rise_fraction value.

### 6.6 Band Comparison and Selection

Tabulate per band: mean impulse event rate for day and night recordings, best-fit inter-arrival distribution and parameters, log-normal amplitude distribution parameters, spectral shape achievability, and day/night statistical stability. Plot event rates across bands on a single chart to make the comparison visually clear. The operating band selection follows directly from this table.

---

## 7. Output Deliverables from the Analysis

The analysis of the baseline recordings should produce the following concrete outputs that feed directly into the KGDSS implementation.

- Per-band impulse event rate table, day and night
- Inter-arrival time distribution type and parameters per band
- Log-normal amplitude distribution parameters per band
- Empirical rise_fraction value for the gaussian_envelope function
- Target spectral envelope for the GNU Radio shaping filter
- Band suitability ranking with recommendation for operating frequency
- Flag indicating whether day/night adaptive parameters are needed
