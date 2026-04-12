/*
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#ifndef KGDSS_TEST_HEX_UTIL_HPP
#define KGDSS_TEST_HEX_UTIL_HPP

#include <cctype>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

namespace gr {
namespace kgdss {
namespace test {

inline int hex_nibble(char c)
{
    if (c >= '0' && c <= '9')
        return c - '0';
    if (c >= 'a' && c <= 'f')
        return c - 'a' + 10;
    if (c >= 'A' && c <= 'F')
        return c - 'A' + 10;
    return -1;
}

inline std::vector<uint8_t> hex_decode(const std::string& hex)
{
    std::string s;
    s.reserve(hex.size());
    for (char c : hex) {
        if (std::isspace(static_cast<unsigned char>(c)))
            continue;
        s.push_back(c);
    }
    if (s.size() % 2 != 0)
        throw std::invalid_argument("hex_decode: odd length");
    std::vector<uint8_t> out(s.size() / 2);
    for (size_t i = 0; i < out.size(); i++) {
        int hi = hex_nibble(s[2 * i]);
        int lo = hex_nibble(s[2 * i + 1]);
        if (hi < 0 || lo < 0)
            throw std::invalid_argument("hex_decode: non-hex digit");
        out[i] = static_cast<uint8_t>((hi << 4) | lo);
    }
    return out;
}

} // namespace test
} // namespace kgdss
} // namespace gr

#endif
