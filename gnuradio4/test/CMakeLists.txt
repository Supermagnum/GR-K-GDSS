function(gr_k_gdss4_add_ut name)
  add_executable(${name} ${name}.cpp)
  target_compile_features(${name} PRIVATE cxx_std_23)
  target_link_libraries(
    ${name}
    PRIVATE gnuradio4::gnuradio-options gnuradio4::gnuradio-core gnuradio4::gnuradio-blocklib-core
            gnuradio4::gr-testing gnuradio4::gr-k-gdss ut)
  add_test(NAME ${name} COMMAND ${CMAKE_CROSSCOMPILING_EMULATOR} $<TARGET_FILE:${name}>)
endfunction()

gr_k_gdss4_add_ut(qa_ChachaKeystreamHelper)
gr_k_gdss4_add_ut(qa_KgdssSpreaderCc)
gr_k_gdss4_add_ut(qa_KgdssDespreaderCc)
