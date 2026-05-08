// SPDX-License-Identifier: GPL-3.0-or-later
#include <boost/ut.hpp>
#include <gnuradio-4.0/Block.hpp>
#include <gnuradio-4.0/Tensor.hpp>
#include <gnuradio-4.0/kgdss/KgdssDespreaderCc.hpp>
#include <gnuradio-4.0/kgdss/detail/DespreaderEngine.hpp>
#include <gnuradio-4.0/kgdss/detail/SpreaderEngine.hpp>

#include <array>
#include <cmath>
#include <complex>
#include <numeric>
#include <random>
#include <vector>

#include <sodium.h>

using namespace boost::ut;

namespace {

[[nodiscard]] constexpr int stN(gr::work::Status st) noexcept {
    return static_cast<int>(st);
}

[[nodiscard]] std::vector<float> pnIq(int L, float variance, unsigned seed) {
    std::mt19937                    rng(seed == 0U ? 5003U : seed);
    std::normal_distribution<float> g(0.F, std::sqrt(variance));
    std::vector<float>              r(static_cast<std::size_t>(2 * L));
    for (int i = 0; i < L; ++i) {
        float u       = std::abs(g(rng));
        float v       = std::abs(g(rng));
        r[static_cast<std::size_t>(2 * i)]     = u;
        r[static_cast<std::size_t>(2 * i + 1)] = v;
    }
    return r;
}

std::array<std::uint8_t, 32> fillKey(std::uint8_t v) {
    std::array<std::uint8_t, 32> k{};
    k.fill(v);
    return k;
}

} // namespace

