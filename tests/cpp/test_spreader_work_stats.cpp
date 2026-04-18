/*
 * GTest: kgdss_spreader_cc work() Box-Muller mask statistics. A real-valued
 * input symbol (1,0) makes out = symbol * mask equal mask directly, so the
 * I/Q components of the output are the raw mask_i / mask_q values and the
 * per-chip clamp and Gaussian fit can be tested without sum/difference
 * cancellation. Uses public block API only.
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#include <gnuradio/kgdss/kgdss_spreader_cc.h>

#include <gtest/gtest.h>

#include <algorithm>
#include <cmath>
#include <cstring>
#include <numeric>
#include <vector>

namespace {

constexpr float kMinMask = 1e-4f;

double normal_cdf(double z)
{
    return 0.5 * (1.0 + std::erf(z / std::sqrt(2.0)));
}

/* Two-sided K-S statistic D for sorted standardised samples vs N(0,1). */
double ks_D(const std::vector<double>& z_sorted)
{
    const size_t n = z_sorted.size();
    if (n == 0)
        return 1.0;
    double D = 0.0;
    for (size_t i = 0; i < n; i++) {
        const double x = z_sorted[i];
        const double F = normal_cdf(x);
        const double F_lo = static_cast<double>(i) / static_cast<double>(n);
        const double F_hi = static_cast<double>(i + 1) / static_cast<double>(n);
        D = std::max(D, std::abs(F - F_lo));
        D = std::max(D, std::abs(F_hi - F));
    }
    return D;
}

} // namespace

TEST(SpreaderWorkStats, BoxMullerGaussianApproximation)
{
    const int sequence_length = 64;
    const int chips_per_symbol = 256;
    const float variance = 1.0f;
    const unsigned seed = 12345;
    std::vector<uint8_t> key(32);
    std::vector<uint8_t> nonce(12);
    for (int i = 0; i < 32; i++)
        key[i] = static_cast<uint8_t>(i + 0x20);
    for (int i = 0; i < 12; i++)
        nonce[i] = static_cast<uint8_t>(i ^ 0x33);

    gr::kgdss::kgdss_spreader_cc::sptr sp =
        gr::kgdss::kgdss_spreader_cc::make(
            sequence_length, chips_per_symbol, variance, seed, key, nonce);

    const int n_sym = 3907;
    const int n_out = n_sym * chips_per_symbol;
    std::vector<gr_complex> in_buf(n_sym, gr_complex(1.0f, 0.0f));
    std::vector<gr_complex> out_buf(n_out);

    gr_vector_const_void_star ins(1);
    gr_vector_void_star outs(1);
    ins[0] = in_buf.data();
    outs[0] = out_buf.data();

    const int produced = sp->work(n_out, ins, outs);
    ASSERT_EQ(produced, n_out);

    std::vector<double> mi;
    mi.reserve(static_cast<size_t>(n_out));
    for (int i = 0; i < n_out; i++) {
        const float re = out_buf[i].real();
        const float im = out_buf[i].imag();
        mi.push_back(re);
        ASSERT_GE(std::abs(re), kMinMask) << "mask_i clamp at " << i;
        ASSERT_GE(std::abs(im), kMinMask) << "mask_q clamp at " << i;
    }

    const double sum =
        std::accumulate(mi.begin(), mi.end(), 0.0, [](double a, double b) { return a + b; });
    const double mean = sum / static_cast<double>(mi.size());
    ASSERT_NEAR(mean, 0.0, 0.01);

    double var_sum = 0.0;
    for (double x : mi) {
        const double d = x - mean;
        var_sum += d * d;
    }
    const double var = var_sum / static_cast<double>(mi.size() - 1);
    ASSERT_NEAR(var, static_cast<double>(variance), 0.01 * static_cast<double>(variance));

    std::vector<double> z = mi;
    const double s = std::sqrt(var + 1e-30);
    for (double& x : z)
        x = (x - mean) / s;
    std::sort(z.begin(), z.end());
    const double D = ks_D(z);
    const double n = static_cast<double>(z.size());
    const double crit = 1.63 / std::sqrt(n);
    ASSERT_GT(D, 0.0);
    ASSERT_LT(D, crit) << "K-S style check: D=" << D << " crit(approx p>0.01)=" << crit;
}
