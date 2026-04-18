/*
 * Keyed GDSS Despreader implementation
 *
 * Despreads keyed GDSS complex samples and recovers symbols. Uses the same
 * ChaCha20 key and nonce as the spreader to regenerate the Gaussian mask,
 * then applies matched-filter despreading (chip * conj(mask)) to suppress
 * inter-symbol interference under multipath fading.
 *
 * Algorithm:
 *   - Keystream and Box-Muller match the spreader (8 bytes per chip -> mask I,Q).
 *   - Despread (matched filter): raw_sym = sum(chip * conj(mask)) / sum(|mask|^2).
 *     This converts ISI from Cauchy-distributed (ZF) to Gaussian-distributed (MF),
 *     which averages toward zero over chips_per_symbol chips.
 *   - Channel equalization: decision-directed complex channel estimation.
 *     raw_sym ~ h_eff * sym; decision = sign(Re(raw_sym * conj(h_est)));
 *     h_est updated with IIR: h_est = (1-a)*h_est + a*raw_sym*decision.
 *     Output equalized symbol = raw_sym * conj(h_est) / |h_est|^2.
 *   - Correlation: inner product sample * conj(sequence_chip) for lock and timing.
 *   - Timing loop: normalized S-curve discriminant with fractional accumulator
 *     and adaptive gain proportional to lock quality.
 *   - Lock: adaptive threshold (ADAPTIVE_THRESHOLD_MIN 0.2) and LOCK_THRESHOLD
 *     consecutive high correlations set is_locked; output ports 1 (lock 0/1) and
 *     2 (SNR estimate dB) are updated each symbol.
 *
 * Key/nonce: set at construction or via set_key message port (PMT dict "key"/"nonce").
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <gnuradio/kgdss/kgdss_despreader_cc.h>
#include "chacha_ietf_keystream.h"
#include "kgdss_despreader_cc_impl.h"
#include <gnuradio/io_signature.h>
#include <pmt/pmt.h>
#include <cmath>
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <stdexcept>

namespace gr {
namespace kgdss {

/* Minimum correlation (relative to peak) to consider "locked". */
const float kgdss_despreader_cc_impl::ADAPTIVE_THRESHOLD_MIN = 0.2f;
/* Number of phase bins in acquisition for coarse code-phase search. */
const int kgdss_despreader_cc_impl::COARSE_SEARCH_BINS = 32;

kgdss_despreader_cc::~kgdss_despreader_cc() {}

void kgdss_despreader_cc::set_spreading_sequence(const std::vector<float>& spreading_sequence)
{
    (void)spreading_sequence;
}

void kgdss_despreader_cc::set_chips_per_symbol(int chips_per_symbol)
{
    (void)chips_per_symbol;
}

kgdss_despreader_cc::sync_state kgdss_despreader_cc::get_sync_state() const
{
    return STATE_ACQUISITION;
}

bool kgdss_despreader_cc::is_locked() const
{
    return false;
}

float kgdss_despreader_cc::get_snr_estimate() const
{
    return 0.0f;
}

float kgdss_despreader_cc::get_last_soft_metric() const
{
    return 0.0f;
}

float kgdss_despreader_cc::get_frequency_error() const
{
    return 0.0f;
}

void kgdss_despreader_cc::set_counter(uint64_t counter)
{
    (void)counter;
}

bool kgdss_despreader_cc::get_overflow_occurred() const
{
    return false;
}

void kgdss_despreader_cc::set_channel_equalization(bool enable)
{
    (void)enable;
}

bool kgdss_despreader_cc::get_channel_equalization() const
{
    return false;
}

kgdss_despreader_cc::sptr kgdss_despreader_cc::make(
    const std::vector<float>& spreading_sequence,
    int chips_per_symbol,
    float correlation_threshold,
    int timing_error_tolerance,
    const std::vector<uint8_t>& chacha_key,
    const std::vector<uint8_t>& chacha_nonce)
{
    return gnuradio::get_initial_sptr(
        new kgdss_despreader_cc_impl(spreading_sequence,
                                     chips_per_symbol,
                                     correlation_threshold,
                                     timing_error_tolerance,
                                     chacha_key,
                                     chacha_nonce));
}

