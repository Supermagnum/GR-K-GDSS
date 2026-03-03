# Unit tests (pytest). Run after install or set PYTHONPATH to include installed gnuradio.kgdss.

find_package(Python3 COMPONENTS Interpreter REQUIRED)

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
