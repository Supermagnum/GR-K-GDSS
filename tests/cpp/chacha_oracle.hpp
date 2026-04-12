/*
 * Test-only oracle: ChaCha20-IETF keystream via libsodium crypto_stream_chacha20_ietf
 * (not _xor_ic), independent of gr::kgdss::detail::produce_chacha_ietf_keystream.
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#ifndef KGDSS_TEST_CHACHA_ORACLE_HPP
#define KGDSS_TEST_CHACHA_ORACLE_HPP

#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <vector>
#include <sodium.h>

namespace gr {
namespace kgdss {
namespace test {

inline void chacha20_ietf_oracle(std::vector<uint8_t>& out,
                                 uint64_t byte_offset,
                                 size_t length,
                                 const uint8_t* key,
                                 const uint8_t* nonce)
{
    if (length == 0) {
        out.clear();
        return;
    }
    const size_t total = static_cast<size_t>(byte_offset) + length;
    std::vector<uint8_t> buf(total);
    if (crypto_stream_chacha20_ietf(buf.data(), total, nonce, key) != 0) {
        throw std::runtime_error("chacha20_ietf_oracle: crypto_stream_chacha20_ietf failed");
    }
    out.resize(length);
    std::memcpy(out.data(), buf.data() + byte_offset, length);
}

} // namespace test
} // namespace kgdss
} // namespace gr

#endif