kgdss_despreader_cc_impl::kgdss_despreader_cc_impl(
    const std::vector<float>& spreading_sequence,
    int chips_per_symbol,
    float correlation_threshold,
    int timing_error_tolerance,
    const std::vector<uint8_t>& chacha_key,
    const std::vector<uint8_t>& chacha_nonce)
    : kgdss_despreader_cc("kgdss_despreader_cc",
                          gr::io_signature::make(1, 1, sizeof(gr_complex)),
                          gr::io_signature::makev(
                              3, 3, std::vector<int>{ sizeof(gr_complex), sizeof(float), sizeof(float) }),
                          spreading_sequence,
                          chips_per_symbol,
                          correlation_threshold,
                          timing_error_tolerance),
      d_sequence_length(static_cast<int>(spreading_sequence.size()) % 2 == 0
                            ? static_cast<int>(spreading_sequence.size()) / 2
                            : static_cast<int>(spreading_sequence.size())),
      d_chips_per_symbol(chips_per_symbol),
      d_correlation_threshold(correlation_threshold),
      d_timing_error_tolerance(timing_error_tolerance),
      d_state(STATE_ACQUISITION),
      d_code_phase(0),
      d_timing_offset(0),
      d_acquisition_counter(0),
      d_lock_counter(0),
      d_early_correlation(0.0f),
      d_prompt_correlation(0.0f),
      d_late_correlation(0.0f),
      d_timing_error(0.0f),
      d_timing_accum(0.0f),
      d_correlation_peak(0.0f),
      d_correlation_avg(0.0f),
      d_is_locked(false),
      d_signal_power(0.0f),
      d_noise_power(0.0f),
      d_snr_db(0.0f),
      d_last_soft_metric(0.0f),
      d_channel_est(1.0f, 0.0f),
      d_channel_eq_enabled(false),
      d_freq_error_rad_per_sym(0.0f),
      d_prev_corr_phase(0.0f),
      d_have_prev_corr(false),
      d_key(chacha_key),
      d_nonce(chacha_nonce),
      d_counter(0),
      d_key_set(chacha_key.size() == 32 && chacha_nonce.size() == 12),
      d_ks_remainder_len(0)
{
    if (d_sequence_length == 0) {
        throw std::invalid_argument("Spreading sequence cannot be empty");
    }
    if (d_chips_per_symbol <= 0) {
        throw std::invalid_argument("Chips per symbol must be positive");
    }
    if (!chacha_key.empty() && chacha_key.size() != 32) {
        throw std::invalid_argument("ChaCha20 key must be 0 or 32 bytes");
    }
    if (!chacha_nonce.empty() && chacha_nonce.size() != 12) {
        throw std::invalid_argument("ChaCha20 nonce must be 0 or 12 bytes");
    }

    if (sodium_init() < 0) {
        throw std::runtime_error("libsodium initialization failed");
    }

    build_sequence_complex(spreading_sequence);
    d_input_buffer.clear();

    message_port_register_in(pmt::mp("set_key"));
    set_msg_handler(pmt::mp("set_key"),
                    [this](pmt::pmt_t msg) { this->handle_key_msg(msg); });
    message_port_register_in(pmt::mp("set_counter"));
    set_msg_handler(pmt::mp("set_counter"),
                    [this](pmt::pmt_t msg) { this->handle_counter_msg(msg); });
}

kgdss_despreader_cc_impl::~kgdss_despreader_cc_impl() {}