suite<"KgdssDespreaderCc"> DespreaderSuite = [] {
    "despreader_engine_blocks_without_key"_test = [] {
        auto                          pn = pnIq(16, 1.F, 303U);
        gnuradio4::kgdss::detail::DespreaderEngine de;
        de.configureFromSpreadingSequence(std::span(pn), 24, 0.4F, 3);
        std::vector<std::complex<float>> chips(24, { 1.F, 0.F });
        std::vector<std::complex<float>> sym(1);
        std::vector<float>               lk(1), sn(1);
        int                              used = 0;
        std::size_t                      w    = 0;
        expect(eq(stN(de.process(std::span(chips), std::span(sym), std::span(lk), std::span(sn), used, w)),
            stN(gr::work::Status::INSUFFICIENT_INPUT_ITEMS)));
    };

    "round_trip_spread_then_despread"_test = [] {
        expect(::sodium_init() >= 0);
        const int      L    = 24;
        const unsigned seed = 808U;
        const float    var  = 1.F;
        const int      sf   = 32;
        auto           iq   = pnIq(L, var, seed);

        gnuradio4::kgdss::detail::SpreaderEngine sp;
        sp.generateSequence(L, var, seed);
        auto                          key   = fillKey(0xD1U);
        constexpr std::array<std::uint8_t, 12> nonce{};
        sp.setKeyMaterial(key, nonce);

        gnuradio4::kgdss::detail::DespreaderEngine de;
        de.configureFromSpreadingSequence(std::span(iq), sf, 0.45F, 3);
        de.setKeyMaterial(key, nonce);

        std::complex<float>              sent(1.F, 0.F);
        std::vector<std::complex<float>> inSym{ sent };
        std::vector<std::complex<float>> chips(static_cast<std::size_t>(sf));
        std::size_t                      w = 0;
        expect(eq(stN(sp.process(std::span(inSym), std::span(chips), sf, var, L, w)), stN(gr::work::Status::OK)));

        std::vector<std::complex<float>> outSym(1);
        std::vector<float>               lock(1), snr(1);
        int                              used = 0;
        w                                       = 0;
        expect(eq(stN(de.process(std::span(chips), std::span(outSym), std::span(lock), std::span(snr), used, w)),
            stN(gr::work::Status::OK)));

        float err =
            std::abs(outSym[0].real() - sent.real()) + std::abs(outSym[0].imag() - sent.imag());
        expect(lt(err, 0.2F));
    };

    "wrong_key_produces_large_error_vs_sent"_test = [] {
        expect(::sodium_init() >= 0);
        const int      L = 16;
        const unsigned sd = 55U;
        const int      sf = 28;
        auto           iq = pnIq(L, 1.F, sd);

        gnuradio4::kgdss::detail::SpreaderEngine sp;
        sp.generateSequence(L, 1.F, sd);
        auto kG = fillKey(0x10U);
        std::array<std::uint8_t, 12> nG{};
        nG.fill(3U);
        sp.setKeyMaterial(kG, nG);

        std::complex<float>              sym(1.F, 0.F);
        std::vector<std::complex<float>> svec{ sym };
        std::vector<std::complex<float>> chips(static_cast<std::size_t>(sf));
        std::size_t                      w = 0;
        expect(eq(stN(sp.process(std::span(svec), std::span(chips), sf, 1.F, L, w)), stN(gr::work::Status::OK)));

        gnuradio4::kgdss::detail::DespreaderEngine okd;
        okd.configureFromSpreadingSequence(std::span(iq), sf, 0.35F, 3);
        okd.setKeyMaterial(kG, nG);

        gnuradio4::kgdss::detail::DespreaderEngine bad;
        bad.configureFromSpreadingSequence(std::span(iq), sf, 0.35F, 3);
        auto kB = fillKey(0xEFU);
        bad.setKeyMaterial(kB, nG);

        std::vector<std::complex<float>> gSym(1), bSym(1);
        std::vector<float>               lock1(1), snr1(1), lock2(1), snr2(1);
        int                              c1 = 0, c2 = 0;
        w = 0;
        expect(eq(stN(okd.process(std::span(chips), std::span(gSym), std::span(lock1), std::span(snr1), c1, w)),
            stN(gr::work::Status::OK)));
        w = 0;
        expect(eq(stN(bad.process(std::span(chips), std::span(bSym), std::span(lock2), std::span(snr2), c2, w)),
            stN(gr::work::Status::OK)));

        float gErr = std::abs(gSym[0].real() - sym.real()) + std::abs(gSym[0].imag() - sym.imag());
        float bErr = std::abs(bSym[0].real() - sym.real()) + std::abs(bSym[0].imag() - sym.imag());
        expect(lt(gErr, 0.25F));
        expect(gt(bErr, gErr + 1e-2F));
    };

    "channel_equalization_toggle"_test = [] {
        auto pn = pnIq(16, 1.F, 909U);
        gnuradio4::kgdss::detail::DespreaderEngine de;
        de.configureFromSpreadingSequence(std::span(pn), 16, 0.4F, 3);
        de.setChannelEqualization(true);
        expect(eq(de.getChannelEqualization(), true));
        de.setChannelEqualization(false);
        expect(eq(de.getChannelEqualization(), false));
    };

    "despreader_block_insufficient_when_unarmed"_test = [] {
        expect(::sodium_init() >= 0);
        auto pn                           = pnIq(10, 1.F, 414U);
        gr::Tensor<float>                 ten(std::move(pn));
        gnuradio4::kgdss::KgdssDespreaderCc blk(gr::property_map{ { "name", std::string("dsp") },
            { "spreading_factor", 16 }, { "spreading_sequence", ten }, { "correlation_threshold", 0.5F },
            { "timing_error_tolerance", 2 }, { "channel_equalization", false } });
        blk.init(std::make_shared<gr::Sequence>());
        blk.start();
        std::vector<std::complex<float>> in(16, { 1.F, 0.F });
        std::vector<std::complex<float>> osym(1);
        std::vector<float>               olk(1), osnr(1);
        expect(
            eq(stN(blk.processBulk(std::span(in), std::span(osym), std::span(olk), std::span(osnr))),
                stN(gr::work::Status::INSUFFICIENT_INPUT_ITEMS)));
    };

    "timing_offset_zero_when_equalizer_disabled"_test = [] {
        auto pn = pnIq(20, 1.F, 222U);
        gnuradio4::kgdss::detail::DespreaderEngine de;
        de.configureFromSpreadingSequence(std::span(pn), 20, 0.4F, 3);
        de.setChannelEqualization(false);
        expect(eq(de.timingOffset(), 0));
    };

    "aligned_input_timing_loop_stable"_test = [] {
        expect(::sodium_init() >= 0);
        const int L = 32;
        unsigned  seed = 1001U;
        int       sf = 24;
        auto      iq = pnIq(L, 1.F, seed);

        gnuradio4::kgdss::detail::SpreaderEngine sp;
        sp.generateSequence(L, 1.F, seed);
        auto k                       = fillKey(0x22U);
        std::array<std::uint8_t, 12> n{};
        n.fill(0x44U);
        sp.setKeyMaterial(k, n);

        gnuradio4::kgdss::detail::DespreaderEngine de;
        de.configureFromSpreadingSequence(std::span(iq), sf, 0.4F, 3);
        de.setKeyMaterial(k, n);
        de.setChannelEqualization(true);

        int before = de.timingOffset();
        for (int i = 0; i < 12; ++i) {
            std::vector<std::complex<float>> s{ { (i % 2 == 0) ? 1.F : -1.F, 0.F } };
            std::vector<std::complex<float>> c(static_cast<std::size_t>(sf));
            std::size_t                      w = 0;
            expect(eq(stN(sp.process(std::span(s), std::span(c), sf, 1.F, L, w)), stN(gr::work::Status::OK)));
            std::vector<std::complex<float>> rx(1);
            std::vector<float>               lockBuf(1), snrBuf(1);
            int                              used = 0;
            w                                         = 0;
            expect(eq(stN(de.process(std::span(c), std::span(rx), std::span(lockBuf), std::span(snrBuf), used, w)),
                stN(gr::work::Status::OK)));
        }
        int after = de.timingOffset();
        expect(lt(std::abs(after - before), 4));
    };
};

int main() { return boost::ut::cfg<boost::ut::override>.run(); }
