/*
 * GTest: ChaCha20-IETF keystream (detail::produce_chacha_ietf_keystream) vs oracle and
 * Wycheproof-derived vectors (ChaCha20-Poly1305 cases with empty AAD).
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#include "chacha_ietf_keystream.h"
#include "chacha_oracle.hpp"
#include "hex_util.hpp"
#include "test_vectors.h"

#include <gtest/gtest.h>

#include <cmath>
#include <cstring>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>

#ifdef KGDSS_HAVE_NLOHMANN_JSON
#include <nlohmann/json.hpp>
#endif

namespace gr::kgdss::test {

namespace {

void assert_bytes_eq(const std::vector<uint8_t>& a,
                     const std::vector<uint8_t>& b,
                     const char* ctx)
{
    ASSERT_EQ(a.size(), b.size()) << ctx;
    for (size_t i = 0; i < a.size(); i++) {
        if (a[i] != b[i]) {
            std::ostringstream os;
            os << ctx << " mismatch at byte " << i << " got 0x" << std::hex
               << static_cast<int>(a[i]) << " expected 0x"
               << static_cast<int>(b[i]) << std::dec;
            FAIL() << os.str();
        }
    }
}

} // namespace

TEST(ChachaKeystream, Rfc7539_2_1_1_BlockCounter1)
{
    std::vector<uint8_t> key(32, 0);
    std::vector<uint8_t> nonce(12, 0);
    std::vector<uint8_t> exp = hex_decode(RFC7539_2_1_1_KEYSTREAM_BLOCK1_HEX);
    ASSERT_EQ(exp.size(), 64U);

    std::array<uint8_t, 64> rem{};
    size_t rem_len = 0;
    std::vector<uint8_t> got(64);
    uint64_t ctr = 64;
    detail::produce_chacha_ietf_keystream(
        got.data(), got.size(), key.data(), nonce.data(), ctr, rem, rem_len);
    ASSERT_EQ(rem_len, 0U);
    ASSERT_EQ(ctr, 64U + 64U);

    std::vector<uint8_t> oracle;
    chacha20_ietf_oracle(oracle, 64, 64, key.data(), nonce.data());
    assert_bytes_eq(got, oracle, "RFC7539_2_1_1 vs oracle");
    assert_bytes_eq(got, exp, "RFC7539_2_1_1 vs published hex");
}

TEST(ChachaKeystream, Rfc7539_2_4_2_MessageXorMatchesOracleOffset64)
{
    std::vector<uint8_t> key = hex_decode(RFC7539_2_4_2_KEY_HEX);
    std::vector<uint8_t> nonce = hex_decode(RFC7539_2_4_2_NONCE_HEX);
    std::vector<uint8_t> msg = hex_decode(RFC7539_2_4_2_MSG_HEX);
    std::vector<uint8_t> ct = hex_decode(RFC7539_2_4_2_CT_HEX);
    ASSERT_EQ(msg.size(), RFC7539_2_4_2_MSG_LEN);
    ASSERT_EQ(ct.size(), RFC7539_2_4_2_MSG_LEN);

    std::vector<uint8_t> xor_ks(msg.size());
    for (size_t i = 0; i < msg.size(); i++)
        xor_ks[i] = static_cast<uint8_t>(msg[i] ^ ct[i]);

    std::vector<uint8_t> oracle;
    chacha20_ietf_oracle(oracle, 64, msg.size(), key.data(), nonce.data());
    assert_bytes_eq(xor_ks, oracle, "msg^ct vs oracle@64");

    std::array<uint8_t, 64> rem{};
    size_t rem_len = 0;
    std::vector<uint8_t> got(msg.size());
    uint64_t ctr = 64;
    detail::produce_chacha_ietf_keystream(
        got.data(), got.size(), key.data(), nonce.data(), ctr, rem, rem_len);
    assert_bytes_eq(got, xor_ks, "produce vs msg^ct");
}

TEST(ChachaKeystream, SplitUnequalChunksMatchesOneShot)
{
    std::vector<uint8_t> key(32);
    for (int i = 0; i < 32; i++)
        key[i] = static_cast<uint8_t>(i + 1);
    std::vector<uint8_t> nonce(12);
    for (int i = 0; i < 12; i++)
        nonce[i] = static_cast<uint8_t>(i + 0x40);

    const size_t total = 200;
    std::vector<uint8_t> oracle;
    chacha20_ietf_oracle(oracle, 0, total, key.data(), nonce.data());

    std::array<uint8_t, 64> rem{};
    size_t rem_len = 0;
    uint64_t ctr = 0;
    std::vector<uint8_t> split(total);
    size_t off = 0;
    const size_t first = 7;
    detail::produce_chacha_ietf_keystream(
        split.data() + off, first, key.data(), nonce.data(), ctr, rem, rem_len);
    off += first;
    const size_t second = 63;
    detail::produce_chacha_ietf_keystream(
        split.data() + off, second, key.data(), nonce.data(), ctr, rem, rem_len);
    off += second;
    detail::produce_chacha_ietf_keystream(split.data() + off,
                                         total - off,
                                         key.data(),
                                         nonce.data(),
                                         ctr,
                                         rem,
                                         rem_len);
    assert_bytes_eq(split, oracle, "split 7+63+rest");
}

TEST(ChachaKeystream, SixteenByteChunksFourTimesEqualsSixtyFour)
{
    std::vector<uint8_t> key(32, 9);
    std::vector<uint8_t> nonce(12, 3);

    std::array<uint8_t, 64> rem{};
    size_t rem_len = 0;
    uint64_t ctr = 0;
    std::vector<uint8_t> a(64);
    for (int i = 0; i < 4; i++) {
        detail::produce_chacha_ietf_keystream(
            a.data() + i * 16, 16, key.data(), nonce.data(), ctr, rem, rem_len);
    }

    std::array<uint8_t, 64> rem2{};
    size_t rem2_len = 0;
    uint64_t ctr2 = 0;
    std::vector<uint8_t> b(64);
    detail::produce_chacha_ietf_keystream(
        b.data(), 64, key.data(), nonce.data(), ctr2, rem2, rem2_len);

    assert_bytes_eq(a, b, "4x16 vs 64");
}

TEST(ChachaKeystream, Split37Plus63Equals100)
{
    std::vector<uint8_t> key(32, 0xab);
    std::vector<uint8_t> nonce(12, 0xcd);

    std::vector<uint8_t> oracle;
    chacha20_ietf_oracle(oracle, 0, 100, key.data(), nonce.data());

    std::array<uint8_t, 64> rem{};
    size_t rem_len = 0;
    uint64_t ctr = 0;
    std::vector<uint8_t> split(100);
    detail::produce_chacha_ietf_keystream(
        split.data(), 37, key.data(), nonce.data(), ctr, rem, rem_len);
    detail::produce_chacha_ietf_keystream(
        split.data() + 37, 63, key.data(), nonce.data(), ctr, rem, rem_len);
    assert_bytes_eq(split, oracle, "37+63");
}

TEST(ChachaKeystream, ResetCounterAfterManualClearMatchesFresh)
{
    std::vector<uint8_t> key(32, 1);
    std::vector<uint8_t> nonce(12, 2);

    std::array<uint8_t, 64> rem{};
    size_t rem_len = 0;
    uint64_t ctr = 0;
    std::vector<uint8_t> first(16);
    detail::produce_chacha_ietf_keystream(
        first.data(), 16, key.data(), nonce.data(), ctr, rem, rem_len);

    ctr = 0;
    rem_len = 0;
    std::vector<uint8_t> second(16);
    detail::produce_chacha_ietf_keystream(
        second.data(), 16, key.data(), nonce.data(), ctr, rem, rem_len);

    std::vector<uint8_t> oracle;
    chacha20_ietf_oracle(oracle, 0, 16, key.data(), nonce.data());
    assert_bytes_eq(second, oracle, "after reset");
}

TEST(ChachaKeystream, Large4096BytesMatchesOracle)
{
    std::vector<uint8_t> key(32);
    for (int i = 0; i < 32; i++)
        key[i] = static_cast<uint8_t>(i * 3 + 5);
    std::vector<uint8_t> nonce(12);
    for (int i = 0; i < 12; i++)
        nonce[i] = static_cast<uint8_t>(i ^ 0x5a);

    const size_t total = 256U * 16U;
    std::vector<uint8_t> oracle;
    chacha20_ietf_oracle(oracle, 0, total, key.data(), nonce.data());

    std::array<uint8_t, 64> rem{};
    size_t rem_len = 0;
    uint64_t ctr = 0;
    std::vector<uint8_t> got(total);
    detail::produce_chacha_ietf_keystream(
        got.data(), total, key.data(), nonce.data(), ctr, rem, rem_len);
    assert_bytes_eq(got, oracle, "4096 byte oracle");
}

TEST(ChachaKeystream, CounterOverflowThrows)
{
    std::vector<uint8_t> key(32, 7);
    std::vector<uint8_t> nonce(12, 8);
    std::array<uint8_t, 64> rem{};
    size_t rem_len = 0;
    /* Last legal stream byte is at offset UINT32_MAX*64+63; one more full block needs
     * block index UINT32_MAX+1. */
    uint64_t ctr = static_cast<uint64_t>(UINT32_MAX) * 64ULL;
    std::vector<uint8_t> buf(65);
    bool threw = false;
    try {
        detail::produce_chacha_ietf_keystream(
            buf.data(), 65, key.data(), nonce.data(), ctr, rem, rem_len);
    } catch (const std::runtime_error& e) {
        threw = true;
        std::string m(e.what());
        EXPECT_NE(m.find("counter"), std::string::npos)
            << "message should mention counter: " << m;
    }
    ASSERT_TRUE(threw);
}

