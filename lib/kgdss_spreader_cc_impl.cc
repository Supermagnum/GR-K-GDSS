/*
 * Keyed GDSS Spreader implementation
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <gnuradio/kgdss/kgdss_spreader_cc.h>
#include "kgdss_spreader_cc_impl.h"
#include <gnuradio/io_signature.h>
#include <chrono>
#include <cmath>
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
      d_counter(0)
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
    if (d_key.size() != 32) {
        throw std::invalid_argument("ChaCha20 key must be exactly 32 bytes");
    }
    if (d_nonce.size() != 12) {
        throw std::invalid_argument("ChaCha20 nonce must be exactly 12 bytes");
    }

    if (sodium_init() < 0) {
        throw std::runtime_error("libsodium initialization failed");
    }

    generate_sequence();
}

kgdss_spreader_cc_impl::~kgdss_spreader_cc_impl() {}

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

void kgdss_spreader_cc_impl::fill_keystream(uint8_t* buf, size_t len)
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

    std::lock_guard<std::mutex> lock(d_mutex);

    int ninput_items = noutput_items / d_chips_per_symbol;
    int output_idx = 0;

    // Generate keyed Gaussian masking using ChaCha20 + Box-Muller (mask clamp 1e-4f)
    std::vector<uint8_t> ks(static_cast<size_t>(noutput_items) * 16);
    fill_keystream(ks.data(), ks.size());

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
            const uint8_t* base = ks.data() + static_cast<size_t>(out_index) * 16;

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

