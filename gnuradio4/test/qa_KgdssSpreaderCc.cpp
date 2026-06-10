// SPDX-License-Identifier: GPL-3.0-or-later
#include <boost/ut.hpp>
#include <gnuradio-4.0/Block.hpp>
#include <gnuradio-4.0/Port.hpp>
#include <gnuradio-4.0/Sequence.hpp>
#include <gnuradio-4.0/Tag.hpp>
#include <gnuradio-4.0/Tensor.hpp>
#include <gnuradio-4.0/Value.hpp>
#include <gnuradio-4.0/kgdss/KgdssSpreaderCc.hpp>
#include <gnuradio-4.0/kgdss/detail/SpreaderEngine.hpp>

#include <array>
#include <cmath>
#include <complex>
#include <cstdint>
#include <numeric>
#include <string>
#include <string_view>
#include <thread>
#include <vector>

#include <sodium.h>

using namespace boost::ut;

namespace {

[[nodiscard]] constexpr int stN(gr::work::Status st) noexcept {
    return static_cast<int>(st);
}

void notify(gr::MsgPortOut& downstream, gr::property_map&& body) {
    gr::Message msg;
    msg.cmd  = gr::message::Command::Notify;
    msg.data = std::move(body);
    auto writer = downstream.streamWriter().template reserve<gr::SpanReleasePolicy::ProcessAll>(1UZ);
    writer[0]   = std::move(msg);
    writer.publish(1UZ);
}

gr::Tensor<std::uint8_t> makeNonce(std::uint8_t base = 1) {
    std::vector<std::uint8_t> v(12);
    std::iota(v.begin(), v.end(), base);
    return gr::Tensor<std::uint8_t>(std::move(v));
}

} // namespace

