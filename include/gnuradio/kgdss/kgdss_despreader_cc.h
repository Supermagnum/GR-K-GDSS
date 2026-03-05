/*
 * Keyed GDSS Despreader/Correlator - despreads GDSS signal and recovers symbols
 *
 * Input: complex stream (chips_per_symbol samples per symbol).
 * Outputs: [0] complex despread symbols; [1] lock indicator (0 or 1 float); [2] SNR estimate (float dB).
 *
 * Parameters:
 *   spreading_sequence - reference sequence (length or 2*length for I,Q); can be placeholder when using key.
 *   chips_per_symbol - decimation factor (samples in per symbol out); must match spreader.
 *   correlation_threshold - base threshold for lock detection (adaptive threshold applied).
 *   timing_error_tolerance - max timing offset in samples for tracking.
 *   chacha_key - 32-byte ChaCha20 key; empty to defer (use set_key message).
 *   chacha_nonce - 12-byte ChaCha20 IETF nonce; empty if key empty.
 *
 * Message port "set_key": PMT dict with "key" (u8vector 32) and "nonce" (u8vector 12).
 * get_sync_state(), is_locked(), get_snr_estimate(), get_last_soft_metric(), get_frequency_error() for status.
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

    /** spreading_sequence non-empty; chips_per_symbol > 0; key 0 or 32 bytes; nonce 0 or 12 bytes. */
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

