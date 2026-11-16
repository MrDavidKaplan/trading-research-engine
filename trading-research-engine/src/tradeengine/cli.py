"""Command line entry points. Run `python run.py --help` from the checkout."""
import argparse
import json
from pathlib import Path
import sys
from .data import generate_demo, load_bars
from .execution import NativeBroker, PythonBroker
from .models import Config
from .research import evaluate
from .report import write_report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Historical signal research and execution simulation")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("demo", "run"):
        p = sub.add_parser(command, help="Run synthetic demo" if command == "demo" else "Run your historical OHLCV CSV")
        p.add_argument("--output", type=Path, required=True, help="New output directory; existing paths are never overwritten")
        p.add_argument("--config", type=Path, help="JSON object overriding documented Config defaults")
        p.add_argument("--backend", choices=("python", "cpp"), default="python")
        p.add_argument("--native-lib", type=Path, help="Path printed by scripts/build_native.py")
        p.add_argument("--select", action="store_true", help="Select MA pair on training data from the documented fixed grid")
        if command == "run":
            p.add_argument("--data", type=Path, required=True)
            p.add_argument("--synthetic", action="store_true", help="Label input as synthetic in all outputs")
        else:
            p.add_argument("--seed", type=int, default=17)
            p.add_argument("--bars", type=int, default=900)
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise ValueError(f"Output already exists: {args.output}. Choose a new directory.")
        overrides = json.loads(args.config.read_text()) if args.config else {}
        if not isinstance(overrides, dict):
            raise ValueError("Config must be a JSON object")
        config = Config(**overrides)
        if args.backend == "cpp":
            if not args.native_lib:
                raise ValueError("C++ backend requires --native-lib; run python scripts/build_native.py")
            broker = NativeBroker(args.native_lib)
        else:
            broker = PythonBroker()
        # Temporary demo file keeps a rejected run from leaving incomplete output.
        if args.command == "demo":
            import tempfile
            with tempfile.TemporaryDirectory() as directory:
                path = generate_demo(Path(directory)/"synthetic.csv", args.bars, args.seed)
                bars = load_bars(path)
                experiment = evaluate(bars, config, broker, args.select)
                report = write_report(args.output, path, experiment, broker.name, True, args.select)
                (args.output/"synthetic.csv").write_bytes(path.read_bytes())
        else:
            bars = load_bars(args.data)
            experiment = evaluate(bars, config, broker, args.select)
            report = write_report(args.output, args.data, experiment, broker.name, args.synthetic, args.select)
        summary = experiment["metrics"]["net_execution"]
        print(f"Report: {report.resolve()}")
        print(f"Holdout return: {summary['total_return']:.2%} | Costs: ${experiment['costs']['total_cost']:,.2f}")
        print("Synthetic demonstration; not evidence of a trading edge." if args.command == "demo" or args.synthetic
              else "User-supplied data; results depend on its provenance and price adjustments.")
    except (ValueError, TypeError, OSError, ArithmeticError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()
