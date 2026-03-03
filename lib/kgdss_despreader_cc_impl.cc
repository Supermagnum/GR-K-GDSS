/*
 * Keyed GDSS Despreader implementation
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <gnuradio/kgdss/kgdss_despreader_cc.h>
#include "kgdss_despreader_cc_impl.h"
#include <gnuradio/io_signature.h>
#include <cmath>
#include <algorithm>
#include <cstring>
#include <stdexcept>

namespace gr {
namespace kgdss {

const float kgdss_despreader_cc_impl::ADAPTIVE_THRESHOLD_MIN = 0.2f;
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
      d_correlation_peak(0.0f),
      d_correlation_avg(0.0f),
      d_is_locked(false),
      d_signal_power(0.0f),
      d_noise_power(0.0f),
      d_snr_db(0.0f),
      d_last_soft_metric(0.0f),
      d_freq_error_rad_per_sym(0.0f),
      d_prev_corr_phase(0.0f),
      d_have_prev_corr(false),
      d_key(chacha_key),
      d_nonce(chacha_nonce),
      d_counter(0)
{
    if (d_sequence_length == 0) {
        throw std::invalid_argument("Spreading sequence cannot be empty");
    }
    if (d_chips_per_symbol <= 0) {
        throw std::invalid_argument("Chips per symbol must be positive");
    }
    if (d_key.size() != 32) {
        throw std::invalid_argument("ChaCha20 key must be exactly 32 bytes");
    }
    if (d_nonce.size() != 12) {
        throw std::invalid_argument("ChaCha20 nonce must be exactly 12 bytes");
    }

    if (sodium_init() < 0) {
        throw std::runtime_error("libsodium initialization failed");
    }

    build_sequence_complex(spreading_sequence);

    d_input_buffer.clear();
}

kgdss_despreader_cc_impl::~kgdss_despreader_cc_impl() {}

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
    float sum_i = 0.0f;
    float sum_q = 0.0f;
    int n = std::min(length, d_sequence_length);

    for (int i = 0; i < n; i++) {
        int seq_idx = (d_code_phase + i) % d_sequence_length;
        gr_complex s = samples[offset + i];
        float m_re = d_spreading_sequence_complex[seq_idx].real();
        sum_i += s.real() * m_re;
        sum_q += s.imag() * m_re;
    }

    if (n > 0) {
        sum_i /= static_cast<float>(n);
        sum_q /= static_cast<float>(n);
    }
    return gr_complex(sum_i, sum_q);
}

void kgdss_despreader_cc_impl::update_timing()
{
    float error = d_early_correlation - d_late_correlation;
    d_timing_error = error * 0.1f;

    if (std::abs(d_timing_error) > 0.5f) {
        d_timing_offset += (d_timing_error > 0) ? 1 : -1;
        d_timing_offset = std::max(-d_timing_error_tolerance,
                                  std::min(d_timing_error_tolerance, d_timing_offset));
    }
}

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

void kgdss_despreader_cc_impl::fill_keystream(uint8_t* buf, size_t len)
{
    if (len == 0) return;
    const size_t block = d_counter / 64;
    const size_t skip = d_counter % 64;
    const size_t to_gen = skip + len;
    if (to_gen > 0) {
        std::vector<uint8_t> tmp(to_gen);
        std::memset(tmp.data(), 0, to_gen);
        crypto_stream_chacha20_ietf_xor_ic(
            tmp.data(), tmp.data(), to_gen, d_nonce.data(),
            static_cast<uint32_t>(block), d_key.data());
        std::memcpy(buf, tmp.data() + skip, len);
    }
    d_counter += len;
}

float kgdss_despreader_cc_impl::box_muller(float u1, float u2)
{
    if (u1 < 1e-10f) {
        u1 = 1e-10f;
    }
    return std::sqrt(-2.0f * std::log(u1)) *
           std::cos(2.0f * static_cast<float>(M_PI) * u2);
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

    std::lock_guard<std::mutex> lock(d_mutex);

    int ninput_items_available = ninput_items[0];
    int ninput_items_needed = noutput_items * d_chips_per_symbol;
    int ninput_items_used = std::min(ninput_items_available, ninput_items_needed);
    int actual_output_items = ninput_items_used / d_chips_per_symbol;

    const float MIN_MASK = 1e-4f;
    auto to_uniform = [](const uint8_t* b) -> float {
        uint32_t v;
        std::memcpy(&v, b, 4);
        return (static_cast<float>(v) + 0.5f) / 4294967296.0f;
    };

    int output_idx = 0;
    for (int sym = 0; sym < actual_output_items; sym++) {
        int input_offset = sym * d_chips_per_symbol;

        if (input_offset + d_chips_per_symbol > ninput_items_used) {
            break;
        }

        // Per-symbol keystream: same byte range as spreader for this symbol's chips
        const size_t ks_len = static_cast<size_t>(d_chips_per_symbol) * 16;
        std::vector<uint8_t> ks(ks_len);
        fill_keystream(ks.data(), ks_len);

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
            const int n_chips = std::min(d_chips_per_symbol, d_sequence_length);
            for (int chip = 0; chip < n_chips; chip++) {
                const uint8_t* base = ks.data() + static_cast<size_t>(chip) * 16;
                float mask_i = box_muller(to_uniform(base + 0), to_uniform(base + 4));
                float mask_q = box_muller(to_uniform(base + 8), to_uniform(base + 12));
                if (std::abs(mask_i) < MIN_MASK) mask_i = (mask_i >= 0 ? MIN_MASK : -MIN_MASK);
                if (std::abs(mask_q) < MIN_MASK) mask_q = (mask_q >= 0 ? MIN_MASK : -MIN_MASK);
                sum_i += in[input_offset + chip].real() / mask_i;
                sum_q += in[input_offset + chip].imag() / mask_q;
            }
            const float nf = static_cast<float>(n_chips);
            out_symbols[output_idx] = gr_complex(sum_i / nf, sum_q / nf);

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

            int early_offset = std::max(0, input_offset - 1);
            d_early_correlation = std::abs(correlate(in, early_offset, d_chips_per_symbol));

            d_prompt_correlation = std::abs(correlate(in, input_offset, d_chips_per_symbol));

            int late_offset = std::max(0, std::min(max_offset, input_offset + 1));
            d_late_correlation = std::abs(correlate(in, late_offset, d_chips_per_symbol));

            update_timing();

            int despread_offset = std::max(0, std::min(max_offset, input_offset + d_timing_offset));
            gr_complex despread = correlate(in, despread_offset, d_chips_per_symbol);

            float sum_i = 0.0f;
            float sum_q = 0.0f;
            const int n_chips = std::min(d_chips_per_symbol, d_sequence_length);
            for (int chip = 0; chip < n_chips; chip++) {
                const uint8_t* base = ks.data() + static_cast<size_t>(chip) * 16;
                float mask_i = box_muller(to_uniform(base + 0), to_uniform(base + 4));
                float mask_q = box_muller(to_uniform(base + 8), to_uniform(base + 12));
                if (std::abs(mask_i) < MIN_MASK) mask_i = (mask_i >= 0 ? MIN_MASK : -MIN_MASK);
                if (std::abs(mask_q) < MIN_MASK) mask_q = (mask_q >= 0 ? MIN_MASK : -MIN_MASK);
                sum_i += in[despread_offset + chip].real() / mask_i;
                sum_q += in[despread_offset + chip].imag() / mask_q;
            }
            const float nf = static_cast<float>(n_chips);
            out_symbols[output_idx] = gr_complex(sum_i / nf, sum_q / nf);

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

