# Reproduction and audit

## Reproduce the checked-in example

From the repository root:

```bash
python run.py run --data examples/synthetic.csv --synthetic --output outputs/review
python -m unittest discover -s tests -v
```

Compare `outputs/review/summary.json` with `examples/review/summary.json`. The numerical outputs should agree within floating-point tolerance; runtime metadata can differ. For native execution, build first and add `--backend cpp --native-lib build/execution.so` (platform suffix varies).

The default fixture has 900 bars: training ends at index 584; holdout covers indices 585–899. Fixed parameters are 20/60. The training portfolio starts at index 59. This is 314 holdout return intervals, since the initial holdout row is uninvested cash.

## Output dictionary

| File | Meaning |
| --- | --- |
| `report.html` | Self-contained report with inline SVG; no network dependency |
| `manifest.json` | Input hash, engine/runtime/backend, exact config and split dates |
| `summary.json` | Training and holdout metrics, direct costs, attribution residual |
| `comparison.csv` | Date-aligned equity for all four models |
| `net_equity.csv` | Close cash, shares, mark price, equity and signal |
| `net_orders.csv` | Every target and its eventual fill/expiry status |
| `net_fills.csv` | Nonzero signed executions, reference price/volume and cost components |
| `net_events.csv` | Ordered phase-level audit trail |
| `gross_*`, `train_*` | Same four ledgers for gross replay and training simulation |
| `cost_sensitivity.csv` | Fixed-target results at 0, 0.5, 1, 2 and 5 times base costs |
| `training_candidates.csv` | Only emitted with `--select`; training-only candidate scores |
| `equity.svg`, `drawdown.svg` | Standalone vector figures |
| `synthetic.csv` | Demo command only: exact generated input used |

A ledger with no rows is an empty file; it is not an error. Final orders have status `CANCELLED_END` and no execution date. They were never eligible, so their requested/filled/unfilled quantities stay zero.

## Reconcile one trade

1. Locate its `order_id` in `net_orders.csv` and confirm decision date precedes execution date.
2. Match the corresponding fill row; compare its reference to the input bar's open.
3. Confirm `reference_volume` equals the preceding input row's volume.
4. Reconstruct adjusted price and fee with the formulas in methodology.
5. Apply `cash -= quantity * price + commission` and `position += quantity`.
6. At that day's close, recompute `equity = cash + position * close`.

The spread, slippage and impact fields explain the difference between reference and execution price. Do not subtract them a second time from cash.

## Cost attribution

For identical gross/net fill sequences, gross final equity minus net final equity equals total direct costs. The report records `identical_fills` and the residual. If affordability changed quantities, a nonzero residual is expected; it is not proof of an accounting error. Check fill sequences before interpreting it.

A one-times sensitivity replay should reproduce net final equity, because it receives the exact net targets and the exact base costs. This is covered by a regression test.

## Determinism and environment

No live data downloads, hidden API keys, random strategy selection, or background services are involved. The demo generator has an explicit seed. All subsequent simulation behavior is deterministic. The manifest captures engine version and Python version; use Git's commit ID to pin source code when sharing research. Input hash pins data bytes. Keep your custom config together with the output.

Native and Python paths are compared within tolerances, not a promise of bit-for-bit identity across all compilers. Financial output is not rounded until display. Compiler flags prohibit fast-math shortcuts. Optional debug builds use undefined-behavior sanitization on GCC/Clang:

```bash
python scripts/build_native.py --debug
python -m unittest discover -s tests -v
```

## Publishing

No private explanation file or generated build binary belongs in the repository. `personal_readme` name patterns are ignored. To publish a checkout after creating a new empty GitHub repository:

```bash
git add .
git commit -m "Implement reproducible trading research and execution engine"
git remote add origin https://github.com/YOUR_USERNAME/trading-research-engine.git
git push -u origin main
```

If you downloaded a source ZIP rather than a Git checkout, run `git init -b main` first. Configure your Git author identity locally if Git requests it. Do not paste access tokens into files or commit messages. Alternatively, with GitHub CLI already authenticated, use `gh repo create trading-research-engine --public --source . --remote origin --push`.
