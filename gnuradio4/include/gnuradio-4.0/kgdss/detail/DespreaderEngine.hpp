// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef GNURADIO4_KGDSS_DETAIL_DESPREADERENGINE_HPP
#define GNURADIO4_KGDSS_DETAIL_DESPREADERENGINE_HPP

#include <gnuradio-4.0/Block.hpp>
#include <gnuradio-4.0/kgdss/detail/ChachaKeystreamHelper.hpp>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <mutex>
#include <span>
#include <stdexcept>
#include <vector>

#include <sodium.h>

namespace gnuradio4::kgdss::detail {

class DespreaderEngine {
public:
    enum class SyncState { Acquisition, Tracking, Locked };

private:
    static constexpr float kAdaptiveThreshMin = 0.2f;
    static constexpr int kCoarseBins          = 32;
    static constexpr int kLockThresh          = 10;
    static constexpr int kAcqTimeout          = 10000;

public:
    void configureFromSpreadingSequence(std::span<const float> spreading_sequence, int chips_per_symbol, float correlation_threshold,
        int timing_error_tolerance) {
        if (spreading_sequence.empty()) {
            throw std::invalid_argument("Spreading sequence cannot be empty");
        }
        if (chips_per_symbol <= 0) {
            throw std::invalid_argument("Chips per symbol must be positive");
        }
        d_chips_per_symbol       = chips_per_symbol;
        d_correlation_threshold  = correlation_threshold;
        d_timing_error_tolerance = timing_error_tolerance;
        buildSequenceComplex(spreading_sequence);
        resetTrackingWithMutex();
    }

    void applyChipsSettings(int chips_per_symbol) {
        if (chips_per_symbol <= 0) {
            throw std::invalid_argument("Chips per symbol must be positive");
        }
        d_chips_per_symbol = chips_per_symbol;
    }

    void setCorrelationThreshold(float t) noexcept { d_correlation_threshold = t; }
    void setTimingErrorTolerance(int t) noexcept { d_timing_error_tolerance = t; }

    static void rejectKeyWithLog(const char* context) noexcept {
        std::cerr << "gr-k-gdss: despreader set_key rejected (invalid key/nonce lengths) [" << context << "]\n";
    }

    void setKeyMaterial(const std::array<std::uint8_t, 32>& key, const std::array<std::uint8_t, 12>& nonce) noexcept {
        std::unique_lock lk(d_key_mutex);
        std::memcpy(d_key.data(), key.data(), 32U);
        std::memcpy(d_nonce.data(), nonce.data(), 12U);
        d_counter          = 0ULL;
        d_ks_remainder_len = 0UZ;
        d_key_armed.store(true, std::memory_order_release);
        d_overflow.store(false, std::memory_order_release);
        std::lock_guard sm(d_mutex);
        resetTrackingUnlocked();
    }

    void clearKey() noexcept {
        std::unique_lock lk(d_key_mutex);
        sodium_memzero(d_key.data(), d_key.size());
        sodium_memzero(d_nonce.data(), d_nonce.size());
        d_key_armed.store(false, std::memory_order_release);
        d_counter          = 0ULL;
        d_ks_remainder_len = 0UZ;
        std::lock_guard sm(d_mutex);
        resetTrackingUnlocked();
    }

    [[nodiscard]] bool keyArmed() const noexcept { return d_key_armed.load(std::memory_order_acquire); }

    void setCounter(std::uint64_t c) noexcept {
        std::unique_lock lk(d_key_mutex);
        d_counter          = c;
        d_ks_remainder_len = 0UZ;
    }

    [[nodiscard]] bool overflowOccurred() const noexcept { return d_overflow.load(std::memory_order_acquire); }

    void setChannelEqualization(bool enable) noexcept {
        std::lock_guard lk(d_mutex);
        d_channel_eq_enabled = enable;
        d_channel_est        = std::complex<float>(1.0f, 0.0f);
    }

    [[nodiscard]] bool getChannelEqualization() const noexcept {
        std::lock_guard lk(d_mutex);
        return d_channel_eq_enabled;
    }

    [[nodiscard]] SyncState getSyncState() const noexcept {
        std::lock_guard lk(d_mutex);
        return d_state;
    }

    [[nodiscard]] bool isLocked() const noexcept {
        std::lock_guard lk(d_mutex);
        return d_is_locked;
    }

    [[nodiscard]] float getSnrEstimate() const noexcept {
        std::lock_guard lk(d_mutex);
        return d_snr_db;
    }

