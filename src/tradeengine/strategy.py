"""A deliberately simple, causal long/flat moving-average signal."""
from collections import deque
from math import fsum


class MovingAverage:
    def __init__(self, fast, slow):
        if not 1 <= fast < slow:
            raise ValueError("Require 1 <= fast < slow")
        self.fast = deque(maxlen=fast)
        self.slow = deque(maxlen=slow)

    def update(self, close):
        """Consume one completed close; return 1 for long, 0 for flat."""
        self.fast.append(close)
        self.slow.append(close)
        if len(self.slow) < self.slow.maxlen:
            return 0
        return int(fsum(self.fast) / len(self.fast) > fsum(self.slow) / len(self.slow))


def signals(bars, fast, slow):
    model = MovingAverage(fast, slow)
    return [model.update(bar.close) for bar in bars]
