// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef GNURADIO4_KGDSS_DETAIL_SPREADERENGINE_HPP
#define GNURADIO4_KGDSS_DETAIL_SPREADERENGINE_HPP

#include <gnuradio-4.0/Block.hpp>
#include <gnuradio-4.0/kgdss/detail/ChachaKeystreamHelper.hpp>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <mutex>
#include <random>
#include <span>
#include <vector>

#include <sodium.h>

namespace gnuradio4::kgdss::detail {

class SpreaderEngine {
public:
    void generateSequence(int sequenceLength, float variance, unsigned seed) noexcept {
        if (sequenceLength <= 0 || variance <= 0.0f) {
            return;
        }
        const unsigned      s =
            seed == 0U
                ? static_cast<unsigned>(
                      std::chrono::system_clock::now().time_since_epoch().count())
                : seed;
        d_rng.seed(s);
        d_gaussian   = std::normal_distribution<float>(0.0f, std::sqrt(variance));
        d_spreading_sequence_complex.resize(static_cast<std::size_t>(sequenceLength));
        for (int i = 0; i < sequenceLength; ++i) {
            const float                       u =
                std::abs(d_gaussian(d_rng));
            const float                       v =
                std::abs(d_gaussian(d_rng));
            d_spreading_sequence_complex[static_cast<std::size_t>(i)] = std::complex<float>(u, v);
        }
        d_chip_index = 0;
    }

    void setKeyMaterial(const std::array<std::uint8_t, 32>& key,
        const std::array<std::uint8_t, 12>&                   nonce) noexcept {
        std::unique_lock lk(d_key_mutex);
        std::memcpy(d_key.data(), key.data(), 32U);
        std::memcpy(d_nonce.data(), nonce.data(), 12U);
        d_counter           = 0ULL;
        d_ks_remainder_len  = 0UZ;
        d_key_armed.store(true, std::memory_order_release);
        d_overflow.store(false, std::memory_order_release);
        d_chip_index = 0;
    }

    static void rejectKeyWithLog() noexcept {
        std::cerr << "gr-k-gdss: spreader set_key rejected (invalid key/nonce lengths)\n";
    }

    void clearKey() noexcept {
        std::unique_lock lk(d_key_mutex);
        sodium_memzero(d_key.data(), d_key.size());
        sodium_memzero(d_nonce.data(), d_nonce.size());
        d_key_armed.store(false, std::memory_order_release);
        d_counter           = 0ULL;
        d_ks_remainder_len  = 0UZ;
    }

    [[nodiscard]] bool keyArmed() const noexcept { return d_key_armed.load(std::memory_order_acquire); }

    void setCounter(std::uint64_t c) noexcept {
        std::unique_lock lk(d_key_mutex);
        d_counter          = c;
        d_ks_remainder_len = 0UZ;
    }

    [[nodiscard]] bool overflowOccurred() const noexcept { return d_overflow.load(std::memory_order_acquire); }

    static void boxMullerPair(float u1, float u2, float variance, float& g0, float& g1) noexcept {
        if (u1 < 1e-10f) {
            u1 = 1e-10f;
        }
        const float radius =
            std::sqrt(-2.0f * std::log(u1)) * std::sqrt(variance);
        const float angle = 2.0f * static_cast<float>(M_PI) * u2;
        g0                  = radius * std::cos(angle);
        g1                  = radius * std::sin(angle);
    }

