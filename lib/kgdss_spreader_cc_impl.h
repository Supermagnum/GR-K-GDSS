/*
 * Keyed GDSS Spreader implementation
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#ifndef INCLUDED_KGDSS_SPREADER_CC_IMPL_H
#define INCLUDED_KGDSS_SPREADER_CC_IMPL_H

#include <gnuradio/kgdss/kgdss_spreader_cc.h>
#include <pmt/pmt.h>
#include <array>
#include <vector>
#include <mutex>
#include <random>
#include <complex>
#include <cstdint>
#include <cstddef>
#include <sodium.h>

namespace gr {
namespace kgdss {

class kgdss_spreader_cc_impl : public kgdss_spreader_cc
{
private:
    std::vector<gr_complex> d_spreading_sequence_complex;
    int d_sequence_length;
    int d_chips_per_symbol;
    int d_chip_index;
    float d_variance;
    unsigned int d_seed;
    std::mt19937 d_rng;
    std::normal_distribution<float> d_gaussian;
    mutable std::mutex d_mutex;

    std::vector<uint8_t> d_key;   // 32 bytes ChaCha20 key
    std::vector<uint8_t> d_nonce; // 12 bytes ChaCha20 nonce
    uint64_t d_counter;           // keystream position counter
    bool d_key_set;               // true once key/nonce set (constructor or set_key message)
    std::mutex d_key_mutex; // protects key material, d_counter, remainder, d_key_set
    std::array<uint8_t, 64> d_ks_remainder;
    size_t d_ks_remainder_len;
    std::vector<uint8_t> d_ks_buf;

    void generate_sequence();
    void handle_key_msg(pmt::pmt_t msg);
    float box_muller(float u1, float u2);

public:
    kgdss_spreader_cc_impl(int sequence_length,
                           int chips_per_symbol,
                           float variance,
                           unsigned int seed,
                           const std::vector<uint8_t>& chacha_key,
                           const std::vector<uint8_t>& chacha_nonce);
    ~kgdss_spreader_cc_impl();

    void set_spreading_sequence(const std::vector<float>& sequence) override;
    void set_chips_per_symbol(int chips_per_symbol) override;
    void regenerate_sequence(float variance, unsigned int seed) override;
    std::vector<float> get_spreading_sequence() const override;

    int work(int noutput_items,
             gr_vector_const_void_star& input_items,
             gr_vector_void_star& output_items) override;
};

} // namespace kgdss
} // namespace gr

#endif /* INCLUDED_KGDSS_SPREADER_CC_IMPL_H */

