/*
 * Keyed GDSS Despreader implementation
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#ifndef INCLUDED_KGDSS_DESPREDER_CC_IMPL_H
#define INCLUDED_KGDSS_DESPREDER_CC_IMPL_H

#include <gnuradio/kgdss/kgdss_despreader_cc.h>
#include <vector>
#include <deque>
#include <mutex>
#include <complex>
#include <cstdint>
#include <sodium.h>

namespace gr {
namespace kgdss {

class kgdss_despreader_cc_impl : public kgdss_despreader_cc
{
private:
    std::vector<gr_complex> d_spreading_sequence_complex;
    int d_sequence_length;
    int d_chips_per_symbol;
    float d_correlation_threshold;
    int d_timing_error_tolerance;

    sync_state d_state;
    int d_code_phase;
    int d_timing_offset;
    int d_acquisition_counter;
    int d_lock_counter;
    static const int ACQUISITION_TIMEOUT = 10000;
    static const int LOCK_THRESHOLD = 10;

    std::deque<gr_complex> d_input_buffer;
    static const int BUFFER_SIZE = 1024;

    float d_early_correlation;
    float d_prompt_correlation;
    float d_late_correlation;
    float d_timing_error;

    float d_correlation_peak;
    float d_correlation_avg;
    bool d_is_locked;

    float d_signal_power;
    float d_noise_power;
    float d_snr_db;

    float d_last_soft_metric;

    float d_freq_error_rad_per_sym;
    float d_prev_corr_phase;
    bool d_have_prev_corr;

    static const float ADAPTIVE_THRESHOLD_MIN;
    static const int COARSE_SEARCH_BINS;

    mutable std::mutex d_mutex;

    std::vector<uint8_t> d_key;   // 32 bytes ChaCha20 key
    std::vector<uint8_t> d_nonce; // 12 bytes ChaCha20 nonce
    uint64_t d_counter;           // keystream position counter

    void build_sequence_complex(const std::vector<float>& spreading_sequence);
    gr_complex correlate(const gr_complex* samples, int offset, int length);
    void update_timing();
    void update_lock_detection(float correlation);
    void update_snr_estimate(gr_complex symbol, float correlation);

    void fill_keystream(uint8_t* buf, size_t len);
    float box_muller(float u1, float u2);

    void forecast(int noutput_items, gr_vector_int& ninput_items_required) override;

public:
    kgdss_despreader_cc_impl(const std::vector<float>& spreading_sequence,
                             int chips_per_symbol,
                             float correlation_threshold,
                             int timing_error_tolerance,
                             const std::vector<uint8_t>& chacha_key,
                             const std::vector<uint8_t>& chacha_nonce);
    ~kgdss_despreader_cc_impl();

    void set_spreading_sequence(const std::vector<float>& spreading_sequence) override;
    void set_chips_per_symbol(int chips_per_symbol) override;
    sync_state get_sync_state() const override;
    bool is_locked() const override;
    float get_snr_estimate() const override;
    float get_last_soft_metric() const override;
    float get_frequency_error() const override;

    int general_work(int noutput_items,
                     gr_vector_int& ninput_items,
                     gr_vector_const_void_star& input_items,
                     gr_vector_void_star& output_items) override;
};

} // namespace kgdss
} // namespace gr

#endif /* INCLUDED_KGDSS_DESPREDER_CC_IMPL_H */

