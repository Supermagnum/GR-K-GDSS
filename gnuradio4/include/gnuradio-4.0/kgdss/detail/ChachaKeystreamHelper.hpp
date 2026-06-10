// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef GNURADIO4_KGDSS_DETAIL_CHACHAKEYSTREAMHELPER_HPP
#define GNURADIO4_KGDSS_DETAIL_CHACHAKEYSTREAMHELPER_HPP

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>

#include <sodium.h>

namespace gnuradio4::kgdss::detail {

/** `ctr` is the byte offset in the stream; libsodium block index is ctr / 64 (uint32_t).
 * Returns false if the implicit block counter would exceed UINT32_MAX (no keystream produced). */
[[nodiscard]] inline bool produce_chacha_ietf_keystream(std::uint8_t* buf, std::size_t len,
    const std::uint8_t* key, const std::uint8_t* nonce, std::uint64_t& ctr, std::array<std::uint8_t, 64>& rem,
    std::size_t& remLen) noexcept {
    std::size_t filled = 0;
    std::uint8_t chacha_block[64];

    while (filled < len) {
        if (remLen > 0) {
            const std::size_t take = std::min(remLen, len - filled);
            std::memcpy(buf + filled, rem.data(), take);
            if (take < remLen) {
                std::memmove(rem.data(), rem.data() + take, remLen - take);
            }
            remLen -= take;
            filled += take;
            ctr += take;
            continue;
        }

        const std::uint64_t block_idx = ctr / 64ULL;
        if (block_idx > static_cast<std::uint64_t>(UINT32_MAX)) {
            return false;
        }
        const std::size_t skip = static_cast<std::size_t>(ctr % 64ULL);
        std::memset(chacha_block, 0, sizeof(chacha_block));
        if (crypto_stream_chacha20_ietf_xor_ic(chacha_block, chacha_block, sizeof(chacha_block), nonce, static_cast<std::uint32_t>(block_idx), key)
            != 0) [[unlikely]] {
            return false;
        }

        const std::size_t avail = sizeof(chacha_block) - skip;
        const std::size_t take  = std::min(avail, len - filled);
        std::memcpy(buf + filled, chacha_block + skip, take);
        ctr += take;
        filled += take;
        const std::size_t used_from_block = skip + take;
        if (used_from_block < sizeof(chacha_block)) {
            remLen = sizeof(chacha_block) - used_from_block;
            std::memcpy(rem.data(), chacha_block + used_from_block, remLen);
        } else {
            remLen = 0;
        }
    }
    return true;
}

} // namespace gnuradio4::kgdss::detail

#endif