#ifdef KGDSS_HAVE_NLOHMANN_JSON

TEST(WycheproofChachaPoly1305Subset, MsgXorCtMatchesProduceAtOffset64)
{
    const char* path = KGDSS_WYCH_SUBSET_JSON_PATH;
    std::ifstream in(path);
    ASSERT_TRUE(in.good()) << "open " << path;
    nlohmann::json j;
    in >> j;
    ASSERT_TRUE(j.contains("tests"));
    const auto& tests = j["tests"];
    ASSERT_TRUE(tests.is_array());
    int n = 0;
    for (const auto& t : tests) {
        if (!t.contains("key") || !t.contains("iv") || !t.contains("msg") ||
            !t.contains("ct"))
            continue;
        std::vector<uint8_t> key = hex_decode(t["key"].get<std::string>());
        std::vector<uint8_t> nonce = hex_decode(t["iv"].get<std::string>());
        std::vector<uint8_t> msg = hex_decode(t["msg"].get<std::string>());
        std::vector<uint8_t> ct = hex_decode(t["ct"].get<std::string>());
        ASSERT_EQ(msg.size(), ct.size());
        std::vector<uint8_t> xor_ks(msg.size());
        for (size_t i = 0; i < msg.size(); i++)
            xor_ks[i] = static_cast<uint8_t>(msg[i] ^ ct[i]);

        std::vector<uint8_t> oracle;
        chacha20_ietf_oracle(oracle, 64, msg.size(), key.data(), nonce.data());
        assert_bytes_eq(xor_ks, oracle, "wycheproof oracle");

        std::array<uint8_t, 64> rem{};
        size_t rem_len = 0;
        uint64_t ctr = 64;
        std::vector<uint8_t> got(msg.size());
        detail::produce_chacha_ietf_keystream(
            got.data(), got.size(), key.data(), nonce.data(), ctr, rem, rem_len);
        assert_bytes_eq(got, xor_ks, "wycheproof produce");
        n++;
    }
    EXPECT_GE(n, 1);
}

