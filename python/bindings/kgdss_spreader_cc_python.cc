/*
 * Keyed GDSS Spreader Python bindings
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#include <pybind11/complex.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

#include <gnuradio/kgdss/kgdss_spreader_cc.h>

void bind_kgdss_spreader_cc(py::module& m)
{
    using kgdss_spreader_cc = gr::kgdss::kgdss_spreader_cc;

    py::class_<kgdss_spreader_cc,
               gr::sync_interpolator,
               gr::block,
               gr::basic_block,
               std::shared_ptr<kgdss_spreader_cc>>(m, "kgdss_spreader_cc")
        .def(py::init([](int sequence_length,
                         int chips_per_symbol,
                         float variance,
                         unsigned int seed,
                         py::bytes key_bytes,
                         py::bytes nonce_bytes) {
                 std::string sk = key_bytes, sn = nonce_bytes;
                 std::vector<uint8_t> key(sk.begin(), sk.end());
                 std::vector<uint8_t> nonce(sn.begin(), sn.end());
                 return kgdss_spreader_cc::make(sequence_length,
                                               chips_per_symbol,
                                               variance,
                                               seed,
                                               key,
                                               nonce);
             }),
             py::arg("sequence_length"),
             py::arg("chips_per_symbol"),
             py::arg("variance"),
             py::arg("seed"),
             py::arg("chacha_key"),
             py::arg("chacha_nonce"),
             "Make a Keyed GDSS spreader block")
        .def("set_spreading_sequence",
             &kgdss_spreader_cc::set_spreading_sequence,
             py::arg("sequence"))
        .def("set_chips_per_symbol",
             &kgdss_spreader_cc::set_chips_per_symbol,
             py::arg("chips_per_symbol"))
        .def("regenerate_sequence",
             &kgdss_spreader_cc::regenerate_sequence,
             py::arg("variance"),
             py::arg("seed") = 0)
        .def("get_spreading_sequence", &kgdss_spreader_cc::get_spreading_sequence);
}
