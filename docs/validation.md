# Validation record

Local verification for version 1.0.0, 2026-11-16:

| Check | Observed result |
| --- | --- |
| Python 3.12.14 on Linux | 32 tests passed, no skips after native build |
| C++17 optimized build | Compiled with warnings treated as errors |
| C++ undefined-behavior sanitizer build | Test suite passed without a sanitizer failure |
| Randomized execution comparison | 1,000 deterministic fill cases agreed within numerical tolerances |
| Full Python/C++ demo | All summary metrics agreed to absolute tolerance 1e-7 |
| Optional package installation | Wheel built locally; installed package generated the complete demo |
| Fixed-parameter and selected experiments | Both completed and exported reports |
| Documentation/report links | Referenced local paths resolved |
| SVG export | Parsed with its SVG namespace and rendered for inspection |

The tests include accounting identities, partial fills, next-open timing, previous-volume causality, future-price perturbations, holdout isolation, cash constraints, invalid input, and zero-equity metrics. See the test names and fixtures in `tests/test_engine.py` for exact coverage.

The GitHub Actions matrix targets Linux, macOS, and Windows with Python 3.10/3.12. Those additional environments are configured, not claimed as locally executed. Check remote workflow results after publication. Local testing is not a production certification or validation of a trading edge.

The committed example uses the exact synthetic fixture in `examples/synthetic.csv`. Its results are software examples, not market-performance evidence.