    [[nodiscard]] int timingOffset() const noexcept {
        std::lock_guard lk(d_mutex);
        return d_timing_offset;
    }

    /** Port of kgdss_despreader_cc_impl::general_work (GR 3.10). */
    [[nodiscard]] gr::work::Status process(std::span<const std::complex<float>> in, std::span<std::complex<float>> symOut,
        std::span<float> lockOut, std::span<float> snrOut, int& chipsConsumed, std::size_t& noKeySilentCounter) noexcept {
        using gr::work::Status;
        chipsConsumed = 0;
        if (!d_key_armed.load(std::memory_order_acquire)) {
            if ((noKeySilentCounter++ % 8192UZ) == 0UZ) {
                std::cerr << "gr-k-gdss: despreader blocked: no cryptographic key armed.\n";
            }
            return Status::INSUFFICIENT_INPUT_ITEMS;
        }

        const int nAvail = static_cast<int>(in.size());
        const int maxByIn = nAvail / std::max(1, d_chips_per_symbol);
        const int cap    = static_cast<int>(std::min({ symOut.size(), lockOut.size(), snrOut.size() }));
        const int actual = std::min(maxByIn, cap);
        if (actual <= 0) {
            return Status::INSUFFICIENT_INPUT_ITEMS;
        }

        const float                          kMinMask = 1e-4f;
        auto                                 toUniform  = [](const std::uint8_t* b) -> float {
            const std::uint32_t v = static_cast<std::uint32_t>(b[0]) | (static_cast<std::uint32_t>(b[1]) << 8)
                | (static_cast<std::uint32_t>(b[2]) << 16) | (static_cast<std::uint32_t>(b[3]) << 24);
            return (static_cast<float>(v) + 0.5f) / 4294967296.0f;
        };

        int output_idx = 0;
        for (int sym = 0; sym < actual; ++sym) {
            const int input_offset = sym * d_chips_per_symbol;
            if (input_offset + d_chips_per_symbol > nAvail) {
                break;
            }

            const std::size_t ks_len = static_cast<std::size_t>(d_chips_per_symbol) * 8U;

            std::array<std::uint8_t, 32> key_snap{};
            std::array<std::uint8_t, 12> nonce_snap{};
            std::uint64_t                ctr_snap     = 0;
            std::array<std::uint8_t, 64> rem_snap{};
            std::size_t                  rem_len_snap = 0;
            bool                         key_ok       = false;

            {
                std::lock_guard kl(d_key_mutex);
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
                break;
            }

            if (ks_len > 0) {
                const std::uint64_t last_byte  = ctr_snap + ks_len - 1ULL;
                const std::uint64_t last_block = last_byte / 64ULL;
                if (last_block > static_cast<std::uint64_t>(UINT32_MAX)) {
                    d_overflow.store(true, std::memory_order_release);
                    d_key_armed.store(false, std::memory_order_release);
                    return Status::ERROR;
                }
            }

            if (ks_len > d_ks_buf.size()) {
                d_ks_buf.resize(ks_len);
            }

            if (!produce_chacha_ietf_keystream(d_ks_buf.data(), ks_len, key_snap.data(), nonce_snap.data(), ctr_snap, rem_snap, rem_len_snap)) {
                d_overflow.store(true, std::memory_order_release);
                d_key_armed.store(false, std::memory_order_release);
                return Status::ERROR;
            }

            bool committed = false;
            {
                std::lock_guard kl(d_key_mutex);
                if (d_key_armed.load(std::memory_order_relaxed)
                    && std::memcmp(d_key.data(), key_snap.data(), 32) == 0 && std::memcmp(d_nonce.data(), nonce_snap.data(), 12) == 0) {
                    d_counter          = ctr_snap;
                    d_ks_remainder_len = rem_len_snap;
                    if (rem_len_snap > 0) {
                        std::memcpy(d_ks_remainder.data(), rem_snap.data(), rem_len_snap);
                    }
                    committed = true;
                }
            }
            const std::uint8_t* ks = d_ks_buf.data();
            if (!committed) {
                break;
            }

            const std::complex<float>* samp = in.data();

            std::unique_lock sl(d_mutex);
            if (d_state == SyncState::Acquisition) {
                const int                       step           = std::max(1, d_sequence_length / kCoarseBins);
                float                           best_corr      = 0.0f;
                int                             best_phase     = d_code_phase;

                for (int phase = 0; phase < d_sequence_length; phase += step) {
                    d_code_phase = phase;
                    const float corr_mag = std::abs(correlatePort(samp, input_offset, d_chips_per_symbol));
                    if (corr_mag > best_corr) {
                        best_corr = corr_mag;
                        best_phase = phase;
                    }
                }
                const int start = std::max(0, best_phase - step);
                const int stop  = std::min(d_sequence_length, best_phase + step + 1);
                for (int phase = start; phase < stop; ++phase) {
                    d_code_phase = phase;
                    const float corr_mag = std::abs(correlatePort(samp, input_offset, d_chips_per_symbol));
                    if (corr_mag > best_corr) {
                        best_corr = corr_mag;
                        best_phase = phase;
                    }
                }

                d_code_phase           = best_phase;
                d_prompt_correlation = best_corr;
                updateLockDetection(best_corr);

                d_acquisition_counter++;
                if (d_acquisition_counter > kAcqTimeout) {
                    d_acquisition_counter = 0;
                }

                const std::complex<float> despread = correlatePort(samp, input_offset, d_chips_per_symbol);

                float sum_i       = 0.0f;
                float sum_q       = 0.0f;
                float mask_sq_sum = 0.0f;
                const int n_chips = std::min(d_chips_per_symbol, d_sequence_length);
                for (int chip = 0; chip < n_chips; ++chip) {
                    const std::uint8_t* base = ks + static_cast<std::size_t>(chip) * 8;
                    float                 mi = 0.0f;
                    float                 mq = 0.0f;
                    boxMullerPair(toUniform(base), toUniform(base + 4), mi, mq);
                    if (std::abs(mi) < kMinMask) {
                        mi = (mi >= 0 ? kMinMask : -kMinMask);
                    }
                    if (std::abs(mq) < kMinMask) {
                        mq = (mq >= 0 ? kMinMask : -kMinMask);
                    }
                    const float s_re = samp[input_offset + chip].real();
                    const float s_im = samp[input_offset + chip].imag();
                    sum_i += s_re * mi + s_im * mq;
                    sum_q += s_im * mi - s_re * mq;
                    mask_sq_sum += mi * mi + mq * mq;
                }
                {
                    const float             norm =
                        std::max(mask_sq_sum, 1e-6f);
                    const std::complex<float> raw_sym(sum_i / norm, sum_q / norm);
                    symOut[static_cast<std::size_t>(output_idx)] =
                        applyChannelEqualizationUnlocked(raw_sym);
                }

                const float peak = std::max(d_correlation_peak, 1e-6f);
                d_last_soft_metric            = best_corr / peak;

                const float phase = std::arg(despread);
                if (d_have_prev_corr) {
                    float dphi = phase - d_prev_corr_phase;
                    if (dphi > 3.14159265f) {
                        dphi -= 6.28318531f;
                    }
                    if (dphi < -3.14159265f) {
                        dphi += 6.28318531f;
                    }
                    d_freq_error_rad_per_sym = 0.9f * d_freq_error_rad_per_sym + 0.1f * dphi;
                } else {
                    d_have_prev_corr = true;
                }
                d_prev_corr_phase = phase;

            } else {
                const int max_offset = nAvail - d_chips_per_symbol;
                if (max_offset < 0) {
                    sl.unlock();
                    break;
                }

                const int despread_offset = std::max(0, std::min(max_offset, input_offset + d_timing_offset));

                d_prompt_correlation = std::abs(correlatePort(samp, input_offset, d_chips_per_symbol));
                std::complex<float> despread =
                    correlatePort(samp, despread_offset, d_chips_per_symbol);

                const int tol = std::min(3, d_timing_error_tolerance);
                std::array<int, 3> mf_e{};
                std::array<int, 3> mf_l{};
                std::array<float, 3> e_i{};
                std::array<float, 3> e_q{};
                std::array<float, 3> l_i{};
                std::array<float, 3> l_q{};
                for (int i = 0; i < tol; ++i) {
                    mf_e[static_cast<std::size_t>(i)] =
                        std::max(0, despread_offset - (i + 1));
                    mf_l[static_cast<std::size_t>(i)] =
                        std::min(max_offset, despread_offset + (i + 1));
                }

                float sum_i       = 0.0f;
                float sum_q       = 0.0f;
                float mask_sq_sum = 0.0f;
                const int n_chips = std::min(d_chips_per_symbol, d_sequence_length);
                for (int chip = 0; chip < n_chips; ++chip) {
                    const std::uint8_t* base = ks + static_cast<std::size_t>(chip) * 8;
                    float mi = 0.0f, mq = 0.0f;
                    boxMullerPair(toUniform(base), toUniform(base + 4), mi, mq);
                    if (std::abs(mi) < kMinMask) {
                        mi = (mi >= 0 ? kMinMask : -kMinMask);
                    }
                    if (std::abs(mq) < kMinMask) {
                        mq = (mq >= 0 ? kMinMask : -kMinMask);
                    }

                    const float s_re = samp[despread_offset + chip].real();
                    const float s_im = samp[despread_offset + chip].imag();
                    sum_i += s_re * mi + s_im * mq;
                    sum_q += s_im * mi - s_re * mq;

                    for (int i = 0; i < tol; ++i) {
                        const int eo = mf_e[static_cast<std::size_t>(i)] + chip;
                        const float er = samp[eo].real();
                        const float em = samp[eo].imag();
                        e_i[static_cast<std::size_t>(i)] += er * mi + em * mq;
                        e_q[static_cast<std::size_t>(i)] += em * mi - er * mq;

                        const int lo = mf_l[static_cast<std::size_t>(i)] + chip;
                        const float lr = samp[lo].real();
                        const float lm = samp[lo].imag();
                        l_i[static_cast<std::size_t>(i)] += lr * mi + lm * mq;
                        l_q[static_cast<std::size_t>(i)] += lm * mi - lr * mq;
                    }
                    mask_sq_sum += mi * mi + mq * mq;
                }

                float prompt_mf_power = 0.0f;
                {
                    const float norm_sq = std::max(mask_sq_sum * mask_sq_sum, 1e-12f);
                    float ep_sum        = 0.0f;
                    float lp_sum        = 0.0f;
                    for (int i = 0; i < tol; ++i) {
                        ep_sum +=
                            (e_i[static_cast<std::size_t>(i)] * e_i[static_cast<std::size_t>(i)]
                                + e_q[static_cast<std::size_t>(i)] * e_q[static_cast<std::size_t>(i)])
                            / norm_sq;
                        lp_sum +=
                            (l_i[static_cast<std::size_t>(i)] * l_i[static_cast<std::size_t>(i)]
                                + l_q[static_cast<std::size_t>(i)] * l_q[static_cast<std::size_t>(i)])
                            / norm_sq;
                    }
                    d_early_correlation = ep_sum;
                    d_late_correlation = lp_sum;
                    prompt_mf_power = (sum_i * sum_i + sum_q * sum_q) / norm_sq;
                }
                updateTiming(prompt_mf_power);

                {
                    const float norm = std::max(mask_sq_sum, 1e-6f);
                    const std::complex<float> raw_sym(sum_i / norm, sum_q / norm);
                    symOut[static_cast<std::size_t>(output_idx)] =
                        applyChannelEqualizationUnlocked(raw_sym);
                }

                updateLockDetection(d_prompt_correlation);
                updateSnrEstimate(despread, d_prompt_correlation);

                const float peak = std::max(d_correlation_peak, 1e-6f);
                d_last_soft_metric = d_prompt_correlation / peak;

                const float phase = std::arg(despread);
                if (d_have_prev_corr) {
                    float dphi = phase - d_prev_corr_phase;
                    if (dphi > 3.14159265f) {
                        dphi -= 6.28318531f;
                    }
                    if (dphi < -3.14159265f) {
                        dphi += 6.28318531f;
                    }
                    d_freq_error_rad_per_sym =
                        0.9f * d_freq_error_rad_per_sym + 0.1f * dphi;
                } else {
                    d_have_prev_corr = true;
                }
                d_prev_corr_phase = phase;
            }

            lockOut[static_cast<std::size_t>(output_idx)] = d_is_locked ? 1.0f : 0.0f;
            snrOut[static_cast<std::size_t>(output_idx)] = d_snr_db;
            sl.unlock();

            ++output_idx;
        }

        chipsConsumed = output_idx * d_chips_per_symbol;
        return Status::OK;
    }

private:
    void resetTrackingWithMutex() noexcept {
        std::lock_guard lk(d_mutex);
        resetTrackingUnlocked();
    }

