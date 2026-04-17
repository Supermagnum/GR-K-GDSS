/*
 * Keyed GDSS Spreader - spreads complex symbols using keyed Gaussian-distributed sequence
 *
 * Input: complex stream (one symbol per call; interpolates to chips_per_symbol samples).
 * Output: complex stream (chips_per_symbol samples per input symbol), masked so that
 * the waveform is statistically similar to Gaussian noise without the key.
 *
 * Parameters:
 *   sequence_length - length of internal spreading sequence (e.g. 256).
 *   chips_per_symbol - interpolation factor (samples out per symbol in); typically 256.
 *   variance - Gaussian mask variance (e.g. 1.0).
 *   seed - RNG seed when key not set; 0 = use time-based seed.
 *   chacha_key - 32-byte ChaCha20 key; empty to defer (use set_key message).
 *   chacha_nonce - 12-byte ChaCha20 IETF nonce; empty if key empty.
 *
 * Message port "set_key": PMT dict with "key" (u8vector 32) and "nonce" (u8vector 12).
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

    /** sequence_length and chips_per_symbol positive; variance > 0; key 0 or 32 bytes; nonce 0 or 12 bytes. */
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
    virtual void set_counter(uint64_t counter);
    virtual bool get_overflow_occurred() const;

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

