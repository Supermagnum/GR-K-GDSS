/*
 * gr-k-gdss Python bindings module
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#include <pybind11/pybind11.h>

namespace py = pybind11;

void bind_kgdss_spreader_cc(py::module& m);
void bind_kgdss_despreader_cc(py::module& m);

PYBIND11_MODULE(kgdss_python, m)
{
    py::module::import("gnuradio.gr");

    m.doc() = "Keyed GDSS (Gaussian-Distributed Spread-Spectrum) GNU Radio blocks";

    bind_kgdss_spreader_cc(m);
    bind_kgdss_despreader_cc(m);
}
