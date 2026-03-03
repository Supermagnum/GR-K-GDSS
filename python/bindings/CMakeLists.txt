# Keyed GDSS Python bindings (pybind11)

find_package(pybind11 CONFIG REQUIRED)
find_package(Python3 COMPONENTS Interpreter NumPy REQUIRED)

set(kgdss_python_sources
    kgdss_python.cc
    kgdss_spreader_cc_python.cc
    kgdss_despreader_cc_python.cc
)

pybind11_add_module(kgdss_python ${kgdss_python_sources})

target_include_directories(
    kgdss_python
    PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/../../lib
           ${CMAKE_CURRENT_SOURCE_DIR}/../../include
)

target_link_libraries(
    kgdss_python
    PRIVATE pybind11::pybind11
            gnuradio-kgdss
            ${GR_RUNTIME_LIBRARIES}
            ${GR_BLOCKS_LIBRARIES}
)

if(CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
    target_compile_options(kgdss_python PRIVATE -Wno-unused-variable)
endif()

if(NOT DEFINED kgdss_python_install_dir)
    if(DEFINED GR_PYTHON_DIR)
        set(kgdss_python_install_dir ${GR_PYTHON_DIR}/gnuradio/kgdss)
    else()
        execute_process(
            COMMAND ${Python3_EXECUTABLE} -c
                    "import site; print(site.getsitepackages()[0] if site.getsitepackages() else site.getusersitepackages())"
            OUTPUT_VARIABLE Python3_SITELIB
            OUTPUT_STRIP_TRAILING_WHITESPACE
        )
        set(kgdss_python_install_dir ${Python3_SITELIB}/gnuradio/kgdss)
    endif()
endif()

install(
    TARGETS kgdss_python
    LIBRARY DESTINATION ${kgdss_python_install_dir}
    RUNTIME DESTINATION ${kgdss_python_install_dir}
    COMPONENT pythonapi
)
