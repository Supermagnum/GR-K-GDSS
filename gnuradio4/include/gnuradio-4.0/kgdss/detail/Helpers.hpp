// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef GNURADIO4_KGDSS_DETAIL_HELPERS_HPP
#define GNURADIO4_KGDSS_DETAIL_HELPERS_HPP

#include <gnuradio-4.0/Tensor.hpp>
#include <gnuradio-4.0/Message.hpp>
#include <gnuradio-4.0/Tag.hpp>

#include <cstddef>
#include <cstring>
#include <expected>
#include <optional>
#include <span>
#include <string_view>

namespace gnuradio4::kgdss::detail {

[[nodiscard]] inline const gr::Tensor<std::uint8_t>* tensorU8FromMap(const gr::property_map& map, std::string_view keyView) {
    const std::pmr::string key = gr::convert_string_domain(keyView);
    const auto              it = map.find(key);
    if (it == map.end()) {
        return nullptr;
    }
    return it->second.get_if<gr::Tensor<std::uint8_t>>();
}

/**
 * Copy a fixed-length byte field from a gr::property_map entry.
 * The entry must hold a gr::Tensor<uint8_t> of exactly N bytes.
 * Returns true and fills dst on success.
 */
[[nodiscard]] inline bool copyBytesFromMap(const gr::property_map& map, std::string_view keyView,
    std::uint8_t* dst, std::size_t N) noexcept {
    const gr::Tensor<std::uint8_t>* t = tensorU8FromMap(map, keyView);
    if (t == nullptr || t->size() != N) {
        return false;
    }
    std::memcpy(dst, t->data(), N);
    return true;
}

[[nodiscard]] inline std::optional<std::uint64_t> scalarUint64FromMap(const gr::property_map& map, std::string_view keyView) {
    const std::pmr::string key = gr::convert_string_domain(keyView);
    const auto             it = map.find(key);
    if (it == map.end()) {
        return std::nullopt;
    }
    const auto& v = it->second;
    if (const auto* u = v.get_if<std::uint64_t>()) {
        return *u;
    }
    if (const auto* i = v.get_if<std::int64_t>()) {
        if (*i < 0) {
            return std::nullopt;
        }
        return static_cast<std::uint64_t>(*i);
    }
    if (const auto* u32 = v.get_if<std::uint32_t>()) {
        return static_cast<std::uint64_t>(*u32);
    }
    return std::nullopt;
}

[[nodiscard]] inline std::optional<std::uint64_t> counterFromMessagePayload(
    const std::expected<gr::property_map, gr::Error>& data) noexcept {
    if (!data.has_value()) {
        return std::nullopt;
    }
    const gr::property_map& map = *data;
    if (auto c = scalarUint64FromMap(map, "counter"); c.has_value()) {
        return c;
    }
    return scalarUint64FromMap(map, "set_counter");
}

} // namespace gnuradio4::kgdss::detail

#endif
