"""Chronological evaluation and matched-order cost experiments."""
from dataclasses import replace
from .engine import simulate, idealized
from .execution import PythonBroker
from .metrics import summarize, cost_summary

GRID = ((10, 40), (20, 60), (40, 120))


def evaluate(bars, config, broker=None, select=False):
    """Select parameters on training data only, then start holdout flat.

    The optional grid has a common training start so candidates see identical
    dates. Warm-up history carries into holdout; cash and positions do not.
    """
    broker = broker or PythonBroker()
    split = int(len(bars) * config.train_fraction)
    warmup = max(slow for _, slow in GRID) - 1 if select else config.slow - 1
    if split - warmup < 30 or len(bars) - split < 30:
        raise ValueError("Need >=30 training and holdout bars after warm-up; supply more data")
    candidates = []
    if select:
        for fast, slow in GRID:
            candidate = replace(config, fast=fast, slow=slow)
            result = simulate(bars, candidate, broker, warmup, split)
            stats = summarize(result.equity, candidate.initial_cash, candidate.annualization)
            candidates.append(dict(fast=fast, slow=slow, **stats))
        # Undefined Sharpe ranks last; stable ordering resolves exact ties.
        winner = max(candidates, key=lambda r: r["sharpe"] if r["sharpe"] is not None else float("-inf"))
        config = replace(config, fast=winner["fast"], slow=winner["slow"])
    train = simulate(bars, config, broker, warmup, split)
    net = simulate(bars, config, broker, split, len(bars))
    fixed_targets = [0] * len(bars)
    for i, order in enumerate(net.orders, split):
        fixed_targets[i] = order["target"]
    zero = replace(config, spread_bps=0, slippage_bps=0, impact_bps=0,
                   commission_per_share=0, minimum_commission=0)
    gross = simulate(bars, zero, broker, split, len(bars), fixed_targets)
    ideal = idealized(bars, config, split, len(bars))
    # Buy-and-hold begins at the same first tradable open, with fractional shares.
    entry = bars[split+1].open
    buyhold = [dict(date=b.date.isoformat(), equity=config.initial_cash if i == split
                   else config.initial_cash * b.close / entry)
               for i, b in enumerate(bars[split:], split)]
    curves = {"ideal_signal": ideal, "gross_execution": gross.equity,
              "net_execution": net.equity, "buy_and_hold": buyhold}
    metrics = {name: summarize(rows, config.initial_cash, config.annualization) for name, rows in curves.items()}
    costs = cost_summary(net.fills)
    drag = gross.equity[-1]["equity"] - net.equity[-1]["equity"]
    attribution = dict(gross_minus_net=drag, direct_costs=costs["total_cost"],
                       fill_path_residual=drag-costs["total_cost"],
                       identical_fills=[(f["date"], f["quantity"]) for f in gross.fills] ==
                                       [(f["date"], f["quantity"]) for f in net.fills])
    sensitivity = []
    for multiple in (0.0, 0.5, 1.0, 2.0, 5.0):
        # Extremely large user-defined costs may make a sell price nonpositive.
        # Such scenarios are outside the model; exclude them explicitly.
        if multiple * (config.spread_bps / 2 + config.slippage_bps + config.impact_bps) >= 10_000:
            continue
        scaled = replace(config, **{name: getattr(config, name)*multiple for name in
                         ("spread_bps", "slippage_bps", "impact_bps", "commission_per_share", "minimum_commission")})
        result = simulate(bars, scaled, broker, split, len(bars), fixed_targets)
        sensitivity.append(dict(cost_multiple=multiple,
                                **summarize(result.equity, config.initial_cash, config.annualization),
                                **cost_summary(result.fills)))
    return dict(config=config, split=split, warmup=warmup, candidates=candidates,
                train=train, net=net, gross=gross, curves=curves, metrics=metrics,
                costs=costs, attribution=attribution, sensitivity=sensitivity)