    void resetTrackingUnlocked() noexcept {
        d_state                   = SyncState::Acquisition;
        d_code_phase              = 0;
        d_timing_offset           = 0;
        d_acquisition_counter     = 0;
        d_lock_counter            = 0;
        d_have_prev_corr          = false;
        d_freq_error_rad_per_sym  = 0.0f;
        d_timing_accum            = 0.0f;
        d_timing_error            = 0.0f;
        d_early_correlation       = 0.0f;
        d_prompt_correlation      = 0.0f;
        d_late_correlation        = 0.0f;
        d_is_locked               = false;
        d_correlation_peak        = 0.0f;
        d_correlation_avg         = 0.0f;
        d_signal_power            = 0.0f;
        d_noise_power             = 0.0f;
        d_snr_db                  = 0.0f;
        d_last_soft_metric        = 0.0f;
        d_channel_est             = std::complex<float>(1.0f, 0.0f);
    }

    void buildSequenceComplex(std::span<const float> spreading_sequence) {
        if (spreading_sequence.size() % 2UZ == 0UZ) {
            d_sequence_length = static_cast<int>(spreading_sequence.size()) / 2;
        } else {
            d_sequence_length = static_cast<int>(spreading_sequence.size());
        }
        d_spreading_sequence_complex.resize(static_cast<std::size_t>(d_sequence_length));
        if (spreading_sequence.size() % 2UZ == 0UZ) {
            for (int i = 0; i < d_sequence_length; ++i) {
                d_spreading_sequence_complex[static_cast<std::size_t>(i)] =
                    std::complex<float>(spreading_sequence[static_cast<std::size_t>(2 * i)],
                        spreading_sequence[static_cast<std::size_t>(2 * i + 1)]);
            }
        } else {
            for (int i = 0; i < d_sequence_length; ++i) {
                d_spreading_sequence_complex[static_cast<std::size_t>(i)] =
                    std::complex<float>(std::abs(spreading_sequence[static_cast<std::size_t>(i)]), 0.0f);
            }
        }
    }