const suite<"KgdssSpreaderCc"> SpreaderSuite = [] {
    "engine_without_key"_test = [] {
        gnuradio4::kgdss::detail::SpreaderEngine eng;
        eng.generateSequence(8, 1.F, 101U);
        std::vector<std::complex<float>> syms(2, { 1.F, -1.F });
        const int                        sf = 24;
        std::vector<std::complex<float>> chips(static_cast<std::size_t>(syms.size() * static_cast<std::size_t>(sf)));
        std::size_t                      w = 0;
        expect(eq(stN(eng.process(std::span(syms), std::span(chips), sf, 1.F, 8, w)), stN(gr::work::Status::INSUFFICIENT_INPUT_ITEMS)));
    };

    "engine_after_key"_test = [] {
        expect(::sodium_init() >= 0);
        gnuradio4::kgdss::detail::SpreaderEngine eng;
        eng.generateSequence(8, 1.F, 7U);
        std::array<std::uint8_t, 32> key{};
        key[0] = 0x5A;
        constexpr std::array<std::uint8_t, 12> nonce{};
        eng.setKeyMaterial(key, nonce);
        std::vector<std::complex<float>> syms{ { 1.F, 0.25F } };
        const int                        sf = 32;
        std::vector<std::complex<float>> out(static_cast<std::size_t>(sf));
        std::size_t                      w = 0;
        expect(eq(stN(eng.process(std::span(syms), std::span(out), sf, 1.F, 8, w)), stN(gr::work::Status::OK)));
        float n = 0.F;
        for (auto& z : out) {
            n += std::norm(z);
        }
        expect(gt(n, 1e-8F));
    };

    "reject_short_key_tensor"_test = [] {
        expect(::sodium_init() >= 0);
        gnuradio4::kgdss::KgdssSpreaderCc block(gr::property_map{ { "name", std::string("sp") },
            { "spreading_factor", 16 }, { "sequence_length", 8 }, { "variance", 1.0 }, { "seed", 4U } });
        block.init(std::make_shared<gr::Sequence>());
        block.start();
        std::vector<std::uint8_t> bad(31U, 9U);
        gr::property_map          pm;
        pm[gr::convert_string_domain(std::string_view("key"))] = gr::pmt::Value(gr::Tensor<std::uint8_t>(std::move(bad)));
        pm[gr::convert_string_domain(std::string_view("nonce"))] = gr::pmt::Value(makeNonce());
        gr::MsgPortOut             down;
        expect(down.connect(block.set_key).has_value());
        notify(down, std::move(pm));
        block.processScheduledMessages();
        expect(eq(block.key_armed.value, false));
        std::vector<std::complex<float>> ins{ { 1.F, 0.F } };
        std::vector<std::complex<float>> outs(16);
        expect(eq(stN(block.processBulk(std::span(ins), std::span(outs))), stN(gr::work::Status::INSUFFICIENT_INPUT_ITEMS)));
    };

    "valid_set_key_outputs"_test = [] {
        expect(::sodium_init() >= 0);
        gnuradio4::kgdss::KgdssSpreaderCc block(gr::property_map{ { "name", std::string("sp2") },
            { "spreading_factor", 16 }, { "sequence_length", 8 }, { "variance", 1.0 }, { "seed", 6U } });
        block.init(std::make_shared<gr::Sequence>());
        block.start();
        std::vector<std::uint8_t> kb(32U, 0xC0U);
        gr::property_map          pm;
        pm[gr::convert_string_domain(std::string_view("key"))] = gr::pmt::Value(gr::Tensor<std::uint8_t>(std::move(kb)));
        pm[gr::convert_string_domain(std::string_view("nonce"))] = gr::pmt::Value(makeNonce(2));
        gr::MsgPortOut             down;
        expect(down.connect(block.set_key).has_value());
        notify(down, std::move(pm));
        block.processScheduledMessages();
        expect(eq(block.key_armed.value, true));
        std::vector<std::complex<float>> ins{ { 1.F, 0.F } };
        std::vector<std::complex<float>> outs(16);
        expect(eq(stN(block.processBulk(std::span(ins), std::span(outs))), stN(gr::work::Status::OK)));
    };

    "mask_determinism_reset_counter"_test = [] {
        expect(::sodium_init() >= 0);
        std::array<std::uint8_t, 32> key{};
        key.fill(0x42U);
        std::array<std::uint8_t, 12> nonce{};
        nonce.fill(0x18U);
        auto run = [&]() {
            gnuradio4::kgdss::detail::SpreaderEngine eng;
            eng.setKeyMaterial(key, nonce);
            eng.generateSequence(8, 1.F, 99U);
            std::vector<std::complex<float>> syms{ { 3.F, -1.F } };
            const int                        sf = 40;
            std::vector<std::complex<float>> chips(static_cast<std::size_t>(sf));
            std::size_t                      w = 0;
            expect(eq(stN(eng.process(std::span(syms), std::span(chips), sf, 1.F, 8, w)), stN(gr::work::Status::OK)));
            return chips;
        };
        const auto a = run();
        const auto b = run();
        float      err = 0.F;
        expect(eq(a.size(), b.size()));
        for (std::size_t i = 0; i < a.size(); ++i) {
            err += std::abs(a[i].real() - b[i].real()) + std::abs(a[i].imag() - b[i].imag());
        }
        expect(lt(err, 1e-5F));
    };

    "gaussian_mask_statistics"_test = [] {
        expect(::sodium_init() >= 0);
        gnuradio4::kgdss::detail::SpreaderEngine eng;
        std::array<std::uint8_t, 32> key{};
        key.fill(0xA1U);
        std::array<std::uint8_t, 12> nonce{};
        nonce.fill(0xB2U);
        eng.setKeyMaterial(key, nonce);
        eng.generateSequence(32, 1.F, 15U);
        double        sumR = 0.;
        double        sumI = 0.;
        double        sumSq = 0.;
        std::uint64_t cnt = 0;
        const int     batches = 280;
        const int     sf = 64;
        for (int b = 0; b < batches; ++b) {
            std::vector<std::complex<float>> syms{ { 1.F, 0.F } };
            std::vector<std::complex<float>> chips(static_cast<std::size_t>(sf));
            std::size_t                      w = 0;
            expect(eq(stN(eng.process(std::span(syms), std::span(chips), sf, 1.F, 32, w)), stN(gr::work::Status::OK)));
            for (auto& z : chips) {
                sumR += static_cast<double>(z.real());
                sumI += static_cast<double>(z.imag());
                sumSq += static_cast<double>(z.real() * z.real() + z.imag() * z.imag());
                ++cnt;
            }
        }
        const double inv = 1.0 / static_cast<double>(cnt);
        const double mR = sumR * inv;
        const double mI = sumI * inv;
        /* With symbol (1,0), chip equals mask_i + i mask_q each with variance=1, hence E|z|^2 ~ 2. */
        const double var = sumSq * inv - (mR * mR + mI * mI);
        expect(lt(std::abs(mR), 0.13));
        expect(lt(std::abs(mI), 0.13));
        expect(lt(std::abs(var - 2.0), 0.35));
    };

    "mutex_stress_set_key_and_process"_test = [] {
        expect(::sodium_init() >= 0);
        gnuradio4::kgdss::detail::SpreaderEngine eng;
        eng.generateSequence(8, 1.F, 2U);
        std::array<std::uint8_t, 32> k1{};
        k1[0] = 3;
        std::array<std::uint8_t, 32> k2{};
        k2[31] = 7;
        constexpr std::array<std::uint8_t, 12> n1{};
        std::array<std::uint8_t, 12>           n2{};
        n2[10] = 0xEE;
        auto thr = [&]() {
            for (int i = 0; i < 480; ++i) {
                if (i % 2 == 0) {
                    eng.setKeyMaterial(k1, n1);
                } else {
                    eng.setKeyMaterial(k2, n2);
                }
            }
        };
        std::thread t(thr);
        for (int i = 0; i < 520; ++i) {
            std::vector<std::complex<float>> syms{ { 1.F, 1.F } };
            std::vector<std::complex<float>> chips(48);
            std::size_t                      w = 0;
            (void)eng.process(std::span(syms), std::span(chips), 48, 1.F, 8, w);
        }
        t.join();
    };
};

int main() {
    return boost::ut::cfg<boost::ut::override>.run();
}
