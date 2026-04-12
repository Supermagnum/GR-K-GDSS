# Unit tests (pytest). Run after install or set PYTHONPATH to include installed gnuradio.kgdss.
# Optional C++ crypto tests (Google Test): -DKGDSS_ENABLE_CRYPTO_TESTS=ON at configure time.

find_package(Python3 COMPONENTS Interpreter REQUIRED)

if(KGDSS_ENABLE_CRYPTO_TESTS)
    if(SODIUM_FOUND)
        add_subdirectory(cpp)
    else()
        message(
            WARNING
                "KGDSS_ENABLE_CRYPTO_TESTS is ON but libsodium was not found; skipping C++ crypto tests."
        )
    endif()
endif()

find_program(PYTEST NAMES pytest pytest-3)
if(PYTEST)
    add_test(
        NAME pytest_kgdss
        COMMAND ${Python3_EXECUTABLE} -m pytest
                ${CMAKE_CURRENT_SOURCE_DIR}
                -v
                --tb=short
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    )
endif()
