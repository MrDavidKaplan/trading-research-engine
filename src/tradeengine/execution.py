"""Interchangeable Python/C++ fill kernels with the same conservative rules."""
import ctypes
from dataclasses import dataclass
from math import floor
from pathlib import Path


@dataclass(frozen=True)
class Fill:
    quantity: int  # Signed: positive buy, negative sell.
    price: float
    commission: float
    spread_cost: float
    slippage_cost: float
    impact_cost: float


class PythonBroker:
    name = "python"

    def execute(self, target, position, cash, reference, volume, config):
        """Fill a target at the next open using PREVIOUS-bar volume as a proxy.

        A fresh target replaces yesterday's remainder. Buy fills are reduced by
        binary search until price plus commission is affordable. No borrowing.
        """
        delta = target - position
        capacity = floor(config.participation * volume)
        quantity = min(abs(delta), capacity)
        if delta < 0:
            quantity = min(quantity, position)
        side = 1 if delta > 0 else -1

        def quote(q):
            half = reference * config.spread_bps / 20_000
            slip = reference * config.slippage_bps / 10_000
            impact = reference * config.impact_bps / 10_000 * q / max(volume, 1)
            price = reference + side * (half + slip + impact)
            fee = max(config.minimum_commission, q * config.commission_per_share) if q else 0.0
            return price, fee, half, slip, impact

        if side > 0:
            low, high = 0, quantity
            while low < high:
                mid = (low + high + 1) // 2
                price, fee, *_ = quote(mid)
                if mid * price + fee <= cash:
                    low = mid
                else:
                    high = mid - 1
            quantity = low
        if quantity == 0:
            return Fill(0, reference, 0.0, 0.0, 0.0, 0.0)
        price, fee, half, slip, impact = quote(quantity)
        # Do not allow a tiny sell to leave the account with negative cash.
        if side < 0 and cash + quantity * price < fee:
            return Fill(0, reference, 0.0, 0.0, 0.0, 0.0)
        return Fill(side * quantity, price, fee, quantity * half, quantity * slip, quantity * impact)


class _NativeFill(ctypes.Structure):
    _fields_ = [("quantity", ctypes.c_int64), ("price", ctypes.c_double),
                ("commission", ctypes.c_double), ("spread_cost", ctypes.c_double),
                ("slippage_cost", ctypes.c_double), ("impact_cost", ctypes.c_double)]


class NativeBroker:
    name = "cpp"

    def __init__(self, library):
        self.lib = ctypes.CDLL(str(Path(library).resolve()))
        self.lib.te_version.restype = ctypes.c_int
        if self.lib.te_version() != 1:
            raise ValueError("Native execution ABI version mismatch")
        fn = self.lib.te_execute
        fn.argtypes = [ctypes.c_int64, ctypes.c_int64, ctypes.c_double, ctypes.c_double,
                       ctypes.c_int64, *([ctypes.c_double] * 6), ctypes.POINTER(_NativeFill)]
        fn.restype = ctypes.c_int
        self.fn = fn

    def execute(self, target, position, cash, reference, volume, config):
        result = _NativeFill()
        status = self.fn(target, position, cash, reference, volume, config.participation,
                         config.spread_bps, config.slippage_bps, config.impact_bps,
                         config.commission_per_share, config.minimum_commission,
                         ctypes.byref(result))
        if status:
            raise ValueError("Native execution rejected invalid input")
        return Fill(*(getattr(result, name) for name, _ in result._fields_))
