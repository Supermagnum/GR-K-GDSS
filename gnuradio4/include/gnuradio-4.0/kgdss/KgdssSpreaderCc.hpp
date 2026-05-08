// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef GNURADIO4_KGDSS_KGDSS_SPREADER_CC_HPP
#define GNURADIO4_KGDSS_KGDSS_SPREADER_CC_HPP

#include <gnuradio-4.0/Block.hpp>
#include <gnuradio-4.0/BlockRegistry.hpp>
#include <gnuradio-4.0/Message.hpp>
#include <gnuradio-4.0/Port.hpp>
#include <gnuradio-4.0/Tag.hpp>
#include <gnuradio-4.0/Tensor.hpp>
#include <gnuradio-4.0/annotated.hpp>
#include <gnuradio-4.0/kgdss/detail/Helpers.hpp>
#include <gnuradio-4.0/kgdss/detail/SpreaderEngine.hpp>

#include <algorithm>
#include <array>
#include <complex>
#include <cstring>
#include <cstdint>

#include <sodium.h>

namespace gnuradio4::kgdss {

GR_REGISTER_BLOCK(gnuradio4::kgdss::KgdssSpreaderCc)

struct KgdssSpreaderCc : gr::Block<KgdssSpreaderCc, gr::Resampling<1UZ, 256UZ, false>, gr::NoTagPropagation> {
    using Description = gr::Doc<"Keyed GDSS spreader (ChaCha20-driven Gaussian mask via Box-Muller). No output until a "
                                "valid 32-byte key and 12-byte nonce are armed via message port `set_key`.">;

    gr::PortIn<std::complex<float>>  in{};
    gr::PortOut<std::complex<float>> out{};

    gr::MsgPortIn                      set_key{};
    gr::MsgPortIn                      set_counter{};

    gr::Annotated<int, "sequence_length", gr::Doc<"gold / amplitude sequence internal length">>          sequence_length  = 256;
    gr::Annotated<int, "spreading_factor", gr::Doc<"chips per output symbol">>                            spreading_factor = 256;
    gr::Annotated<float, "variance", gr::Doc<"Gaussian mask variance scaling">> variance                 = 1.0f;
    gr::Annotated<unsigned int, "seed", gr::Doc<"RNG seed for internal sequence generator; 0 = time">>     seed             = 0U;
    gr::Annotated<bool, "key_armed", gr::Visible, gr::Doc<"read-only: cryptographic key armed">>          key_armed        = false;

    GR_MAKE_REFLECTABLE(KgdssSpreaderCc, in, out, set_key, set_counter, sequence_length, spreading_factor, variance, seed, key_armed);

    detail::SpreaderEngine _engine{};
    std::size_t            _noKeySilentWarn{ 0 };

    void syncResamplingFactors() noexcept {
        this->input_chunk_size = gr::Size_t(1);
        this->output_chunk_size = gr::Size_t(static_cast<gr::Size_t>(std::max(1, spreading_factor.value)));
    }

    void start() noexcept {
        if (::sodium_init() < 0) {
            this->requestStop();
            return;
        }
        if (sequence_length.value <= 0 || spreading_factor.value <= 0 || variance.value <= 0.0f) {
            this->requestStop();
            return;
        }
        syncResamplingFactors();
        _engine.generateSequence(sequence_length.value, variance.value, seed.value);
    }

    void settingsChanged(const gr::property_map&, const gr::property_map& newSettings) noexcept {
        if (newSettings.contains("spreading_factor")) {
            syncResamplingFactors();
        }
        if (newSettings.contains("sequence_length") || newSettings.contains("variance") || newSettings.contains("seed")) {
            if (sequence_length.value > 0 && variance.value > 0.0f) {
                _engine.generateSequence(sequence_length.value, variance.value, seed.value);
            }
        }
    }

    [[nodiscard]] gr::work::Status processBulk(std::span<const std::complex<float>> input, std::span<std::complex<float>> output) noexcept {
        key_armed.value = _engine.keyArmed();
        if (static_cast<std::size_t>(spreading_factor.value) * input.size() != output.size()) {
            return gr::work::Status::ERROR;
        }
        const auto st =
            _engine.process(input,
                output,
                spreading_factor.value,
                variance.value,
                sequence_length.value,
                _noKeySilentWarn);
        if (st != gr::work::Status::OK) {
            if (output.size() > 0) {
                std::fill(output.begin(), output.end(), std::complex<float>{});
            }
        }
        key_armed.value = _engine.keyArmed();
        return st;
    }

    static bool copyKeyNonceFromDict(const gr::property_map& body, std::array<std::uint8_t, 32>& key,
        std::array<std::uint8_t, 12>&                                                                   nonce) noexcept {
        return detail::copyBytesFromMap(body, "key",   key.data(),   32UZ)
            && detail::copyBytesFromMap(body, "nonce", nonce.data(), 12UZ);
    }

    void handleSetKey(gr::MsgPortIn& port, const gr::Message& message) noexcept {
        if (!message.data.has_value()) {
            return;
        }
        const gr::property_map&               body = message.data.value();
        std::array<std::uint8_t, 32>          key{};
        std::array<std::uint8_t, 12>          nonce{};
        if (!copyKeyNonceFromDict(body, key, nonce)) {
            detail::SpreaderEngine::rejectKeyWithLog();
            key_armed.value = false;
            return;
        }
        _engine.setKeyMaterial(key, nonce);
        _engine.generateSequence(sequence_length.value, variance.value, seed.value);
        key_armed.value = true;
    }

    void handleSetCounter(gr::MsgPortIn& port, const gr::Message& message) noexcept {
        (void)port;
        if (!message.data.has_value()) {
            return;
        }
        auto ctr =
            detail::scalarUint64FromMap(message.data.value(), "counter");
        if (!ctr.has_value()) {
            ctr = detail::counterFromMessagePayload(message.data);
        }
        if (ctr.has_value()) {
            _engine.setCounter(*ctr);
        }
    }

    void processMessages(gr::MsgPortIn& port, std::span<const gr::Message> messages) {
        if (messages.empty()) [[unlikely]] {
            return;
        }
        if (std::addressof(port) == std::addressof(set_key)) {
            for (const gr::Message& m : messages) {
                handleSetKey(port, m);
            }
        } else if (std::addressof(port) == std::addressof(set_counter)) {
            for (const gr::Message& m : messages) {
                handleSetCounter(port, m);
            }
        }
    }
};

} // namespace gnuradio4::kgdss

#endif
