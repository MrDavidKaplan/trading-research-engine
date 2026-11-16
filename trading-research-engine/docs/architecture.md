# Architecture

## Responsibility boundaries

| Layer | Files | Owns |
| --- | --- | --- |
| Input | `models.py`, `data.py` | Validated parameters and chronological OHLCV bars |
| Signal | `strategy.py` | Rolling close history and long/flat decisions |
| Event loop | `engine.py` | Order timing, positions, cash, valuation, audit events |
| Execution | `execution.py`, `native/execution.cpp` | Participation cap, transaction price, commission, affordability |
| Research | `research.py`, `metrics.py` | Split discipline, comparator construction, sensitivity, metrics |
| Output | `report.py`, `cli.py` | Reproduction manifest, exports, offline report, command line |

The execution kernel is stateless. It takes a desired total position, current position/cash, current open, and previous volume; it returns one signed fill. Portfolio state stays in one place: the Python event loop. This makes the C++ boundary small enough to test exhaustively without maintaining two independent portfolio implementations.

## Event contract

For each bar in an evaluation interval:

1. **OPEN**: observe the current open. A target created at the prior close becomes eligible.
2. **FILL**: evaluate the order using that open, prior-bar volume, and available cash. Apply signed quantity and commission exactly once.
3. **EXPIRE**: discard any unfilled portion; it cannot silently execute again.
4. **CLOSE**: mark existing inventory at the completed close; update the signal.
5. **ORDER**: derive a fresh desired share position from that close's information.

At the last close, cancel the new target because no next bar exists. Keep any current position in the final mark-to-market value.

`OPEN`, `CLOSE`, and `ORDER` are recorded even when nothing trades. `FILL` appears only for nonzero quantity. `EXPIRE` is recorded only when an eligible order is not completely filled. The orders ledger contains `FILLED`, `PARTIAL`, `UNFILLED`, or `CANCELLED_END` status. A zero-change target resolves as `FILLED` with zero quantity and zero commission.

## State and accounting

A fill's quantity is positive for buys and negative for sells:

```text
cash_new = cash_old - signed_quantity * fill_price - commission
position_new = position_old + signed_quantity
equity_at_close = cash_new + position_new * close
```

The simulator enforces nonnegative cash and nonnegative inventory. It does not borrow, short, or create fractional shares. The idealized comparator permits fractional shares but still checks cash at the next open.

All prices and cash use IEEE 754 double precision. There is no tick-size rounding or cent-level fee rounding. This is deliberate for model comparison; production accounting would require instrument-specific rounding and reconciliation policies. A tiny negative numerical cash residue is clamped only after a strict invariant check.

## Order sizing and replacement

A target is a desired **total position**, not an incremental order. For a long signal it is `floor(allocation * equity / close)`; for a flat signal it is zero. At the next open, requested quantity is `target - current_position`.

Targets are recalculated daily, so a persistent signal can cause small rebalancing trades. A partially filled target does not become a persistent queue entry. The next completed close produces a new target, which can reverse the old intent. This policy is visible in the order and event ledgers.

## Native interface

`te_version()` returns ABI version 1. `te_execute(...)` uses `int64_t` for quantities and `double` for money/parameters. It fills a caller-owned `Fill` struct and returns 0 on success or 1 for invalid inputs. C linkage prevents C++ name mangling; `ctypes` supplies the exact field order and argument types.

The output fields are signed quantity, execution price, commission, spread cost, slippage cost, and impact cost. Spread/slippage/impact are already embedded in execution price. Only commission is separately subtracted from cash. Subtracting the other three again would double-count costs.

The normal public entry point validates data and configuration before execution. The low-level Python broker expects valid nonnegative targets/positions and validated config; it is a reference kernel, not a hardened standalone public API. The native function adds defensive numeric checks at its ABI boundary.

## Why the implementation is small

There is no message broker, database, external data service, web server, or heavyweight analytics dependency. These are unnecessary for replaying one daily series, and each would complicate reproducibility. The HTML report embeds its charts and CSS. CSV/JSON files remain available for further analysis in a notebook or spreadsheet.
