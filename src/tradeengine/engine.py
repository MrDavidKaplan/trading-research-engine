"""Close -> order -> next open -> fill -> close valuation event loop."""
from dataclasses import dataclass, asdict
from math import floor, isfinite
from .execution import PythonBroker
from .strategy import signals

MAX_SHARES = 10**12


@dataclass
class Result:
    equity: list
    orders: list
    fills: list
    events: list


def simulate(bars, config, broker=None, start=None, end=None, targets=None):
    """Simulate [start, end), flat at start, without forced final liquidation.

    Targets is an optional fixed list of desired share counts indexed by decision
    bar, used for matched-order cost attribution. Normal runs size at each close.
    Earlier bars warm the signal only: they do not pre-position the portfolio.
    """
    broker = broker or PythonBroker()
    start = config.slow - 1 if start is None else start
    end = len(bars) if end is None else end
    if not 0 <= start < end <= len(bars) or end - start < 2:
        raise ValueError("Simulation requires at least two bars in the selected interval")
    if targets is not None and len(targets) != len(bars):
        raise ValueError("targets must match the full input length")
    states = signals(bars, config.fast, config.slow)
    cash, position = config.initial_cash, 0
    equity, orders, fills, events = [], [], [], []
    pending = None
    for i in range(start, end):
        bar = bars[i]
        day = bar.date.isoformat()
        events.append(dict(date=day, phase="OPEN", detail="market open"))
        if pending is not None:
            desired = pending["target"]
            requested = desired - position
            fill = broker.execute(desired, position, cash, bar.open, bars[i-1].volume, config)
            cash -= fill.quantity * fill.price + fill.commission
            position += fill.quantity
            if cash < -1e-7 or position < 0 or not isfinite(cash):
                raise ArithmeticError("Portfolio invariant violated")
            cash = max(cash, 0.0)  # Clamp sub-cent floating-point residue only.
            pending.update(execution_date=day, requested=requested, filled=fill.quantity,
                           unfilled=requested-fill.quantity,
                           status="FILLED" if fill.quantity == requested else "PARTIAL" if fill.quantity else "UNFILLED")
            if fill.quantity:
                fills.append(dict(order_id=pending["order_id"], date=day, reference=bar.open,
                                  reference_volume=bars[i-1].volume, **asdict(fill)))
                events.append(dict(date=day, phase="FILL", detail=f"order {pending['order_id']}: {fill.quantity} shares"))
            if requested != fill.quantity:
                events.append(dict(date=day, phase="EXPIRE", detail=f"order {pending['order_id']}: {requested-fill.quantity} shares unfilled"))
        value = cash + position * bar.close
        equity.append(dict(date=day, cash=cash, position=position, close=bar.close,
                           equity=value, signal=states[i]))
        events.append(dict(date=day, phase="CLOSE", detail="mark positions and observe signal"))
        target = (floor(value * config.allocation / bar.close) if states[i] else 0) if targets is None else targets[i]
        if type(target) is not int or not 0 <= target <= MAX_SHARES:
            raise ValueError("Target must be an integer in [0, 1e12]")
        pending = dict(order_id=len(orders)+1, decision_date=day, target=target,
                       execution_date="", requested=0, filled=0, unfilled=0, status="CANCELLED_END")
        orders.append(pending)
        events.append(dict(date=day, phase="ORDER", detail=f"target {target} for next open"))
    events.append(dict(date=bars[end-1].date.isoformat(), phase="CANCEL", detail="no next bar: final target cancelled"))
    return Result(equity, orders, fills, events)


def idealized(bars, config, start, end):
    """Fractional shares, no costs/cap, prior-close instruction at next open.

    Desired shares use equity and close available at decision time; exposure can
    drift across the overnight gap. This is not a same-close return shortcut.
    """
    states = signals(bars, config.fast, config.slow)
    cash, shares, target = config.initial_cash, 0.0, 0.0
    rows = []
    for i in range(start, end):
        if i > start:
            delta = target - shares
            if delta > 0:
                delta = min(delta, cash / bars[i].open)
            cash -= delta * bars[i].open
            shares += delta
        value = cash + shares * bars[i].close
        rows.append(dict(date=bars[i].date.isoformat(), equity=value))
        target = value * config.allocation / bars[i].close if states[i] else 0.0
    return rows
