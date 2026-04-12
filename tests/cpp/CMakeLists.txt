# Native ChaCha20 / spreader crypto tests (Google Test). Optional; requires libsodium.
# SPDX-License-Identifier: GPL-3.0-or-later

cmake_minimum_required(VERSION 3.16)

find_package(Threads REQUIRED)
find_package(PkgConfig REQUIRED)
pkg_check_modules(GR_RT_CRYPTO_TEST REQUIRED gnuradio-runtime)
pkg_check_modules(FMT QUIET fmt)

include(FetchContent)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_Declare(
    googletest
    GIT_REPOSITORY https://github.com/google/googletest.git
    GIT_TAG v1.14.0
)
FetchContent_MakeAvailable(googletest)

FetchContent_Declare(
    nlohmann_json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG v3.11.3
)
FetchContent_MakeAvailable(nlohmann_json)

set(_wych_subset "${CMAKE_SOURCE_DIR}/tests/cpp/data/wycheproof_chacha20_poly1305_subset.json")
file(TO_CMAKE_PATH "${_wych_subset}" _wych_subset_cmake)

add_executable(kgdss_test_chacha_keystream test_chacha_keystream.cpp)
target_include_directories(
    kgdss_test_chacha_keystream
    PRIVATE ${CMAKE_SOURCE_DIR}/lib ${SODIUM_INCLUDE_DIRS}
)
target_link_libraries(
    kgdss_test_chacha_keystream
    PRIVATE GTest::gtest_main ${SODIUM_LIBRARIES} Threads::Threads
)
target_link_libraries(kgdss_test_chacha_keystream PRIVATE nlohmann_json::nlohmann_json)
target_compile_definitions(
    kgdss_test_chacha_keystream
    PRIVATE KGDSS_HAVE_NLOHMANN_JSON=1 "KGDSS_WYCH_SUBSET_JSON_PATH=\"${_wych_subset_cmake}\""
)

add_executable(kgdss_test_spreader_stats test_spreader_work_stats.cpp)
target_include_directories(
    kgdss_test_spreader_stats
    PRIVATE ${CMAKE_SOURCE_DIR}/include ${GR_RT_CRYPTO_TEST_INCLUDE_DIRS}
)
set(_spreader_test_libs GTest::gtest_main gnuradio-kgdss ${GR_RT_CRYPTO_TEST_LIBRARIES}
                        ${SODIUM_LIBRARIES} Threads::Threads)
set(_spreader_test_inc ${SODIUM_INCLUDE_DIRS})
if(FMT_FOUND)
    list(APPEND _spreader_test_libs ${FMT_LIBRARIES})
    list(APPEND _spreader_test_inc ${FMT_INCLUDE_DIRS})
else()
    list(APPEND _spreader_test_libs fmt)
endif()
target_link_libraries(kgdss_test_spreader_stats PRIVATE ${_spreader_test_libs})
target_include_directories(kgdss_test_spreader_stats PRIVATE ${_spreader_test_inc})

add_test(NAME kgdss_test_chacha_keystream COMMAND kgdss_test_chacha_keystream)
add_test(NAME kgdss_test_spreader_stats COMMAND kgdss_test_spreader_stats)
