/*
 * Keyed GDSS Despreader/Correlator - despreads GDSS signal and recovers symbols
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#ifndef INCLUDED_KGDSS_DESPREDER_CC_H
#define INCLUDED_KGDSS_DESPREDER_CC_H

#include <gnuradio/kgdss/api.h>
#include <gnuradio/block.h>
#include <vector>

namespace gr {
namespace kgdss {

class KGDSS_API kgdss_despreader_cc : public block
{
public:
    typedef std::shared_ptr<kgdss_despreader_cc> sptr;

    enum sync_state {
        STATE_ACQUISITION,
        STATE_TRACKING,
        STATE_LOCKED
    };

    static sptr make(const std::vector<float>& spreading_sequence,
                     int chips_per_symbol,
                     float correlation_threshold,
                     int timing_error_tolerance,
                     const std::vector<uint8_t>& chacha_key,
                     const std::vector<uint8_t>& chacha_nonce);

    virtual void set_spreading_sequence(const std::vector<float>& spreading_sequence);
    virtual void set_chips_per_symbol(int chips_per_symbol);
    virtual sync_state get_sync_state() const;
    virtual bool is_locked() const;
    virtual float get_snr_estimate() const;
    virtual float get_last_soft_metric() const;
    virtual float get_frequency_error() const;

    virtual ~kgdss_despreader_cc();

protected:
    kgdss_despreader_cc(const std::string& name,
                        gr::io_signature::sptr input_signature,
                        gr::io_signature::sptr output_signature,
                        const std::vector<float>& spreading_sequence,
                        int chips_per_symbol,
                        float correlation_threshold,
                        int timing_error_tolerance)
        : block(name, input_signature, output_signature)
    {
        (void)spreading_sequence;
        (void)chips_per_symbol;
        (void)correlation_threshold;
        (void)timing_error_tolerance;
    }
};

} // namespace kgdss
} // namespace gr

#endif /* INCLUDED_KGDSS_DESPREDER_CC_H */

