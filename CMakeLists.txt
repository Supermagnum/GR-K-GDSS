cmake_minimum_required(VERSION 3.16)
project(gr-k-gdss CXX C)

enable_testing()

list(INSERT CMAKE_MODULE_PATH 0 ${PROJECT_SOURCE_DIR}/cmake/Modules)

find_package(Gnuradio "3.10" REQUIRED)

set(VERSION_MAJOR 1)
set(VERSION_API   0)
set(VERSION_ABI   0)
set(VERSION_PATCH 0)

include(GNUInstallDirs)

find_package(PkgConfig REQUIRED)
pkg_check_modules(SODIUM libsodium)

option(KGDSS_ENABLE_CRYPTO_TESTS "Build native ChaCha20/spreader GTest suite (libsodium + GTest)" OFF)

if(SODIUM_FOUND)
    message(STATUS "Using libsodium for ChaCha20")
    add_compile_definitions(HAVE_LIBSODIUM=1)
else()
    find_package(OpenSSL REQUIRED)
    message(STATUS "libsodium not found, using OpenSSL EVP")
endif()

include(FindPkgConfig)
pkg_check_modules(GR_RUNTIME REQUIRED gnuradio-runtime)
pkg_check_modules(GR_BLOCKS REQUIRED gnuradio-blocks)

add_subdirectory(include/gnuradio/kgdss)
add_subdirectory(lib)
add_subdirectory(python)
add_subdirectory(grc)
add_subdirectory(tests)

