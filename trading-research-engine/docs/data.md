# Data contract

## Accepted input

UTF-8 CSV (optional UTF-8 BOM), exact ordered header:

`date,open,high,low,close,volume`

One row per completed daily bar, one instrument per file. Dates must use `YYYY-MM-DD`, be unique, and be strictly increasing. The engine rejects duplicates instead of guessing which row is correct.

Prices must be finite, positive, at most 1e9, and satisfy `low <= min(open, close) <= max(open, close) <= high`. Volume must be a nonnegative integer at most 1e12. Extra/missing columns, NaN, infinity, malformed dates, decimal share volumes, and inconsistent ranges fail with a row number. Zero-volume rows are permitted and affect the following bar's capacity.

The loader accepts at least three bars; the research runner requires enough data for training, warm-up, and holdout. With fixed default windows and a 65% training split, 138 bars meet the minimum. Optional grid selection needs at least 230 bars. More data is generally needed for meaningful market research.

## Price basis

Do not mix adjusted closes with unadjusted opens/highs/lows. The engine cannot infer splits or dividends. For raw equity bars spanning a split, share inventory would need a corporate-action adjustment that is not implemented. Such a file is unsuitable without preprocessing.

A consistently split-adjusted series can be used as a simplified research price series, but fixed share counts, adjusted volume, commissions per share, and historical execution interpretation require care. Dividend-adjusted total-return prices are not actual historical executable prices. Record your adjustments and their limitations with the experiment.

The software does not certify data quality, vendor rights, point-in-time availability, delisted-security coverage, or survivorship bias. Keep those as explicit research inputs. If you evaluate multiple tickers later, choosing only current winners would introduce selection bias even if each individual backtest has causal signals.

## Calendars and frequency

No exchange calendar is embedded. Rows are assumed to be equally spaced trading observations. Weekends, exchange holidays, and missing sessions are not checked or filled. `annualization=252` is a modeling convention for daily equity-like series, not a detected fact. Intraday bars cannot be represented with the date-only schema; they require a timestamp/session extension.

The high and low columns currently support input integrity checks only; the model does not execute from them. Open supplies the next eligible reference price, close supplies signals/valuation, and volume supplies the following bar's capacity proxy.

## Bundled fixture

`examples/synthetic.csv` is generated using `generate_demo(count=900, seed=17)` with Python's local pseudorandom generator. It contains artificial drift regimes, Gaussian log-price shocks, overnight gaps, and occasional lower-volume days. Dates skip weekends but not exchange holidays. There is no ticker and no external market-data source.

The generator is deterministic within the tested runtime. The committed CSV plus its SHA-256 is the strongest reproduction input: it avoids relying on cross-version random-number or floating-point behavior. The committed report uses this exact CSV.

## Keep data portable

Use relative paths for committed fixtures and absolute or local paths for your own inputs. Large or licensed datasets should remain outside Git. Each output manifest stores the input basename and SHA-256 so another reviewer can establish whether they used identical bytes without exposing your full local path.
