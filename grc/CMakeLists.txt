include(GNUInstallDirs)

install(
    FILES
        ${CMAKE_CURRENT_SOURCE_DIR}/kgdss_spreader_cc.block.yml
        ${CMAKE_CURRENT_SOURCE_DIR}/kgdss_despreader_cc.block.yml
    DESTINATION ${CMAKE_INSTALL_DATAROOTDIR}/gnuradio/grc/blocks
)