    [[nodiscard]] std::complex<float> correlatePort(const std::complex<float>* samples, int offset, int length) noexcept {
        std::complex<float> sum{ 0.0f, 0.0f };
        const int           n =
            std::min(length, d_sequence_length);
        for (int i = 0; i < n; ++i) {
            const int seq_idx =
                (d_code_phase + i) % std::max(1, d_sequence_length);
            const std::complex<float> s   = samples[offset + i];
            const std::complex<float> seq =
                d_spreading_sequence_complex[static_cast<std::size_t>(seq_idx)];
            sum += s * std::conj(seq);
        }
        if (n > 0) {
            sum /= static_cast<float>(n);
        }
        return sum;
    }

    void updateTiming(float prompt_mf_power) noexcept {
        if (d_chips_per_symbol <= 1) {
            d_timing_error   = 0.0f;
            d_timing_offset  = 0;
            d_timing_accum   = 0.0f;
            return;
        }

        if (!d_channel_eq_enabled) {
            d_timing_error = 0.0f;
            d_timing_accum = 0.0f;
            d_timing_offset = 0;
            return;
        }

        constexpr float kHysteresis = 1.15f;
        constexpr float kGain     = 0.35f;
        const int       tol =
            std::min(3, d_timing_error_tolerance);

        float vote = 0.0f;

        float prompt_ref = static_cast<float>(tol) * prompt_mf_power;
        if (d_late_correlation > kHysteresis * prompt_ref &&
            d_late_correlation > d_early_correlation) {
            vote = +1.0f;
        } else if (d_early_correlation > kHysteresis * prompt_ref &&
                   d_early_correlation > d_late_correlation) {
            vote = -1.0f;
        }

        d_timing_error = 0.7f * d_timing_error + 0.3f * vote;
        d_timing_accum += d_timing_error * kGain;
        if (d_timing_accum > 0.5f) {
            d_timing_offset =
                std::min(d_timing_error_tolerance, d_timing_offset + 1);
            d_timing_accum -= 1.0f;
        } else if (d_timing_accum < -0.5f) {
            d_timing_offset =
                std::max(-d_timing_error_tolerance, d_timing_offset - 1);
            d_timing_accum += 1.0f;
        }
    }