void kgdss_despreader_cc_impl::handle_key_msg(pmt::pmt_t msg)
{
    if (!pmt::is_dict(msg)) return;
    pmt::pmt_t key_val = pmt::dict_ref(msg, pmt::mp("key"), pmt::PMT_NIL);
    pmt::pmt_t nonce_val = pmt::dict_ref(msg, pmt::mp("nonce"), pmt::PMT_NIL);
    if (!pmt::is_u8vector(key_val) || !pmt::is_u8vector(nonce_val)) return;
    size_t key_len = pmt::length(key_val);
    size_t nonce_len = pmt::length(nonce_val);
    if (key_len != 32 || nonce_len != 12) return;
    const uint8_t* k = (const uint8_t*)pmt::uniform_vector_elements(key_val, key_len);
    const uint8_t* n = (const uint8_t*)pmt::uniform_vector_elements(nonce_val, nonce_len);
    if (!k || !n) return;
    std::unique_lock<std::mutex> lock(d_key_mutex);
    d_key.assign(k, k + 32);
    d_nonce.assign(n, n + 12);
    d_counter = 0;
    d_ks_remainder_len = 0;
    d_key_set = true;
    d_overflow_occurred.store(false);
    {
        std::lock_guard<std::mutex> state_lock(d_mutex);
        d_state = STATE_ACQUISITION;
        d_code_phase = 0;
        d_lock_counter = 0;
        d_is_locked = false;
        d_have_prev_corr = false;
        d_freq_error_rad_per_sym = 0.0f;
        d_acquisition_counter = 0;
        d_timing_accum = 0.0f;
        d_channel_est = gr_complex(1.0f, 0.0f);
    }
}

void kgdss_despreader_cc_impl::handle_counter_msg(pmt::pmt_t msg)
{
    uint64_t ctr = 0;
    if (pmt::is_uint64(msg)) {
        ctr = pmt::to_uint64(msg);
    } else if (pmt::is_integer(msg)) {
        const long val = pmt::to_long(msg);
        if (val < 0) return;
        ctr = static_cast<uint64_t>(val);
    } else {
        return;
    }
    std::unique_lock<std::mutex> lock(d_key_mutex);
    d_counter = ctr;
    d_ks_remainder_len = 0;
}

void kgdss_despreader_cc_impl::build_sequence_complex(const std::vector<float>& spreading_sequence)
{
    d_spreading_sequence_complex.resize(d_sequence_length);
    if (spreading_sequence.size() == static_cast<size_t>(2 * d_sequence_length)) {
        for (int i = 0; i < d_sequence_length; i++) {
            d_spreading_sequence_complex[i] =
                gr_complex(spreading_sequence[2 * i], spreading_sequence[2 * i + 1]);
        }
    } else {
        for (int i = 0; i < d_sequence_length; i++) {
            d_spreading_sequence_complex[i] =
                gr_complex(std::abs(spreading_sequence[i]), 0.0f);
        }
    }
}

void kgdss_despreader_cc_impl::forecast(int noutput_items, gr_vector_int& ninput_items_required)
{
    ninput_items_required[0] = noutput_items * d_chips_per_symbol;
}

gr_complex kgdss_despreader_cc_impl::correlate(const gr_complex* samples, int offset, int length)
{
    gr_complex sum(0.0f, 0.0f);
    int n = std::min(length, d_sequence_length);

    for (int i = 0; i < n; i++) {
        int seq_idx = (d_code_phase + i) % d_sequence_length;
        gr_complex s = samples[offset + i];
        const gr_complex seq = d_spreading_sequence_complex[seq_idx];
        sum += s * std::conj(seq);
    }

    if (n > 0) {
        sum /= static_cast<float>(n);
    }
    return sum;
}

void kgdss_despreader_cc_impl::update_timing(float prompt_mf_power)
{
    if (d_chips_per_symbol <= 1) {
        d_timing_error = 0.0f;
        d_timing_offset = 0;
        d_timing_accum = 0.0f;
        return;
    }

    // MF-power peak tracking is only meaningful when a channel estimator can
    // correct the phase of the selected tap; without equalization, converging
    // to the power peak can expose a sign-inverting channel phase that flips
    // all BPSK decisions. Keep timing at the nominal input offset in that
    // case so behaviour stays agnostic to channel phase.
    if (!d_channel_eq_enabled) {
        d_timing_error = 0.0f;
        d_timing_accum = 0.0f;
        d_timing_offset = 0;
        return;
    }

    // MF-power peak tracking. In a multipath channel the symmetric early-late
    // S-curve is biased by asymmetric precursor/postcursor sidelobes; the
    // correct timing is the power peak, not the S-curve zero. We therefore
    // vote for the direction whose cumulative neighbor power strictly exceeds
    // the prompt, using a hysteresis margin to avoid noise-driven ping-pong.
    // d_early_correlation / d_late_correlation are the combined MF powers at
    // despread_offset-{1..tol} and despread_offset+{1..tol}.
    const float HYSTERESIS = 1.15f;
    const float GAIN = 0.35f;
    const int tol = std::min(3, d_timing_error_tolerance);

    float vote = 0.0f;
    // Prompt reference scales with number of offsets summed into each side.
    float prompt_ref = static_cast<float>(tol) * prompt_mf_power;
    if (d_late_correlation > HYSTERESIS * prompt_ref &&
        d_late_correlation > d_early_correlation) {
        vote = +1.0f;
    } else if (d_early_correlation > HYSTERESIS * prompt_ref &&
               d_early_correlation > d_late_correlation) {
        vote = -1.0f;
    }

    d_timing_error = 0.7f * d_timing_error + 0.3f * vote;
    d_timing_accum += d_timing_error * GAIN;
    if (d_timing_accum > 0.5f) {
        d_timing_offset = std::min(d_timing_error_tolerance, d_timing_offset + 1);
        d_timing_accum -= 1.0f;
    } else if (d_timing_accum < -0.5f) {
        d_timing_offset = std::max(-d_timing_error_tolerance, d_timing_offset - 1);
        d_timing_accum += 1.0f;
    }
}

