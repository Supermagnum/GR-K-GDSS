/*
 * Keyed GDSS Spreader implementation
 *
 * Spreads complex baseband symbols using cryptographically keyed Gaussian-distributed
 * masking. Each input symbol is repeated chips_per_symbol times and multiplied
 * chip-wise by a mask derived from ChaCha20 keystream via the Box-Muller transform,
 * so the output is statistically similar to Gaussian noise unless the receiver
 * has the same key and nonce to invert the mask.
 *
 * Algorithm:
 *   - ChaCha20 IETF (libsodium) produces a keystream from key (32 bytes) and
 *     nonce (12 bytes). The 64-byte block counter is implicit (starts at 0).
 *   - Every 16 keystream bytes form two uniform [0,1) values (uint32 LE) that
 *     are fed to Box-Muller to produce two Gaussian samples (I and Q mask).
 *   - Mask values are clamped to minimum magnitude MIN_MASK (1e-4) to avoid
 *     division instability in the despreader.
 *   - Output: out[i] = symbol.real() * mask_i + j * symbol.imag() * mask_q.
 *
 * Key/nonce can be set at construction or later via the set_key message port
 * (PMT dict with "key" u8vector length 32, "nonce" u8vector length 12).
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <gnuradio/kgdss/kgdss_spreader_cc.h>
#include "chacha_ietf_keystream.h"
#include "kgdss_spreader_cc_impl.h"
#include <gnuradio/io_signature.h>
#include <pmt/pmt.h>
#include <cassert>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <stdexcept>

namespace gr {
namespace kgdss {

kgdss_spreader_cc::~kgdss_spreader_cc() {}

void kgdss_spreader_cc::set_spreading_sequence(const std::vector<float>& sequence)
{
    (void)sequence;
}

void kgdss_spreader_cc::set_chips_per_symbol(int chips_per_symbol)
{
    (void)chips_per_symbol;
}

void kgdss_spreader_cc::regenerate_sequence(float variance, unsigned int seed)
{
    (void)variance;
    (void)seed;
}

std::vector<float> kgdss_spreader_cc::get_spreading_sequence() const
{
    return std::vector<float>();
}

kgdss_spreader_cc::sptr kgdss_spreader_cc::make(int sequence_length,
                                                int chips_per_symbol,
                                                float variance,
                                                unsigned int seed,
                                                const std::vector<uint8_t>& chacha_key,
                                                const std::vector<uint8_t>& chacha_nonce)
{
    return gnuradio::get_initial_sptr(
        new kgdss_spreader_cc_impl(sequence_length,
                                   chips_per_symbol,
                                   variance,
                                   seed,
                                   chacha_key,
                                   chacha_nonce));
}

kgdss_spreader_cc_impl::kgdss_spreader_cc_impl(int sequence_length,
                                               int chips_per_symbol,
                                               float variance,
                                               unsigned int seed,
                                               const std::vector<uint8_t>& chacha_key,
                                               const std::vector<uint8_t>& chacha_nonce)
    : kgdss_spreader_cc("kgdss_spreader_cc",
                        gr::io_signature::make(1, 1, sizeof(gr_complex)),
                        gr::io_signature::make(1, 1, sizeof(gr_complex)),
                        sequence_length,
                        chips_per_symbol,
                        variance,
                        seed),
      d_sequence_length(sequence_length),
      d_chips_per_symbol(chips_per_symbol),
      d_chip_index(0),
      d_variance(variance),
      d_seed(seed == 0 ? static_cast<unsigned int>(
                              std::chrono::system_clock::now().time_since_epoch().count())
                       : seed),
      d_rng(d_seed),
      d_gaussian(0.0f, std::sqrt(variance)),
      d_key(chacha_key),
      d_nonce(chacha_nonce),
      d_counter(0),
      d_key_set(chacha_key.size() == 32 && chacha_nonce.size() == 12),
      d_ks_remainder_len(0)
{
    if (d_sequence_length <= 0) {
        throw std::invalid_argument("Sequence length must be positive");
    }
    if (d_chips_per_symbol <= 0) {
        throw std::invalid_argument("Chips per symbol must be positive");
    }
    if (d_variance <= 0.0f) {
        throw std::invalid_argument("Variance must be positive");
    }
    if (!d_key.empty() && d_key.size() != 32) {
        throw std::invalid_argument("ChaCha20 key must be 0 or 32 bytes");
    }
    if (!d_nonce.empty() && d_nonce.size() != 12) {
        throw std::invalid_argument("ChaCha20 nonce must be 0 or 12 bytes");
    }
    if (d_key_set && (d_key.size() != 32 || d_nonce.size() != 12)) {
        d_key_set = false;
    }

    if (sodium_init() < 0) {
        throw std::runtime_error("libsodium initialization failed");
    }

    generate_sequence();

    message_port_register_in(pmt::mp("set_key"));
    set_msg_handler(pmt::mp("set_key"),
                    [this](pmt::pmt_t msg) { this->handle_key_msg(msg); });
}

kgdss_spreader_cc_impl::~kgdss_spreader_cc_impl() {}

void kgdss_spreader_cc_impl::handle_key_msg(pmt::pmt_t msg)
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
}

void kgdss_spreader_cc_impl::generate_sequence()
{
    d_spreading_sequence_complex.resize(d_sequence_length);
    for (int i = 0; i < d_sequence_length; i++) {
        float u = d_gaussian(d_rng);
        float v = d_gaussian(d_rng);
        d_spreading_sequence_complex[i] =
            gr_complex(std::abs(u), std::abs(v));
    }
}

void kgdss_spreader_cc_impl::set_spreading_sequence(const std::vector<float>& sequence)
{
    std::lock_guard<std::mutex> lock(d_mutex);
    int need = 2 * d_sequence_length;
    if (static_cast<int>(sequence.size()) == need) {
        d_spreading_sequence_complex.resize(d_sequence_length);
        for (int i = 0; i < d_sequence_length; i++) {
            d_spreading_sequence_complex[i] =
                gr_complex(sequence[2 * i], sequence[2 * i + 1]);
        }
    } else if (static_cast<int>(sequence.size()) == d_sequence_length) {
        d_spreading_sequence_complex.resize(d_sequence_length);
        for (int i = 0; i < d_sequence_length; i++) {
            d_spreading_sequence_complex[i] =
                gr_complex(std::abs(sequence[i]), 0.0f);
        }
    } else {
        throw std::invalid_argument("Sequence length must be sequence_length or 2*sequence_length (I,Q interleaved)");
    }
    d_chip_index = 0;
}

void kgdss_spreader_cc_impl::set_chips_per_symbol(int chips_per_symbol)
{
    std::lock_guard<std::mutex> lock(d_mutex);
    if (chips_per_symbol <= 0) {
        throw std::invalid_argument("Chips per symbol must be positive");
    }
    d_chips_per_symbol = chips_per_symbol;
    set_interpolation(chips_per_symbol);
}

void kgdss_spreader_cc_impl::regenerate_sequence(float variance, unsigned int seed)
{
    std::lock_guard<std::mutex> lock(d_mutex);
    if (variance <= 0.0f) {
        throw std::invalid_argument("Variance must be positive");
    }
    d_variance = variance;
    d_seed = seed == 0 ? static_cast<unsigned int>(
                             std::chrono::system_clock::now().time_since_epoch().count())
                       : seed;
    d_rng.seed(d_seed);
    d_gaussian = std::normal_distribution<float>(0.0f, std::sqrt(variance));
    generate_sequence();
    d_chip_index = 0;
}

std::vector<float> kgdss_spreader_cc_impl::get_spreading_sequence() const
{
    std::lock_guard<std::mutex> lock(d_mutex);
    std::vector<float> out(2 * d_sequence_length);
    for (int i = 0; i < d_sequence_length; i++) {
        out[2 * i] = d_spreading_sequence_complex[i].real();
        out[2 * i + 1] = d_spreading_sequence_complex[i].imag();
    }
    return out;
}

/* Box-Muller transform: convert two uniform [0,1) values to one Gaussian(0, variance).
 * u1 must be > 0 (log(u1) defined); u2 is the angle. Result scaled by sqrt(d_variance). */
