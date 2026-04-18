/*
 * Keyed GDSS Despreader Python bindings
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#include <pybind11/complex.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

#include <gnuradio/kgdss/kgdss_despreader_cc.h>

void bind_kgdss_despreader_cc(py::module& m)
{
    using kgdss_despreader_cc = gr::kgdss::kgdss_despreader_cc;

    py::class_<kgdss_despreader_cc,
               gr::block,
               gr::basic_block,
               std::shared_ptr<kgdss_despreader_cc>>(m, "kgdss_despreader_cc")
        .def(py::init([](const std::vector<float>& spreading_sequence,
                         int chips_per_symbol,
                         float correlation_threshold,
                         int timing_error_tolerance,
                         py::bytes key_bytes,
                         py::bytes nonce_bytes) {
                 std::string sk = key_bytes, sn = nonce_bytes;
                 std::vector<uint8_t> key(sk.begin(), sk.end());
                 std::vector<uint8_t> nonce(sn.begin(), sn.end());
                 return kgdss_despreader_cc::make(spreading_sequence,
                                                 chips_per_symbol,
                                                 correlation_threshold,
                                                 timing_error_tolerance,
                                                 key,
                                                 nonce);
             }),
             py::arg("spreading_sequence"),
             py::arg("chips_per_symbol"),
             py::arg("correlation_threshold"),
             py::arg("timing_error_tolerance"),
             py::arg("chacha_key"),
             py::arg("chacha_nonce"),
             "Make a Keyed GDSS despreader block")
        .def("set_spreading_sequence",
             &kgdss_despreader_cc::set_spreading_sequence,
             py::arg("spreading_sequence"))
        .def("set_chips_per_symbol",
             &kgdss_despreader_cc::set_chips_per_symbol,
             py::arg("chips_per_symbol"))
        .def("get_sync_state", &kgdss_despreader_cc::get_sync_state)
        .def("is_locked", &kgdss_despreader_cc::is_locked)
        .def("get_snr_estimate", &kgdss_despreader_cc::get_snr_estimate)
        .def("get_last_soft_metric", &kgdss_despreader_cc::get_last_soft_metric)
        .def("get_frequency_error", &kgdss_despreader_cc::get_frequency_error)
        .def("set_counter", &kgdss_despreader_cc::set_counter, py::arg("counter"))
        .def("get_overflow_occurred", &kgdss_despreader_cc::get_overflow_occurred)
        .def("set_channel_equalization",
             &kgdss_despreader_cc::set_channel_equalization,
             py::arg("enable"))
        .def("get_channel_equalization", &kgdss_despreader_cc::get_channel_equalization);

    py::enum_<kgdss_despreader_cc::sync_state>(m, "kgdss_sync_state")
        .value("STATE_ACQUISITION", kgdss_despreader_cc::STATE_ACQUISITION)
        .value("STATE_TRACKING", kgdss_despreader_cc::STATE_TRACKING)
        .value("STATE_LOCKED", kgdss_despreader_cc::STATE_LOCKED);
}
