"""Strict one-instrument daily OHLCV CSV input and deterministic demo data."""
import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path
from .models import Bar

FIELDS = ["date", "open", "high", "low", "close", "volume"]


def load_bars(path):
    """Reject ambiguous or malformed data; never silently sort or impute."""
    bars = []
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != FIELDS:
            raise ValueError(f"CSV header must be exactly {','.join(FIELDS)}")
        for line, row in enumerate(reader, 2):
            try:
                if None in row or any(v is None for v in row.values()):
                    raise ValueError("wrong number of fields")
                day = date.fromisoformat(row["date"])
                if day.isoformat() != row["date"]:
                    raise ValueError("date must use YYYY-MM-DD")
                prices = [float(row[k]) for k in FIELDS[1:5]]
                volume = int(row["volume"])
                if any(not math.isfinite(p) or not 0 < p <= 1e9 for p in prices):
                    raise ValueError("prices must be finite and in (0, 1e9]")
                op, hi, lo, cl = prices
                if not lo <= min(op, cl) <= max(op, cl) <= hi:
                    raise ValueError("OHLC range is inconsistent")
                if not 0 <= volume <= 10**12:
                    raise ValueError("volume must be an integer in [0, 1e12]")
                if bars and day <= bars[-1].date:
                    raise ValueError("dates must be unique and strictly increasing")
                bars.append(Bar(day, op, hi, lo, cl, volume))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path}: line {line}: {exc}") from exc
    if len(bars) < 3:
        raise ValueError("At least three bars are required")
    return bars


def generate_demo(path, count=900, seed=17):
    """Synthetic regimes, overnight gaps, and low-volume days; no market data."""
    if count < 100:
        raise ValueError("Demo requires at least 100 bars")
    rng = random.Random(seed)
    day, previous = date(2020, 1, 2), 100.0
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(FIELDS)
        for i in range(count):
            while day.weekday() >= 5:
                day += timedelta(days=1)
            drift = (0.0011, -0.0009, 0.0002)[(i // 100) % 3]
            op = previous * math.exp(rng.gauss(0, 0.004))
            cl = op * math.exp(drift + rng.gauss(0, 0.011))
            hi = max(op, cl) * (1 + abs(rng.gauss(0, 0.005)))
            lo = min(op, cl) * (1 - min(0.5, abs(rng.gauss(0, 0.005))))
            volume = rng.randint(1500, 6000) if i % 23 == 0 else rng.randint(20_000, 120_000)
            writer.writerow([day.isoformat(), *(f"{x:.6f}" for x in (op, hi, lo, cl)), volume])
            previous = cl
            day += timedelta(days=1)
    return path
