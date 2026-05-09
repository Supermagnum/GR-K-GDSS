// SPDX-License-Identifier: GPL-3.0-or-later
#include <boost/ut.hpp>
#include <gnuradio-4.0/Block.hpp>
#include <gnuradio-4.0/Tensor.hpp>
#include <gnuradio-4.0/kgdss/KgdssDespreaderCc.hpp>
#include <gnuradio-4.0/kgdss/detail/DespreaderEngine.hpp>
#include <gnuradio-4.0/kgdss/detail/SpreaderEngine.hpp>

#include <algorithm>
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

[[nodiscard]] float corrComplexMag(const std::vector<std::complex<float>>& a, const std::vector<std::complex<float>>& b) {
    const std::size_t n = std::min(a.size(), b.size());
    if (n < 8UZ) {
        return 0.F;
    }
    double sum_ab = 0.0;
    double sum_a2 = 0.0;
    double sum_b2 = 0.0;
    for (std::size_t i = 0; i < n; ++i) {
        sum_ab += static_cast<double>(a[i].real()) * static_cast<double>(b[i].real())
            + static_cast<double>(a[i].imag()) * static_cast<double>(b[i].imag());
        sum_a2 += static_cast<double>(std::norm(a[i]));
        sum_b2 += static_cast<double>(std::norm(b[i]));
    }
    const double den = std::sqrt(sum_a2) * std::sqrt(sum_b2) + 1e-12;
    return static_cast<float>(std::abs(sum_ab) / den);
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

    // Noiseless back-to-back matched ChaCha + Box-Muller + MF despreading
    // gives coherence ~1.0 (verified in Python reference: max|out-sym| ~1e-15).
    // Threshold 0.98 allows for float32 pipeline rounding; values 0.85-0.95
    // would indicate a keystream alignment or metric problem, not ideal recovery.
    "matched_key_chacha_correlation_stream"_test = [] {
        expect(::sodium_init() >= 0);
        const int      L  = 128;
        const int      sf = 64;
        const float    var = 1.F;
        auto           iq = pnIq(L, var, 77U);
        std::array<std::uint8_t, 32> key{};
        for (std::size_t i = 0; i < key.size(); ++i) {
            key[i] = static_cast<std::uint8_t>(i + 1U);
        }
        std::array<std::uint8_t, 12> nonce{};
        for (std::size_t i = 0; i < nonce.size(); ++i) {
            nonce[i] = static_cast<std::uint8_t>(0x10U + i);
        }

        gnuradio4::kgdss::detail::SpreaderEngine sp;
        sp.generateSequence(L, var, 1414U);
        sp.setKeyMaterial(key, nonce);

        gnuradio4::kgdss::detail::DespreaderEngine de;
        de.configureFromSpreadingSequence(std::span(iq), sf, 0.5F, 3);
        de.setKeyMaterial(key, nonce);

        std::vector<std::complex<float>> sent;
        std::vector<std::complex<float>> got;
        std::mt19937                     rng(2020U);
        std::uniform_real_distribution<float> u(-1.F, 1.F);
        const int nSym = 48;
        for (int i = 0; i < nSym; ++i) {
            std::complex<float> sym(u(rng), u(rng));
            sent.push_back(sym);
            std::vector<std::complex<float>> sv{ sym };
            std::vector<std::complex<float>> chips(static_cast<std::size_t>(sf));
            std::size_t                      w = 0;
            expect(eq(stN(sp.process(std::span(sv), std::span(chips), sf, var, L, w)),
                stN(gr::work::Status::OK)));
            std::vector<std::complex<float>> out(1);
            std::vector<float>               lk(1), sn(1);
            int                              used = 0;
            w                                         = 0;
            expect(eq(stN(de.process(std::span(chips), std::span(out), std::span(lk), std::span(sn), used, w)),
                stN(gr::work::Status::OK)));
            got.push_back(out[0]);
        }
        expect(gt(corrComplexMag(sent, got), 0.98F));
    };

    "wrong_key_chacha_correlation_near_zero"_test = [] {
        expect(::sodium_init() >= 0);
        const int      L  = 64;
        const int      sf = 64;
        const float    var = 1.F;
        auto           iq = pnIq(L, var, 88U);
        auto           kG = fillKey(0x3AU);
        auto           kB = fillKey(0xC5U);
        std::array<std::uint8_t, 12> nG{};
        nG.fill(0x5EU);

        gnuradio4::kgdss::detail::SpreaderEngine sp;
        sp.generateSequence(L, var, 9001U);
        sp.setKeyMaterial(kG, nG);

        std::vector<std::complex<float>> sent;
        std::vector<std::complex<float>> chipsAcc;
        std::mt19937                     rng(4242U);
        std::uniform_real_distribution<float> u(-0.8F, 0.8F);
        const int nSym = 40;
        for (int i = 0; i < nSym; ++i) {
            std::complex<float> sym(u(rng), u(rng));
            sent.push_back(sym);
            std::vector<std::complex<float>> sv{ sym };
            std::vector<std::complex<float>> chips(static_cast<std::size_t>(sf));
            std::size_t                      w = 0;
            expect(eq(stN(sp.process(std::span(sv), std::span(chips), sf, var, L, w)), stN(gr::work::Status::OK)));
            chipsAcc.insert(chipsAcc.end(), chips.begin(), chips.end());
        }

        gnuradio4::kgdss::detail::DespreaderEngine bad;
        bad.configureFromSpreadingSequence(std::span(iq), sf, 0.45F, 3);
        bad.setKeyMaterial(kB, nG);

        std::vector<std::complex<float>> got;
        for (int i = 0; i < nSym; ++i) {
            const std::size_t off = static_cast<std::size_t>(i) * static_cast<std::size_t>(sf);
            std::vector<std::complex<float>> block(static_cast<std::size_t>(sf));
            for (int j = 0; j < sf; ++j) {
                block[static_cast<std::size_t>(j)] = chipsAcc[off + static_cast<std::size_t>(j)];
            }
            std::vector<std::complex<float>> out(1);
            std::vector<float>               lk(1), sn(1);
            int                              used = 0;
            std::size_t                      w    = 0;
            expect(eq(stN(bad.process(std::span(block), std::span(out), std::span(lk), std::span(sn), used, w)),
                stN(gr::work::Status::OK)));
            got.push_back(out[0]);
        }
        expect(lt(corrComplexMag(sent, got), 0.1F));
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