    void updateLockDetection(float correlation) noexcept {
        const float corr_mag = std::abs(correlation);
        d_correlation_avg = 0.9f * d_correlation_avg + 0.1f * corr_mag;
        if (corr_mag > d_correlation_peak) {
            d_correlation_peak = corr_mag;
        }
        const float peak = std::max(d_correlation_peak, 1e-3f);
        const float rel = d_correlation_avg / peak;
        const float adaptive = std::max(kAdaptiveThreshMin, d_correlation_threshold * rel);

        if (corr_mag > adaptive) {
            d_lock_counter++;
            if (d_lock_counter >= kLockThresh) {
                d_is_locked = true;
                if (d_state == SyncState::Acquisition) {
                    d_state = SyncState::Tracking;
                }
                if (d_state == SyncState::Tracking && d_lock_counter >= kLockThresh * 2) {
                    d_state = SyncState::Locked;
                }
            }
        } else {
            d_lock_counter = std::max(0, d_lock_counter - 1);
            if (d_lock_counter == 0 && d_state == SyncState::Locked) {
                d_state       = SyncState::Tracking;
                d_is_locked   = false;
            }
        }
    }

    void updateSnrEstimate(std::complex<float> symbol, float correlation) noexcept {
        const float symbol_power =
            std::norm(symbol);
        const float corr_mag = std::abs(correlation);

        d_signal_power = 0.95f * d_signal_power + 0.05f * corr_mag * corr_mag;

        const float noise_est = std::max(0.0f, symbol_power - d_signal_power);
        d_noise_power = 0.95f * d_noise_power + 0.05f * noise_est;

        if (d_noise_power > 0.0f) {
            d_snr_db = 10.0f * std::log10(d_signal_power / d_noise_power);
        } else {
            d_snr_db = 100.0f;
        }
    }

