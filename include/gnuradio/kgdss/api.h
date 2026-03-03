/*
 * gr-k-gdss - Keyed Gaussian-Distributed Spread-Spectrum
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#ifndef INCLUDED_KGDSS_API_H
#define INCLUDED_KGDSS_API_H

#include <gnuradio/attributes.h>

#ifdef gnuradio_kgdss_EXPORTS
#define KGDSS_API __GR_ATTR_EXPORT
#else
#define KGDSS_API __GR_ATTR_IMPORT
#endif

#endif /* INCLUDED_KGDSS_API_H */