/* Update lock state: compare correlation magnitude to an adaptive threshold
 * (function of correlation_threshold and ratio of current average to peak).
 * Lock is declared after LOCK_THRESHOLD consecutive passes; one fail decrements. */
void kgdss_despreader_cc_impl::update_lock_detection(float correlation)
{
    float corr_mag = std::abs(correlation);

    d_correlation_avg = 0.9f * d_correlation_avg + 0.1f * corr_mag;

    if (corr_mag > d_correlation_peak) {
        d_correlation_peak = corr_mag;
    }

    float peak = std::max(d_correlation_peak, 1e-3f);
    float rel = d_correlation_avg / peak;
    float adaptive = std::max(ADAPTIVE_THRESHOLD_MIN, d_correlation_threshold * rel);

    if (corr_mag > adaptive) {
        d_lock_counter++;
        if (d_lock_counter >= LOCK_THRESHOLD) {
            d_is_locked = true;
            if (d_state == STATE_ACQUISITION) {
                d_state = STATE_TRACKING;
            }
            if (d_state == STATE_TRACKING && d_lock_counter >= LOCK_THRESHOLD * 2) {
                d_state = STATE_LOCKED;
            }
        }
    } else {
        d_lock_counter = std::max(0, d_lock_counter - 1);
        if (d_lock_counter == 0 && d_state == STATE_LOCKED) {
            d_state = STATE_TRACKING;
            d_is_locked = false;
        }
    }
}

void kgdss_despreader_cc_impl::update_snr_estimate(gr_complex symbol, float correlation)
{
    float symbol_power = std::norm(symbol);
    float corr_mag = std::abs(correlation);

    d_signal_power = 0.95f * d_signal_power + 0.05f * corr_mag * corr_mag;

    float noise_est = std::max(0.0f, symbol_power - d_signal_power);
    d_noise_power = 0.95f * d_noise_power + 0.05f * noise_est;

    if (d_noise_power > 0.0f) {
        d_snr_db = 10.0f * std::log10(d_signal_power / d_noise_power);
    } else {
        d_snr_db = 100.0f;
    }
}

/* Decision-directed channel equalization (BPSK assumption).
 * raw_sym ~ h_eff * data_sym where h_eff is the effective fading channel gain
 * and data_sym is assumed to be BPSK (+-1 real). A BPSK decision preserves
 * the sign, so raw_sym * decision tracks h_eff in both amplitude and phase.
 *
 * The estimate is only updated when |raw_sym|^2 is large enough to indicate the
 * MF is chip-aligned; updating on misaligned noise would pull h_est toward a
 * random direction and cause a 180 degree phase inversion that never recovers.
 *
 * Disabled by default (pass-through). Callers that know they have BPSK data
 * and want fading correction enable it with set_channel_equalization(true). */
