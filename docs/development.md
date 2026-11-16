# Development

## Local workflow

There are no required Python runtime packages. Use Python 3.10+ and optionally GCC/Clang/MSVC. Run commands from the repository root.

```bash
python -m unittest discover -s tests -v
python scripts/build_native.py
python -m unittest discover -s tests -v
python run.py demo --select --output outputs/development
```

The first test run can skip native tests. The second should run them after compilation. CI repeats build, tests, and demo on its configured OS/Python matrix. Native tests compare quantities exactly and floating-point fields within tolerance.

## Change the signal

`MovingAverage.update(close)` returns a long/flat state. To add a different strategy, first define which information is observable at decision time. Replace or generalize `signals()` while preserving chronological updates. Both `simulate()` and `idealized()` must consume the same signal definition. Expose parameters in `Config`, validate them, and add prefix-invariance tests before interpreting results.

An opening-gap strategy needs a different information/event contract: the opening gap is not known at yesterday's close. It cannot honestly be dropped into this close-to-next-open model without defining a later executable entry. Options need contract selection, expiry, strike, bid/ask, greeks, assignment, and separate data. Those are extensions, not implemented features.

## Change execution

Implement the same `execute(target, position, cash, reference, volume, config) -> Fill` contract. Keep cost components positive and encode trading direction only in signed quantity and price adjustment. Do not mutate portfolio state in a broker.

When changing C++, update the Python reference and add a hand-derived expected result. Randomized parity alone can miss shared mistakes. If the struct layout or function signature changes, increment `te_version()` and update the ctypes signature together. Rebuild after source changes; the runtime ABI check cannot detect an old binary with unchanged ABI and different model logic.

## Test design

Tests cover:

- Known buy/sell price and commission examples.
- Insufficient cash, zero volume, participation caps and tiny-sale fee rejection.
- Next-open fill timing, final cancellation and partial-order replacement.
- Prefix invariance when future prices change.
- Exact cash/inventory reconciliation and direct-cost identities.
- Chronological holdout isolation and identical target replay.
- CSV/config failure cases and reproducible demo bytes.
- Full-run and 1,000 randomized C++/Python execution comparisons.

Use deterministic local seeds in randomized tests. Test behavioral contracts, not private implementation details.

## Troubleshooting

| Symptom | Resolution |
| --- | --- |
| `python` not found | Try `python3` (macOS/Linux) or `py` (Windows) |
| No compiler | Use Python backend; install your platform's compiler before native build |
| Native library cannot load | Build on this machine and pass the printed absolute path |
| ABI mismatch | Rebuild native source from the current checkout |
| Output already exists | Choose a new output folder |
| Not enough training bars | Provide more observations, reduce the slow window, or use a valid split |
| CSV row error | Fix the specified record; the engine deliberately does not guess repairs |
| HTML looks like source on GitHub | Download it and open locally |
| No trades | Inspect signals, volume, cash, and the orders ledger; flat/no-fill runs are valid |

## Scope for future work

Useful next steps are broker-specific cost calibration, timestamped multi-instrument data, explicit corporate actions, walk-forward evaluation, and a batch native replay API if measured workloads justify it. None is required to reproduce the current single-instrument experiment.