    /** Ported from GR 3.10 kgdss_spreader_cc_impl::work. chipOut.size() must be symIn.size() * chipsPerSymbol. */
    [[nodiscard]] gr::work::Status process(std::span<const std::complex<float>> symIn,
        std::span<std::complex<float>>                                                  chipOut, int chipsPerSymbol,
        float                                                                variance,
        [[maybe_unused]] int                                                 sequenceLength,
        std::size_t&                                                                   noKeySilentCounter) noexcept {
        using gr::work::Status;
        if (!d_key_armed.load(std::memory_order_acquire)) {
            if ((noKeySilentCounter++ % 8192UZ) == 0UZ) {
                std::cerr << "gr-k-gdss: spreader blocked: no cryptographic key armed "
                             "(GDSS masking disabled).\n";
            }
            return Status::INSUFFICIENT_INPUT_ITEMS;
        }

        std::array<std::uint8_t, 32> key_snap{};
        std::array<std::uint8_t, 12> nonce_snap{};
        std::uint64_t                ctr_snap     = 0;
        std::array<std::uint8_t, 64> rem_snap{};
        std::size_t                  rem_len_snap = 0;
        bool                         key_ok       = false;
        {
            std::unique_lock lk(d_key_mutex);
            key_ok = d_key_armed.load(std::memory_order_relaxed);
            if (key_ok) {
                std::memcpy(key_snap.data(), d_key.data(), 32U);
                std::memcpy(nonce_snap.data(), d_nonce.data(), 12U);
                ctr_snap     = d_counter;
                rem_len_snap = d_ks_remainder_len;
                if (rem_len_snap > 0) {
                    std::memcpy(rem_snap.data(), d_ks_remainder.data(), rem_len_snap);
                }
            }
        }
        if (!key_ok) {
            return Status::INSUFFICIENT_INPUT_ITEMS;
        }

        const int ninput_items       = static_cast<int>(symIn.size());
        const int nchips_to_produce  = ninput_items * chipsPerSymbol;
        if (static_cast<std::size_t>(nchips_to_produce) != chipOut.size()) {
            return Status::ERROR;
        }
        const std::size_t need = static_cast<std::size_t>(nchips_to_produce) * 8U;
        if (need > 0) {
            const std::uint64_t last_byte  = ctr_snap + need - 1ULL;
            const std::uint64_t last_block = last_byte / 64ULL;
            if (last_block > static_cast<std::uint64_t>(UINT32_MAX)) {
                d_overflow.store(true, std::memory_order_release);
                d_key_armed.store(false, std::memory_order_release);
                return Status::ERROR;
            }
        }

        if (need > d_ks_buf.size()) {
            d_ks_buf.resize(need);
        }

        std::uint64_t                ctr_mut   = ctr_snap;
        std::size_t                  rem_mut   = rem_len_snap;
        std::array<std::uint8_t, 64> rem_buf   = rem_snap;
        if (!produce_chacha_ietf_keystream(d_ks_buf.data(), need, key_snap.data(), nonce_snap.data(), ctr_mut, rem_buf, rem_mut)) {
            d_overflow.store(true, std::memory_order_release);
            d_key_armed.store(false, std::memory_order_release);
            return Status::ERROR;
        }

        bool committed = false;
        {
            std::unique_lock lk(d_key_mutex);
            if (d_key_armed.load(std::memory_order_relaxed)
                && std::memcmp(d_key.data(), key_snap.data(), 32) == 0
                && std::memcmp(d_nonce.data(), nonce_snap.data(), 12) == 0) {
                d_counter          = ctr_mut;
                d_ks_remainder_len = rem_mut;
                if (rem_mut > 0) {
                    std::memcpy(d_ks_remainder.data(), rem_buf.data(), rem_mut);
                }
                committed = true;
            }
        }
        if (!committed) {
            return Status::INSUFFICIENT_INPUT_ITEMS;
        }

        auto to_uniform = [](const std::uint8_t* b) -> float {
            const std::uint32_t v =
                static_cast<std::uint32_t>(b[0])
                | (static_cast<std::uint32_t>(b[1]) << 8)
                | (static_cast<std::uint32_t>(b[2]) << 16)
                | (static_cast<std::uint32_t>(b[3]) << 24);
            return (static_cast<float>(v) + 0.5f) / 4294967296.0f;
        };

        constexpr float MIN_MASK       = 1e-4f;
        int             chip_index     = d_chip_index;
        int             output_idx     = 0;
        const int       sl             =
            sequenceLength > 0 ? sequenceLength : 1;
        for (int sym_idx = 0; sym_idx < ninput_items; ++sym_idx) {
            const std::complex<float> symbol = symIn[static_cast<std::size_t>(sym_idx)];
            for (int chip = 0; chip < chipsPerSymbol; ++chip) {
                const int                     out_index = output_idx++;
                const std::uint8_t*          base =
                    d_ks_buf.data() + static_cast<std::size_t>(out_index) * 8U;
                float                         mask_i = 0.0f;
                float                         mask_q = 0.0f;
                boxMullerPair(to_uniform(base + 0), to_uniform(base + 4), variance, mask_i, mask_q);
                if (std::abs(mask_i) < MIN_MASK) {
                    mask_i = (mask_i >= 0 ? MIN_MASK : -MIN_MASK);
                }
                if (std::abs(mask_q) < MIN_MASK) {
                    mask_q = (mask_q >= 0 ? MIN_MASK : -MIN_MASK);
                }
                const std::complex<float> mask(mask_i, mask_q);
                chipOut[static_cast<std::size_t>(out_index)] = symbol * mask;
                chip_index = (chip_index + 1) % sl;
                (void)chip;
            }
        }
        d_chip_index = chip_index;
        return Status::OK;
    }

private:
    std::vector<std::complex<float>> d_spreading_sequence_complex{};
    int                              d_chip_index{ 0 };
    std::mt19937                     d_rng{};
    std::normal_distribution<float> d_gaussian{ 0.0f, 1.0f };

    std::mutex                       d_key_mutex{};
    std::array<std::uint8_t, 32>     d_key{};
    std::array<std::uint8_t, 12>     d_nonce{};
    std::uint64_t                    d_counter{ 0 };
    std::atomic<bool>                d_key_armed{ false };
    std::array<std::uint8_t, 64>     d_ks_remainder{};
    std::size_t                      d_ks_remainder_len{ 0 };
    std::vector<std::uint8_t>        d_ks_buf{};
    std::atomic<bool>                d_overflow{ false };
};

} // namespace gnuradio4::kgdss::detail

#endif
