/*
 * Shared ChaCha20-IETF keystream helper for kgdss spreader/despreader.
 * Drains a 64-byte remainder first, then full 64-byte blocks via libsodium.
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#ifndef INCLUDED_KGDSS_CHACHA_IETF_KEYSTREAM_H
#define INCLUDED_KGDSS_CHACHA_IETF_KEYSTREAM_H

#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <sodium.h>

namespace gr {
namespace kgdss {
namespace detail {

/** `ctr` is the byte offset in the stream; libsodium `ic` is ctr / 64 (uint32_t). */
inline void produce_chacha_ietf_keystream(uint8_t* buf,
                                          size_t len,
                                          const uint8_t* key,
                                          const uint8_t* nonce,
                                          uint64_t& ctr,
                                          std::array<uint8_t, 64>& rem,
                                          size_t& rem_len)
{
    size_t filled = 0;
    uint8_t chacha_block[64];

    while (filled < len) {
        if (rem_len > 0) {
            const size_t take = std::min(rem_len, len - filled);
            std::memcpy(buf + filled, rem.data(), take);
            if (take < rem_len) {
                std::memmove(rem.data(), rem.data() + take, rem_len - take);
            }
            rem_len -= take;
            filled += take;
            ctr += take;
            continue;
        }

        const uint64_t block_idx = ctr / 64;
        assert(block_idx <= static_cast<uint64_t>(UINT32_MAX));
        if (block_idx > static_cast<uint64_t>(UINT32_MAX)) {
            throw std::runtime_error(
                "kgdss: ChaCha20-IETF block counter overflow (byte position implies block "
                "counter index > UINT32_MAX)");
        }
        const size_t skip = static_cast<size_t>(ctr % 64);
        std::memset(chacha_block, 0, sizeof(chacha_block));
        if (crypto_stream_chacha20_ietf_xor_ic(chacha_block,
                                               chacha_block,
                                               sizeof(chacha_block),
                                               nonce,
                                               static_cast<uint32_t>(block_idx),
                                               key) != 0) {
            throw std::runtime_error("kgdss: crypto_stream_chacha20_ietf_xor_ic failed");
        }

        const size_t avail = sizeof(chacha_block) - skip;
        const size_t take = std::min(avail, len - filled);
        std::memcpy(buf + filled, chacha_block + skip, take);
        ctr += take;
        filled += take;
        const size_t used_from_block = skip + take;
        if (used_from_block < sizeof(chacha_block)) {
            rem_len = sizeof(chacha_block) - used_from_block;
            std::memcpy(rem.data(), chacha_block + used_from_block, rem_len);
        } else {
            rem_len = 0;
        }
    }
}

} // namespace detail
} // namespace kgdss
} // namespace gr

#endif /* INCLUDED_KGDSS_CHACHA_IETF_KEYSTREAM_H */
