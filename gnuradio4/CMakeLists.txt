# SPDX-License-Identifier: GPL-3.0-or-later
cmake_minimum_required(VERSION 3.22)

if(NOT CMAKE_CXX_COMPILER)
  foreach(_cxx IN ITEMS g++-16 g++-15 g++-14)
    find_program(_gr_k_gdss4_cxx NAMES "${_cxx}")
    if(_gr_k_gdss4_cxx)
      set(CMAKE_CXX_COMPILER "${_gr_k_gdss4_cxx}" CACHE STRING "CXX compiler for GR4 gdss (<print>)"
        FORCE)
      break()
    endif()
  endforeach()
endif()

project(
  gr-k-gdss4
  VERSION 0.1.0
  LANGUAGES CXX
  DESCRIPTION "GNU Radio 4.0 Keyed Gaussian-Distributed Spread Spectrum (Keyed GDSS)")

include(GNUInstallDirs)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(GR_K_GDSS4_BUILD_TESTS "Build Boost.UT regressions for gr-k-gdss4" ON)

find_package(gnuradio4 REQUIRED CONFIG)

find_package(PkgConfig REQUIRED)
pkg_check_modules(libsodium REQUIRED IMPORTED_TARGET libsodium)
pkg_check_modules(ZMQ QUIET IMPORTED_TARGET libzmq)

find_package(gr-linux-crypto4 CONFIG QUIET)

add_library(gnuradio4-gr-k-gdss INTERFACE)
add_library(gnuradio4::gr-k-gdss ALIAS gnuradio4-gr-k-gdss)

target_include_directories(
  gnuradio4-gr-k-gdss
  INTERFACE $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
            $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>)

target_link_libraries(gnuradio4-gr-k-gdss INTERFACE gnuradio4::gnuradio-core gnuradio4::gnuradio-blocklib-core
                                                    PkgConfig::libsodium)

if(ZMQ_FOUND)
  target_compile_definitions(gnuradio4-gr-k-gdss INTERFACE GR_K_GDSS4_HAVE_ZMQ=1)
  target_link_libraries(gnuradio4-gr-k-gdss INTERFACE PkgConfig::ZMQ)
endif()

if(gr-linux-crypto4_FOUND)
  target_compile_definitions(gnuradio4-gr-k-gdss INTERFACE GR_K_GDSS4_HAVE_LINUX_CRYPTO=1)
endif()

install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/include/" DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})

install(
  TARGETS gnuradio4-gr-k-gdss
  EXPORT gr-k-gdss4-targets
  INCLUDES
  DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})

install(
  EXPORT gr-k-gdss4-targets
  FILE gr-k-gdss4-targets.cmake
  NAMESPACE gnuradio4::
  DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/gr-k-gdss4)

include(CMakePackageConfigHelpers)

configure_package_config_file(
  "${CMAKE_CURRENT_SOURCE_DIR}/cmake/gr-k-gdss4-config.cmake.in"
  "${CMAKE_CURRENT_BINARY_DIR}/gr-k-gdss4-config.cmake"
  INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/gr-k-gdss4)

write_basic_package_version_file(
  "${CMAKE_CURRENT_BINARY_DIR}/gr-k-gdss4-config-version.cmake"
  VERSION "${PROJECT_VERSION}"
  COMPATIBILITY SameMajorVersion)

install(FILES "${CMAKE_CURRENT_BINARY_DIR}/gr-k-gdss4-config.cmake"
              "${CMAKE_CURRENT_BINARY_DIR}/gr-k-gdss4-config-version.cmake"
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/gr-k-gdss4)

configure_file("${CMAKE_CURRENT_SOURCE_DIR}/cmake/gnuradio4-gr-k-gdss.pc.in"
               "${CMAKE_CURRENT_BINARY_DIR}/gnuradio4-gr-k-gdss.pc" @ONLY)

install(FILES "${CMAKE_CURRENT_BINARY_DIR}/gnuradio4-gr-k-gdss.pc"
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/pkgconfig)

install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/python/kgdss"
        DESTINATION "${CMAKE_INSTALL_DATADIR}/gr-k-gdss4/python"
        FILES_MATCHING
        PATTERN "*.py"
        PATTERN "*.json")

if(GR_K_GDSS4_BUILD_TESTS)
  include(FetchContent)
  set(BOOST_UT_DISABLE_MODULE ON CACHE BOOL "Disable Boost.UT Module" FORCE)
  FetchContent_Declare(
    ut
    GIT_REPOSITORY https://github.com/boost-ext/ut.git
    GIT_TAG 53e17f25119598c6458d30351b260193096ba67e
    EXCLUDE_FROM_ALL)
  FetchContent_MakeAvailable(ut)
  enable_testing()
  add_subdirectory(test)
endif()
