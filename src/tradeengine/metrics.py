"""Metrics on equally spaced daily close valuations; zero cash/risk-free rate."""
import math
import statistics


def summarize(rows, initial_cash, annualization=252):
    values = [row["equity"] for row in rows]
    returns = []
    for previous, current in zip(values, values[1:]):
        if previous == 0:
            if current != 0:
                raise ValueError("Equity cannot recover from zero without external cash flows")
            returns.append(0.0)  # A bankrupt cash account remains at zero.
        else:
            returns.append(current / previous - 1)
    total = values[-1] / initial_cash - 1
    periods = len(returns)
    deviation = statistics.stdev(returns) if len(returns) > 1 else 0.0
    peak, worst = initial_cash, 0.0
    for value in values:
        peak = max(peak, value)
        worst = min(worst, value / peak - 1)
    return dict(final_equity=values[-1], total_return=total,
                cagr=(values[-1] / initial_cash)**(annualization / periods)-1 if periods else None,
                volatility=deviation * math.sqrt(annualization),
                sharpe=statistics.mean(returns) / deviation * math.sqrt(annualization) if deviation else None,
                max_drawdown=worst, periods=periods)


def cost_summary(fills):
    names = ("commission", "spread_cost", "slippage_cost", "impact_cost")
    result = {name: math.fsum(row[name] for row in fills) for name in names}
    result["total_cost"] = math.fsum(result.values())
    result["fill_count"] = len(fills)
    result["traded_notional"] = math.fsum(abs(row["quantity"]) * row["reference"] for row in fills)
    return result