    [[nodiscard]] std::complex<float> applyChannelEqualizationUnlocked(std::complex<float> raw_sym) noexcept {
        if (!d_channel_eq_enabled) {
            return raw_sym;
        }
        constexpr float kAlpha = 0.05f;
        constexpr float kPwGate = 0.25f;

        float h_mag_sq = std::norm(d_channel_est);
        std::complex<float> out_sym;
        if (h_mag_sq > 1e-10f) {
            out_sym = raw_sym * std::conj(d_channel_est) / h_mag_sq;
        } else {
            out_sym = raw_sym;
        }

        if (std::norm(raw_sym) > kPwGate) {
            const float decision = (out_sym.real() >= 0.0f) ? 1.0f : -1.0f;
            d_channel_est        = d_channel_est * (1.0f - kAlpha)
                + raw_sym * (decision * kAlpha);
        }
        return out_sym;
    }

    static void boxMullerPair(float u1, float u2, float& g0, float& g1) noexcept {
        if (u1 < 1e-10f) {
            u1 = 1e-10f;
        }
        const float radius =
            std::sqrt(-2.0f * std::log(u1));
        const float angle = 2.0f * static_cast<float>(M_PI) * u2;
        g0                  = radius * std::cos(angle);
        g1                  = radius * std::sin(angle);
    }

    std::vector<std::complex<float>> d_spreading_sequence_complex{};
    int                              d_sequence_length{ 1 };
    int                              d_chips_per_symbol{ 256 };
    float                            d_correlation_threshold{ 0.5f };
    int                              d_timing_error_tolerance{ 3 };

    SyncState           d_state{ SyncState::Acquisition };
    int                 d_code_phase{ 0 };
    int                 d_timing_offset{ 0 };
    int                 d_acquisition_counter{ 0 };
    int                 d_lock_counter{ 0 };

    float d_early_correlation{ 0 };
    float d_prompt_correlation{ 0 };
    float d_late_correlation{ 0 };
    float d_timing_error{ 0 };
    float d_timing_accum{ 0 };

    float d_correlation_peak{ 0 };
    float d_correlation_avg{ 0 };
    bool d_is_locked{ false };

    float d_signal_power{ 0 };
    float d_noise_power{ 0 };
    float d_snr_db{ 0 };

    float d_last_soft_metric{ 0 };

    std::complex<float> d_channel_est{ 1.0f, 0.0f };
    bool               d_channel_eq_enabled{ false };

    float d_freq_error_rad_per_sym{ 0 };
    float d_prev_corr_phase{ 0 };
    bool d_have_prev_corr{ false };

    mutable std::mutex d_mutex{};
    mutable std::mutex d_key_mutex{};

    std::array<std::uint8_t, 32> d_key{};
    std::array<std::uint8_t, 12> d_nonce{};
    std::uint64_t d_counter{ 0 };
    std::atomic<bool>           d_key_armed{ false };
    std::array<std::uint8_t, 64> d_ks_remainder{};
    std::size_t                  d_ks_remainder_len{ 0 };
    std::vector<std::uint8_t> d_ks_buf{};
    std::atomic<bool>         d_overflow{ false };
};

} // namespace gnuradio4::kgdss::detail

#endif
