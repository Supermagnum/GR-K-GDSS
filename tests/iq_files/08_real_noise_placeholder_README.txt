Real noise recording instructions for gr-k-gdss IQ test files.

Sample rate: 500 kHz
Duration: minimum 10 seconds
Format: complex float32 (interleaved I,Q), same as other test files.
Connection: Antenna -> SDR Source -> File Sink. Save as 08_real_noise_reference.cf32 (or use
 08_real_noise_with_hardware_artifacts.cf32 from the project sdr-noise folder as baseline).
No transmission during recording.
Compare against Files 1 and 3 using analyse_iq_files.py.

Optional baseline with hardware artifacts (SDR recording):
  Copy from: PROJECTS_DIR/GR-K-GDSS/sdr-noise/08_real_noise_with_hardware_artifacts.cf32
  to this directory (iq_files/) as 08_real_noise_with_hardware_artifacts.cf32.
  Then analyse_iq_files.py will run the same noise tests on File 8.