gr_complex kgdss_despreader_cc_impl::apply_channel_equalization(gr_complex raw_sym)
{
    if (!d_channel_eq_enabled) {
        return raw_sym;
    }

    const float ALPHA = 0.05f;
    const float POWER_GATE = 0.25f;

    float h_mag_sq = std::norm(d_channel_est);
    gr_complex out_sym;
    if (h_mag_sq > 1e-10f) {
        out_sym = raw_sym * std::conj(d_channel_est) / h_mag_sq;
    } else {
        out_sym = raw_sym;
    }

    // Only update when raw MF output has BPSK-like power. Misaligned-timing
    // output has power ~1/n_chips which is much smaller than aligned output.
    if (std::norm(raw_sym) > POWER_GATE) {
        float decision = (out_sym.real() >= 0.0f) ? 1.0f : -1.0f;
        d_channel_est = d_channel_est * (1.0f - ALPHA) + raw_sym * (decision * ALPHA);
    }

    return out_sym;
}

void kgdss_despreader_cc_impl::set_channel_equalization(bool enable)
{
    std::lock_guard<std::mutex> lock(d_mutex);
    d_channel_eq_enabled = enable;
    d_channel_est = gr_complex(1.0f, 0.0f);
}

bool kgdss_despreader_cc_impl::get_channel_equalization() const
{
    std::lock_guard<std::mutex> lock(d_mutex);
    return d_channel_eq_enabled;
}

void kgdss_despreader_cc_impl::set_spreading_sequence(const std::vector<float>& spreading_sequence)
{
    std::lock_guard<std::mutex> lock(d_mutex);
    if (spreading_sequence.empty()) {
        throw std::invalid_argument("Spreading sequence cannot be empty");
    }
    d_sequence_length = (spreading_sequence.size() % 2 == 0)
                            ? static_cast<int>(spreading_sequence.size()) / 2
                            : static_cast<int>(spreading_sequence.size());
    build_sequence_complex(spreading_sequence);

    d_code_phase = 0;
    d_state = STATE_ACQUISITION;
    d_lock_counter = 0;
    d_is_locked = false;
    d_have_prev_corr = false;
    d_freq_error_rad_per_sym = 0.0f;
    d_last_soft_metric = 0.0f;
    d_timing_accum = 0.0f;
    d_channel_est = gr_complex(1.0f, 0.0f);
}

void kgdss_despreader_cc_impl::set_chips_per_symbol(int chips_per_symbol)
{
    std::lock_guard<std::mutex> lock(d_mutex);
    if (chips_per_symbol <= 0) {
        throw std::invalid_argument("Chips per symbol must be positive");
    }
    d_chips_per_symbol = chips_per_symbol;
}

kgdss_despreader_cc::sync_state kgdss_despreader_cc_impl::get_sync_state() const
{
    std::lock_guard<std::mutex> lock(d_mutex);
    return d_state;
}

bool kgdss_despreader_cc_impl::is_locked() const
{
    std::lock_guard<std::mutex> lock(d_mutex);
    return d_is_locked;
}

float kgdss_despreader_cc_impl::get_snr_estimate() const
{
    std::lock_guard<std::mutex> lock(d_mutex);
    return d_snr_db;
}

float kgdss_despreader_cc_impl::get_last_soft_metric() const
{
    std::lock_guard<std::mutex> lock(d_mutex);
    return d_last_soft_metric;
}

float kgdss_despreader_cc_impl::get_frequency_error() const
{
    std::lock_guard<std::mutex> lock(d_mutex);
    return d_freq_error_rad_per_sym;
}

void kgdss_despreader_cc_impl::set_counter(uint64_t counter)
{
    std::unique_lock<std::mutex> lock(d_key_mutex);
    d_counter = counter;
    d_ks_remainder_len = 0;
}

bool kgdss_despreader_cc_impl::get_overflow_occurred() const
{
    return d_overflow_occurred.load();
}

/* Box-Muller: same formula as spreader but without variance scaling.
 * For MF despreading: sum(chip*conj(mask))/sum(|mask|^2). When spreader uses
 * the same keystream scaled by sqrt(variance), both numerator and denominator
 * scale by variance, so the output is independent of variance. */
void kgdss_despreader_cc_impl::box_muller_pair(float u1, float u2, float& g0, float& g1)
{
    if (u1 < 1e-10f) {
        u1 = 1e-10f;
    }
    const float radius = std::sqrt(-2.0f * std::log(u1));
    const float angle = 2.0f * static_cast<float>(M_PI) * u2;
    g0 = radius * std::cos(angle);
    g1 = radius * std::sin(angle);
}

