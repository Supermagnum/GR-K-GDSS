// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef GNURADIO4_KGDSS_KGDSS_DESPREADER_CC_HPP
#define GNURADIO4_KGDSS_KGDSS_DESPREADER_CC_HPP

#include <gnuradio-4.0/Block.hpp>
#include <gnuradio-4.0/BlockRegistry.hpp>
#include <gnuradio-4.0/Message.hpp>
#include <gnuradio-4.0/Port.hpp>
#include <gnuradio-4.0/Tag.hpp>
#include <gnuradio-4.0/Tensor.hpp>
#include <gnuradio-4.0/annotated.hpp>
#include <gnuradio-4.0/kgdss/detail/DespreaderEngine.hpp>
#include <gnuradio-4.0/kgdss/detail/Helpers.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <complex>
#include <cstring>
#include <cstdint>

#include <sodium.h>

namespace gnuradio4::kgdss {

GR_REGISTER_BLOCK(gnuradio4::kgdss::KgdssDespreaderCc)

struct KgdssDespreaderCc :
    gr::Block<KgdssDespreaderCc, gr::Resampling<256UZ, 1UZ, false>, gr::NoTagPropagation> {

    using Description = gr::Doc<"Keyed GDSS despreader (matched-filter inversion of spreader)."
                                " No symbol output until a valid key/nonce arrives on `set_key`.">;

    gr::PortIn<std::complex<float>>  in{};
    gr::PortOut<std::complex<float>> sym{};
    gr::PortOut<float>               lock{};
    gr::PortOut<float>               snr{};

    gr::MsgPortIn set_key{};
    gr::MsgPortIn set_counter{};

    gr::Annotated<gr::Tensor<float>, "spreading_sequence", gr::Doc<"IQ interleaved length 2*L or magnitude length L">> spreading_sequence{};
    gr::Annotated<int, "spreading_factor", gr::Doc<"chips per input symbol">>                   spreading_factor         = 256;
    gr::Annotated<float, "correlation_threshold", gr::Doc<"base lock correlator threshold">>    correlation_threshold   = 0.5f;
    gr::Annotated<int, "timing_error_tolerance", gr::Doc<"max chip timing skew">> timing_error_tolerance = 3;
    gr::Annotated<bool, "channel_equalization",
        gr::Doc<"decision-directed equalization (BPSK assumption); enables MF timing peak tracker">>                          channel_equalization = false;

    gr::Annotated<bool, "key_armed", gr::Visible, gr::Doc<"read-only: cryptographic key armed">> key_armed = false;

    GR_MAKE_REFLECTABLE(KgdssDespreaderCc,
        in,
        sym,
        lock,
        snr,
        set_key,
        set_counter,
        spreading_sequence,
        spreading_factor,
        correlation_threshold,
        timing_error_tolerance,
        channel_equalization,
        key_armed);

    detail::DespreaderEngine _engine{};
    std::size_t              _noKeySilentWarn{ 0 };

    void syncResamplingFactors() noexcept {
        const int sf = std::max(1, spreading_factor.value);
        this->input_chunk_size = gr::Size_t(sf);
        this->output_chunk_size = gr::Size_t(1);
    }

    void applySequenceOrStop() noexcept {
        if (spreading_sequence.value.size() == 0UZ) {
            this->requestStop();
            return;
        }
        try {
            const auto seqView = spreading_sequence.value.data_span();
            _engine.configureFromSpreadingSequence(
                seqView,
                std::max(1, spreading_factor.value),
                correlation_threshold.value,
                timing_error_tolerance.value);
        } catch (...) {
            this->requestStop();
        }
        _engine.setChannelEqualization(channel_equalization.value);
    }

    void start() noexcept {
        if (::sodium_init() < 0) {
            this->requestStop();
            return;
        }
        syncResamplingFactors();
        applySequenceOrStop();
    }

    void settingsChanged(const gr::property_map&, const gr::property_map& ns) noexcept {
        if (ns.contains("spreading_factor")) {
            syncResamplingFactors();
            try {
                _engine.applyChipsSettings(std::max(1, spreading_factor.value));
            } catch (...) {
                requestStop();
            }
        }
        if (ns.contains("spreading_sequence") || ns.contains("correlation_threshold") || ns.contains("timing_error_tolerance")) {
            applySequenceOrStop();
        }
        if (ns.contains("channel_equalization")) {
            _engine.setChannelEqualization(channel_equalization.value);
        }
    }

    [[nodiscard]] gr::work::Status processBulk(std::span<const std::complex<float>> in, std::span<std::complex<float>> symOut,
        std::span<float>                                                                   lockOut,
        std::span<float>                                                                 snrOut) noexcept {
        key_armed.value = _engine.keyArmed();
        const int sf = std::max(1, spreading_factor.value);
        if (sf <= 0) {
            return gr::work::Status::ERROR;
        }
        const std::size_t inSz =
            static_cast<std::size_t>(in.size());
        if (inSz % static_cast<std::size_t>(sf) != 0UZ) {
            return gr::work::Status::ERROR;
        }
        const std::size_t expectedSymbols =
            inSz / static_cast<std::size_t>(sf);
        if (symOut.size()
            < expectedSymbols || lockOut.size() < expectedSymbols || snrOut.size()
            < expectedSymbols) {
            return gr::work::Status::ERROR;
        }
        int                   chipsUsed = 0;
        const gr::work::Status st      = _engine.process(in,
            symOut.first(expectedSymbols),
            lockOut.first(expectedSymbols),
            snrOut.first(expectedSymbols),
            chipsUsed,
            _noKeySilentWarn);

        if (st != gr::work::Status::OK) {
            const std::size_t nSym =
                std::min(expectedSymbols, symOut.size());
            const std::size_t nl = std::min(expectedSymbols, lockOut.size());
            const std::size_t nn =
                std::min(expectedSymbols, snrOut.size());
            std::fill(symOut.begin(), symOut.begin() + static_cast<std::ptrdiff_t>(nSym), std::complex<float>{});
            std::fill(lockOut.begin(), lockOut.begin() + static_cast<std::ptrdiff_t>(nl), 0.F);
            std::fill(snrOut.begin(), snrOut.begin() + static_cast<std::ptrdiff_t>(nn), 0.F);
            key_armed.value = _engine.keyArmed();
            return st;
        }

        key_armed.value = _engine.keyArmed();
        (void)chipsUsed;
        return st;
    }

    static bool copyKeyNonceFromDict(const gr::property_map& body, std::array<std::uint8_t, 32>& key,
        std::array<std::uint8_t, 12>&                                                                   nonce) noexcept {
        return detail::copyBytesFromMap(body, "key",   key.data(),   32UZ)
            && detail::copyBytesFromMap(body, "nonce", nonce.data(), 12UZ);
    }

    void handleSetKey(const gr::Message& message) noexcept {
        if (!message.data.has_value()) {
            return;
        }
        std::array<std::uint8_t, 32> key{};
        std::array<std::uint8_t, 12> nonce{};
        if (!copyKeyNonceFromDict(message.data.value(), key, nonce)) {
            detail::DespreaderEngine::rejectKeyWithLog("dict");
            key_armed.value = false;
            return;
        }
        _engine.setKeyMaterial(key, nonce);
        key_armed.value = true;
    }

    void handleSetCounter(const gr::Message& message) noexcept {
        if (!message.data.has_value()) {
            return;
        }
        auto ctr = detail::scalarUint64FromMap(message.data.value(), "counter");
        if (!ctr) {
            ctr = detail::counterFromMessagePayload(message.data);
        }
        if (ctr) {
            _engine.setCounter(*ctr);
        }
    }

    void processMessages(gr::MsgPortIn& port, std::span<const gr::Message> messages) {
        if (std::addressof(port) == std::addressof(set_key)) {
            for (const gr::Message& m : messages) {
                handleSetKey(m);
            }
        } else if (std::addressof(port) == std::addressof(set_counter)) {
            for (const gr::Message& m : messages) {
                handleSetCounter(m);
            }
        }
    }
};

} // namespace gnuradio4::kgdss

#endif
