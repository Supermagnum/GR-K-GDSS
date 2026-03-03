/*
 * Keyed GDSS Spreader - spreads complex symbols using keyed Gaussian-distributed sequence
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#ifndef INCLUDED_KGDSS_SPREADER_CC_H
#define INCLUDED_KGDSS_SPREADER_CC_H

#include <gnuradio/kgdss/api.h>
#include <gnuradio/sync_interpolator.h>
#include <vector>
#include <cstdint>

namespace gr {
namespace kgdss {

class KGDSS_API kgdss_spreader_cc : public sync_interpolator
{
public:
    typedef std::shared_ptr<kgdss_spreader_cc> sptr;

    static sptr make(int sequence_length,
                     int chips_per_symbol,
                     float variance,
                     unsigned int seed,
                     const std::vector<uint8_t>& chacha_key,
                     const std::vector<uint8_t>& chacha_nonce);

    virtual void set_spreading_sequence(const std::vector<float>& sequence);
    virtual void set_chips_per_symbol(int chips_per_symbol);
    virtual void regenerate_sequence(float variance, unsigned int seed);
    virtual std::vector<float> get_spreading_sequence() const;

    virtual ~kgdss_spreader_cc();

protected:
    kgdss_spreader_cc(const std::string& name,
                      gr::io_signature::sptr input_signature,
                      gr::io_signature::sptr output_signature,
                      int sequence_length,
                      int chips_per_symbol,
                      float variance,
                      unsigned int seed)
        : sync_interpolator(name, input_signature, output_signature, chips_per_symbol)
    {
        (void)sequence_length;
        (void)variance;
        (void)seed;
    }
};

} // namespace kgdss
} // namespace gr

#endif /* INCLUDED_KGDSS_SPREADER_CC_H */