TEST(WycheproofChachaPoly1305Subset, SplitFullKeystreamMatchesOneShot)
{
    const char* path = KGDSS_WYCH_SUBSET_JSON_PATH;
    std::ifstream in(path);
    ASSERT_TRUE(in.good());
    nlohmann::json j;
    in >> j;
    const auto& tests = j["tests"];
    ASSERT_TRUE(tests.is_array() && !tests.empty());
    const auto& t = tests[0];
    std::vector<uint8_t> key = hex_decode(t["key"].get<std::string>());
    std::vector<uint8_t> nonce = hex_decode(t["iv"].get<std::string>());
    std::vector<uint8_t> msg = hex_decode(t["msg"].get<std::string>());
    const size_t nbyte = msg.size();

    std::vector<uint8_t> oracle;
    chacha20_ietf_oracle(oracle, 64, nbyte, key.data(), nonce.data());

    std::array<uint8_t, 64> rem{};
    size_t rem_len = 0;
    uint64_t ctr = 64;
    std::vector<uint8_t> a(nbyte);
    size_t a1 = nbyte / 3;
    size_t a2 = nbyte / 3;
    detail::produce_chacha_ietf_keystream(
        a.data(), a1, key.data(), nonce.data(), ctr, rem, rem_len);
    detail::produce_chacha_ietf_keystream(
        a.data() + a1, a2, key.data(), nonce.data(), ctr, rem, rem_len);
    detail::produce_chacha_ietf_keystream(a.data() + a1 + a2,
                                         nbyte - a1 - a2,
                                         key.data(),
                                         nonce.data(),
                                         ctr,
                                         rem,
                                         rem_len);
    assert_bytes_eq(a, oracle, "wycheproof split");
}

#endif

} // namespace gr::kgdss::test
