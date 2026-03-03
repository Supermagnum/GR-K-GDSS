set(gr_kgdss_sources
    kgdss_spreader_cc_impl.cc
    kgdss_despreader_cc_impl.cc
)

add_library(
    gnuradio-kgdss
    ${gr_kgdss_sources}
)

set_target_properties(
    gnuradio-kgdss
    PROPERTIES POSITION_INDEPENDENT_CODE ON
)

target_link_libraries(
    gnuradio-kgdss PUBLIC
    ${GR_RUNTIME_LIBRARIES}
    ${GR_BLOCKS_LIBRARIES}
)

if(SODIUM_FOUND)
    target_link_libraries(
        gnuradio-kgdss PUBLIC
        ${SODIUM_LIBRARIES}
    )
    target_include_directories(
        gnuradio-kgdss PUBLIC
        ${SODIUM_INCLUDE_DIRS}
    )
else()
    target_link_libraries(
        gnuradio-kgdss PUBLIC
        OpenSSL::SSL
        OpenSSL::Crypto
    )
endif()

target_include_directories(
    gnuradio-kgdss PUBLIC
    ${GR_RUNTIME_INCLUDE_DIRS}
    ${GR_BLOCKS_INCLUDE_DIRS}
    ${CMAKE_CURRENT_SOURCE_DIR}/../include
)