int kgdss_despreader_cc_impl::general_work(int noutput_items,
                                          gr_vector_int& ninput_items,
                                          gr_vector_const_void_star& input_items,
                                          gr_vector_void_star& output_items)
{
    const gr_complex* in = (const gr_complex*)input_items[0];
    gr_complex* out_symbols = (gr_complex*)output_items[0];
    float* out_lock = (float*)output_items[1];
    float* out_snr = (float*)output_items[2];

    int ninput_items_available = ninput_items[0];
    int ninput_items_needed = noutput_items * d_chips_per_symbol;
    int ninput_items_used = std::min(ninput_items_available, ninput_items_needed);
    int actual_output_items = ninput_items_used / d_chips_per_symbol;

    {
        std::unique_lock<std::mutex> key_lock(d_key_mutex);
        if (!d_key_set) return 0;
    }

    const float MIN_MASK = 1e-4f;
    auto to_uniform = [](const uint8_t* b) -> float {
        const uint32_t v = static_cast<uint32_t>(b[0]) |
                           (static_cast<uint32_t>(b[1]) << 8) |
                           (static_cast<uint32_t>(b[2]) << 16) |
                           (static_cast<uint32_t>(b[3]) << 24);
        return (static_cast<float>(v) + 0.5f) / 4294967296.0f;
    };

    int output_idx = 0;
    for (int sym = 0; sym < actual_output_items; sym++) {
        int input_offset = sym * d_chips_per_symbol;

        if (input_offset + d_chips_per_symbol > ninput_items_used) {
            break;
        }

        const size_t ks_len = static_cast<size_t>(d_chips_per_symbol) * 8;

        std::array<uint8_t, 32> key_snap{};
        std::array<uint8_t, 12> nonce_snap{};
        uint64_t ctr_snap = 0;
        std::array<uint8_t, 64> rem_snap{};
        size_t rem_len_snap = 0;
        bool key_ok = false;
        {
            std::lock_guard<std::mutex> kl(d_key_mutex);
            key_ok = d_key_set;
            if (key_ok) {
                std::memcpy(key_snap.data(), d_key.data(), 32);
                std::memcpy(nonce_snap.data(), d_nonce.data(), 12);
                ctr_snap = d_counter;
                rem_len_snap = d_ks_remainder_len;
                if (rem_len_snap > 0) {
                    std::memcpy(rem_snap.data(), d_ks_remainder.data(), rem_len_snap);
                }
            }
        }

        if (!key_ok) break;

        if (ks_len > 0) {
            const uint64_t last_byte = ctr_snap + ks_len - 1ULL;
            const uint64_t last_block = last_byte / 64ULL;
            assert(last_block <= static_cast<uint64_t>(UINT32_MAX));
            if (last_block > static_cast<uint64_t>(UINT32_MAX)) {
                d_overflow_occurred.store(true);
                return WORK_DONE;
            }
        }

        if (ks_len > d_ks_buf.size()) {
            d_ks_buf.resize(ks_len);
        }

        detail::produce_chacha_ietf_keystream(d_ks_buf.data(),
                                              ks_len,
                                              key_snap.data(),
                                              nonce_snap.data(),
                                              ctr_snap,
                                              rem_snap,
                                              rem_len_snap);

        bool committed = false;
        {
            std::lock_guard<std::mutex> kl(d_key_mutex);
            if (d_key_set && d_key.size() == 32 && d_nonce.size() == 12 &&
                std::memcmp(d_key.data(), key_snap.data(), 32) == 0 &&
                std::memcmp(d_nonce.data(), nonce_snap.data(), 12) == 0) {
                d_counter = ctr_snap;
                d_ks_remainder_len = rem_len_snap;
                if (rem_len_snap > 0) {
                    std::memcpy(d_ks_remainder.data(), rem_snap.data(), rem_len_snap);
                }
                committed = true;
            }
        }

        const uint8_t* ks = d_ks_buf.data();

        if (!committed) break;

        std::lock_guard<std::mutex> lock(d_mutex);

        if (d_state == STATE_ACQUISITION) {
            int step = std::max(1, d_sequence_length / COARSE_SEARCH_BINS);
            float best_correlation = 0.0f;
            int best_phase = d_code_phase;

            for (int phase = 0; phase < d_sequence_length; phase += step) {
                d_code_phase = phase;
                gr_complex corr = correlate(in, input_offset, d_chips_per_symbol);
                float corr_mag = std::abs(corr);
                if (corr_mag > best_correlation) {
                    best_correlation = corr_mag;
                    best_phase = phase;
                }
            }
            int start = std::max(0, best_phase - step);
            int stop = std::min(d_sequence_length, best_phase + step + 1);
            for (int phase = start; phase < stop; phase++) {
                d_code_phase = phase;
                gr_complex corr = correlate(in, input_offset, d_chips_per_symbol);
                float corr_mag = std::abs(corr);
                if (corr_mag > best_correlation) {
                    best_correlation = corr_mag;
                    best_phase = phase;
                }
            }

            d_code_phase = best_phase;
            d_prompt_correlation = best_correlation;
            update_lock_detection(best_correlation);

            d_acquisition_counter++;
            if (d_acquisition_counter > ACQUISITION_TIMEOUT) {
                d_acquisition_counter = 0;
            }

            gr_complex despread = correlate(in, input_offset, d_chips_per_symbol);

            float sum_i = 0.0f;
            float sum_q = 0.0f;
            float mask_sq_sum = 0.0f;
            const int n_chips = std::min(d_chips_per_symbol, d_sequence_length);
            for (int chip = 0; chip < n_chips; chip++) {
                const uint8_t* base = ks + static_cast<size_t>(chip) * 8;
                float mask_i = 0.0f;
                float mask_q = 0.0f;
                box_muller_pair(to_uniform(base + 0), to_uniform(base + 4), mask_i, mask_q);
                if (std::abs(mask_i) < MIN_MASK) mask_i = (mask_i >= 0 ? MIN_MASK : -MIN_MASK);
                if (std::abs(mask_q) < MIN_MASK) mask_q = (mask_q >= 0 ? MIN_MASK : -MIN_MASK);
                const float s_re = in[input_offset + chip].real();
                const float s_im = in[input_offset + chip].imag();
                sum_i += s_re * mask_i + s_im * mask_q;
                sum_q += s_im * mask_i - s_re * mask_q;
                mask_sq_sum += mask_i * mask_i + mask_q * mask_q;
            }
            {
                const float norm = std::max(mask_sq_sum, 1e-6f);
                gr_complex raw_sym = gr_complex(sum_i / norm, sum_q / norm);
                out_symbols[output_idx] = apply_channel_equalization(raw_sym);
            }

            float peak = std::max(d_correlation_peak, 1e-6f);
            d_last_soft_metric = best_correlation / peak;

            float phase = std::arg(despread);
            if (d_have_prev_corr) {
                float dphi = phase - d_prev_corr_phase;
                if (dphi > 3.14159265f) dphi -= 6.28318531f;
                if (dphi < -3.14159265f) dphi += 6.28318531f;
                d_freq_error_rad_per_sym = 0.9f * d_freq_error_rad_per_sym + 0.1f * dphi;
            } else {
                d_have_prev_corr = true;
            }
            d_prev_corr_phase = phase;

        } else {
            int max_offset = ninput_items_used - d_chips_per_symbol;
            if (max_offset < 0) {
                break;
            }

            int despread_offset = std::max(0, std::min(max_offset, input_offset + d_timing_offset));

            // Sequence correlation for lock detection and SNR only (not timing).
            d_prompt_correlation = std::abs(correlate(in, input_offset, d_chips_per_symbol));
            gr_complex despread = correlate(in, despread_offset, d_chips_per_symbol);

            // MF despreading with early/late MF powers for timing discriminant.
            // The sequence correlation is random for GDSS mask-only spreading, so
            // early/late correlations cannot detect chip timing. MF power at an
            // offset is non-zero only when that offset aligns mask with chips.
            // MF powers at offsets [-tol .. +tol] are computed to handle chip
            // timing offsets up to the configured tolerance.
            const int tol = std::min(3, d_timing_error_tolerance);
            int mf_e[3], mf_l[3];
            float e_i[3] = {0.0f, 0.0f, 0.0f}, e_q[3] = {0.0f, 0.0f, 0.0f};
            float l_i[3] = {0.0f, 0.0f, 0.0f}, l_q[3] = {0.0f, 0.0f, 0.0f};
            for (int i = 0; i < tol; i++) {
                mf_e[i] = std::max(0, despread_offset - (i + 1));
                mf_l[i] = std::min(max_offset, despread_offset + (i + 1));
            }

            float sum_i = 0.0f, sum_q = 0.0f;
            float mask_sq_sum = 0.0f;
            const int n_chips = std::min(d_chips_per_symbol, d_sequence_length);
            for (int chip = 0; chip < n_chips; chip++) {
                const uint8_t* base = ks + static_cast<size_t>(chip) * 8;
                float mask_i = 0.0f;
                float mask_q = 0.0f;
                box_muller_pair(to_uniform(base + 0), to_uniform(base + 4), mask_i, mask_q);
                if (std::abs(mask_i) < MIN_MASK) mask_i = (mask_i >= 0 ? MIN_MASK : -MIN_MASK);
                if (std::abs(mask_q) < MIN_MASK) mask_q = (mask_q >= 0 ? MIN_MASK : -MIN_MASK);

                const float s_re = in[despread_offset + chip].real();
                const float s_im = in[despread_offset + chip].imag();
                sum_i += s_re * mask_i + s_im * mask_q;
                sum_q += s_im * mask_i - s_re * mask_q;

                for (int i = 0; i < tol; i++) {
                    const float er = in[mf_e[i] + chip].real();
                    const float em = in[mf_e[i] + chip].imag();
                    e_i[i] += er * mask_i + em * mask_q;
                    e_q[i] += em * mask_i - er * mask_q;

                    const float lr = in[mf_l[i] + chip].real();
                    const float lm = in[mf_l[i] + chip].imag();
                    l_i[i] += lr * mask_i + lm * mask_q;
                    l_q[i] += lm * mask_i - lr * mask_q;
                }

                mask_sq_sum += mask_i * mask_i + mask_q * mask_q;
            }
            float prompt_mf_power;
            {
                const float norm_sq = std::max(mask_sq_sum * mask_sq_sum, 1e-12f);
                // Combined early/late MF powers across offsets up to tolerance.
                float ep_sum = 0.0f, lp_sum = 0.0f;
                for (int i = 0; i < tol; i++) {
                    ep_sum += (e_i[i] * e_i[i] + e_q[i] * e_q[i]) / norm_sq;
                    lp_sum += (l_i[i] * l_i[i] + l_q[i] * l_q[i]) / norm_sq;
                }
                d_early_correlation = ep_sum;
                d_late_correlation  = lp_sum;
                prompt_mf_power     = (sum_i * sum_i + sum_q * sum_q) / norm_sq;
            }
            update_timing(prompt_mf_power);

            {
                const float norm = std::max(mask_sq_sum, 1e-6f);
                gr_complex raw_sym = gr_complex(sum_i / norm, sum_q / norm);
                out_symbols[output_idx] = apply_channel_equalization(raw_sym);
            }

            update_lock_detection(d_prompt_correlation);
            update_snr_estimate(despread, d_prompt_correlation);

            float peak = std::max(d_correlation_peak, 1e-6f);
            d_last_soft_metric = d_prompt_correlation / peak;

            float phase = std::arg(despread);
            if (d_have_prev_corr) {
                float dphi = phase - d_prev_corr_phase;
                if (dphi > 3.14159265f) dphi -= 6.28318531f;
                if (dphi < -3.14159265f) dphi += 6.28318531f;
                d_freq_error_rad_per_sym = 0.9f * d_freq_error_rad_per_sym + 0.1f * dphi;
            } else {
                d_have_prev_corr = true;
            }
            d_prev_corr_phase = phase;

            d_code_phase = (d_code_phase + d_chips_per_symbol) % d_sequence_length;
        }

        out_lock[output_idx] = d_is_locked ? 1.0f : 0.0f;
        out_snr[output_idx] = d_snr_db;

        output_idx++;
    }

    consume(0, output_idx * d_chips_per_symbol);

    return output_idx;
}

} // namespace kgdss
} // namespace gr

