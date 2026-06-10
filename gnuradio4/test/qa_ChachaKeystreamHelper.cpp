// SPDX-License-Identifier: GPL-3.0-or-later
#include <boost/ut.hpp>

#include <gnuradio-4.0/kgdss/detail/ChachaKeystreamHelper.hpp>

#include <array>
#include <climits>
#include <cstdint>

#include <sodium.h>

namespace kgd_detail = gnuradio4::kgdss::detail;

using namespace boost::ut;

suite<"produce_chacha_ietf_keystream"> ChaChaHelperSuite = [] {
    "deterministic bytes for same counter key nonce"_test = [] {
        expect(::sodium_init() >= 0);
        constexpr std::array<std::uint8_t, 32> key{};
        constexpr std::array<std::uint8_t, 12> nonce{};
        std::uint64_t                            ctr =
            0ULL;
        std::array<std::uint8_t, 64> rem{};
        std::size_t remLen = 0;

        std::array<std::uint8_t, 128> buf1{};
        std::array<std::uint8_t, 128> buf2{};

        std::uint64_t c1 = ctr;
        expect(kgd_detail::produce_chacha_ietf_keystream(buf1.data(), buf1.size(), key.data(), nonce.data(), c1, rem,
            remLen));
        ctr   = 0;
        remLen = 0;
        std::uint64_t c2 = ctr;
        expect(kgd_detail::produce_chacha_ietf_keystream(buf2.data(), buf2.size(), key.data(), nonce.data(), c2, rem,
            remLen));
        expect(buf1 == buf2);
    };

    "remainder continuation matches single large xor"_test = [] {
        expect(::sodium_init() >= 0);
        constexpr std::array<std::uint8_t, 32> k{};
        constexpr std::array<std::uint8_t, 12> n{};
        std::array<std::uint8_t, 200> one{};
        std::uint64_t                 ctr_a = 0;
        std::array<std::uint8_t, 64> rem_a{};
        std::size_t                 rem_la = 0;
        expect(kgd_detail::produce_chacha_ietf_keystream(one.data(), one.size(), k.data(), n.data(), ctr_a,
            rem_a, rem_la));

        std::array<std::uint8_t, 200> split{};
        std::uint64_t                 ctr_b = 0;
        std::array<std::uint8_t, 64> rem_b{};
        std::size_t                  rem_lb = 0;
        expect(kgd_detail::produce_chacha_ietf_keystream(split.data(), 77UZ, k.data(), n.data(),
            ctr_b, rem_b, rem_lb));
        expect(kgd_detail::produce_chacha_ietf_keystream(split.data() + 77, 123UZ, k.data(), n.data(),
            ctr_b, rem_b, rem_lb));
        expect(one == split);
    };

    "UINT32_MAX block guard returns false without throwing"_test = [] {
        expect(::sodium_init() >= 0);
        constexpr std::array<std::uint8_t, 32> k{};
        constexpr std::array<std::uint8_t, 12> n{};
        std::uint64_t ctr =
            (static_cast<std::uint64_t>(UINT32_MAX) + 1ULL) * 64ULL;
        std::array<std::uint8_t, 64> rem{};
        std::size_t remLen = 0;
        std::array<std::uint8_t, 4> out{};
        expect(!kgd_detail::produce_chacha_ietf_keystream(out.data(), out.size(), k.data(),
            n.data(), ctr,
            rem, remLen));
    };
};

int main() { return boost::ut::cfg<boost::ut::override>.run(); }
