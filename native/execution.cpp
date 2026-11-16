// Stateless C++17 execution kernel. Python owns event order and portfolio state.
#include <algorithm>
#include <cmath>
#include <cstdint>

#if defined(_WIN32)
#define TE_EXPORT __declspec(dllexport)
#else
#define TE_EXPORT __attribute__((visibility("default")))
#endif

extern "C" {
struct Fill {
    std::int64_t quantity;
    double price, commission, spread_cost, slippage_cost, impact_cost;
};
TE_EXPORT int te_version() { return 1; }

TE_EXPORT int te_execute(std::int64_t target, std::int64_t position,
                        double cash, double reference, std::int64_t volume,
                        double participation, double spread_bps, double slippage_bps,
                        double impact_bps, double per_share, double minimum_fee,
                        Fill* out) {
    if (!out || target < 0 || position < 0 || volume < 0 || volume > 1000000000000LL ||
        !std::isfinite(cash) || cash < 0 || !std::isfinite(reference) || reference <= 0 ||
        !std::isfinite(participation) || participation <= 0 || participation > 1 ||
        !std::isfinite(spread_bps) || spread_bps < 0 ||
        !std::isfinite(slippage_bps) || slippage_bps < 0 ||
        !std::isfinite(impact_bps) || impact_bps < 0 ||
        !std::isfinite(per_share) || per_share < 0 ||
        !std::isfinite(minimum_fee) || minimum_fee < 0 ||
        spread_bps / 2 + slippage_bps + impact_bps >= 10000) return 1;
    *out = {0, reference, 0, 0, 0, 0};
    const auto delta = target - position;
    const int side = delta > 0 ? 1 : -1;
    auto q = std::min(delta >= 0 ? delta : -delta,
                     static_cast<std::int64_t>(std::floor(participation * volume)));
    if (side < 0) q = std::min(q, position);
    const double half = reference * spread_bps / 20000.0;
    const double slip = reference * slippage_bps / 10000.0;
    auto price = [&](std::int64_t n) {
        return reference + side * (half + slip + reference * impact_bps / 10000.0 *
                                    n / std::max<std::int64_t>(volume, 1));
    };
    auto fee = [&](std::int64_t n) { return n ? std::max(minimum_fee, n * per_share) : 0.0; };
    if (side > 0) {
        std::int64_t low = 0, high = q;
        while (low < high) {
            const auto mid = low + (high - low + 1) / 2;
            if (mid * price(mid) + fee(mid) <= cash) low = mid;
            else high = mid - 1;
        }
        q = low;
    }
    if (!q || (side < 0 && cash + q * price(q) < fee(q))) return 0;
    *out = {side * q, price(q), fee(q), q * half, q * slip,
            q * reference * impact_bps / 10000.0 * q / std::max<std::int64_t>(volume, 1)};
    return 0;
}
}
