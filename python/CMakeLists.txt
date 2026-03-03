find_package(Python3 COMPONENTS Interpreter REQUIRED)
include(GNUInstallDirs)

add_subdirectory(bindings)

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

install(
    FILES __init__.py session_key_derivation.py sync_burst_utils.py key_injector.py
    DESTINATION ${kgdss_python_install_dir}
    COMPONENT pythonapi
)