float kgdss_spreader_cc_impl::box_muller(float u1, float u2)
{
    if (u1 < 1e-10f) {
        u1 = 1e-10f;
    }
    float g = std::sqrt(-2.0f * std::log(u1)) *
              std::cos(2.0f * static_cast<float>(M_PI) * u2);
    return g * std::sqrt(d_variance);
}

int kgdss_spreader_cc_impl::work(int noutput_items,
                                 gr_vector_const_void_star& input_items,
                                 gr_vector_void_star& output_items)
{
    const gr_complex* in = (const gr_complex*)input_items[0];
    gr_complex* out = (gr_complex*)output_items[0];

    std::array<uint8_t, 32> key_snap{};
    std::array<uint8_t, 12> nonce_snap{};
    uint64_t ctr_snap = 0;
    std::array<uint8_t, 64> rem_snap{};
    size_t rem_len_snap = 0;
    bool key_ok = false;

    {
        std::lock_guard<std::mutex> key_lock(d_key_mutex);
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

    if (!key_ok) {
        std::fill(out, out + noutput_items, gr_complex(0.0f, 0.0f));
        return noutput_items;
    }

    const size_t need = static_cast<size_t>(noutput_items) * 16U;
    if (need > 0) {
        const uint64_t last_byte = ctr_snap + need - 1ULL;
        const uint64_t last_block = last_byte / 64ULL;
        assert(last_block <= static_cast<uint64_t>(UINT32_MAX));
        if (last_block > static_cast<uint64_t>(UINT32_MAX)) {
            throw std::runtime_error(
                "kgdss_spreader_cc: ChaCha20-IETF block counter would exceed UINT32_MAX "
                "(counter limit); reduce burst length or re-key.");
        }
    }

    if (need > d_ks_buf.size()) {
        d_ks_buf.resize(need);
    }

    detail::produce_chacha_ietf_keystream(d_ks_buf.data(),
                                          need,
                                          key_snap.data(),
                                          nonce_snap.data(),
                                          ctr_snap,
                                          rem_snap,
                                          rem_len_snap);

    bool committed = false;
    {
        std::lock_guard<std::mutex> key_lock(d_key_mutex);
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

    if (!committed) {
        std::fill(out, out + noutput_items, gr_complex(0.0f, 0.0f));
        return noutput_items;
    }

    std::lock_guard<std::mutex> lock(d_mutex);

    int ninput_items = noutput_items / d_chips_per_symbol;
    int output_idx = 0;

    auto to_uniform = [](const uint8_t* b) -> float {
        uint32_t v;
        std::memcpy(&v, b, 4);
        return (static_cast<float>(v) + 0.5f) / 4294967296.0f;
    };

    const float MIN_MASK = 1e-4f;
    for (int sym_idx = 0; sym_idx < ninput_items; sym_idx++) {
        gr_complex symbol = in[sym_idx];

        for (int chip = 0; chip < d_chips_per_symbol; chip++) {
            int out_index = output_idx++;
            const uint8_t* base = d_ks_buf.data() + static_cast<size_t>(out_index) * 16;

            float mask_i = box_muller(to_uniform(base + 0), to_uniform(base + 4));
            float mask_q = box_muller(to_uniform(base + 8), to_uniform(base + 12));
            if (std::abs(mask_i) < MIN_MASK) mask_i = (mask_i >= 0 ? MIN_MASK : -MIN_MASK);
            if (std::abs(mask_q) < MIN_MASK) mask_q = (mask_q >= 0 ? MIN_MASK : -MIN_MASK);

            out[out_index] = gr_complex(symbol.real() * mask_i,
                                        symbol.imag() * mask_q);
        }

        d_chip_index = (d_chip_index + d_chips_per_symbol) % d_sequence_length;
    }

    return output_idx;
}

} // namespace kgdss
} // namespace gr

