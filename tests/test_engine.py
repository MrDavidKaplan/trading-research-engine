"""Financial behavior tests with hand-calculated fixtures and causal checks."""
import json
import math
import random
import tempfile
import unittest
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tradeengine.data import generate_demo, load_bars
from tradeengine.engine import simulate, idealized
from tradeengine.execution import PythonBroker, NativeBroker
from tradeengine.metrics import summarize, cost_summary
from tradeengine.models import Bar, Config
from tradeengine.research import evaluate
from tradeengine.report import write_report
from tradeengine.strategy import signals


def fixture(prices, volumes=None):
    return [Bar(date(2020, 1, 1)+timedelta(days=i), p, p, p, p,
                10000 if volumes is None else volumes[i]) for i, p in enumerate(prices)]


def free(**kwargs):
    base = Config(fast=1, slow=2, initial_cash=1000, allocation=1,
                  spread_bps=0, slippage_bps=0, impact_bps=0,
                  commission_per_share=0, minimum_commission=0, participation=1)
    return replace(base, **kwargs)


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.broker = PythonBroker()

    def test_buy_commission_and_spread_by_hand(self):
        config = free(spread_bps=20, commission_per_share=0.1, minimum_commission=1)
        fill = self.broker.execute(10, 0, 2000, 100, 10000, config)
        self.assertEqual(fill.quantity, 10)
        self.assertAlmostEqual(fill.price, 100.1)
        self.assertAlmostEqual(fill.commission, 1)
        self.assertAlmostEqual(fill.spread_cost, 1)
        self.assertAlmostEqual(2000-10*fill.price-fill.commission, 998)

    def test_sell_costs_move_price_down(self):
        f = self.broker.execute(0, 10, 0, 100, 10000, free(spread_bps=20, minimum_commission=1))
        self.assertEqual(f.quantity, -10)
        self.assertAlmostEqual(f.price, 99.9)
        self.assertAlmostEqual(-f.quantity*f.price-f.commission, 998)

    def test_cash_includes_minimum_fee(self):
        f = self.broker.execute(10, 0, 1000, 100, 10000, free(minimum_commission=1))
        self.assertEqual(f.quantity, 9)

    def test_cash_handles_gap(self):
        f = self.broker.execute(10, 0, 1000, 120, 10000, free())
        self.assertEqual(f.quantity, 8)

    def test_partial_capacity(self):
        f = self.broker.execute(100, 0, 10000, 10, 500, free(participation=0.01))
        self.assertEqual(f.quantity, 5)

    def test_zero_volume_and_no_order(self):
        for target, pos, vol in ((10, 0, 0), (10, 10, 100)):
            self.assertEqual(self.broker.execute(target, pos, 10000, 100, vol, free()).quantity, 0)

    def test_unaffordable_small_sell_rejected(self):
        self.assertEqual(self.broker.execute(0, 1, 0, 1, 100, free(minimum_commission=2)).quantity, 0)

    def test_impact_by_hand(self):
        f = self.broker.execute(10, 0, 10000, 100, 100, free(impact_bps=100))
        self.assertAlmostEqual(f.price, 100.1)
        self.assertAlmostEqual(f.impact_cost, 1)

    def test_costs_cannot_improve_same_fill(self):
        for target, pos in ((10, 0), (0, 10)):
            gross = self.broker.execute(target, pos, 10000, 100, 1000, free())
            net = self.broker.execute(target, pos, 10000, 100, 1000, Config())
            self.assertEqual(gross.quantity, net.quantity)
            self.assertGreaterEqual(net.quantity * (net.price-gross.price)+net.commission, 0)


class EngineTests(unittest.TestCase):
    def test_next_open_not_signal_close(self):
        result = simulate(fixture([100, 110, 120, 130]), free(), start=0)
        self.assertEqual(result.fills[0]["date"], "2020-01-03")
        self.assertEqual(result.fills[0]["price"], 120)
        self.assertEqual(result.fills[0]["quantity"], 8)
        self.assertEqual(result.equity[1]["position"], 0)
        self.assertEqual(result.equity[-1]["equity"], 1080)

    def test_previous_volume_only(self):
        a = simulate(fixture([100, 110, 120], [1000, 100, 1]), free(participation=0.01), start=0)
        b = simulate(fixture([100, 110, 120], [1000, 100, 1000000]), free(participation=0.01), start=0)
        self.assertEqual(a.fills, b.fills)
        self.assertEqual(a.fills[0]["quantity"], 1)

    def test_end_target_cancelled_no_liquidation(self):
        r = simulate(fixture([100, 110, 120]), free(), start=0)
        self.assertEqual(r.orders[-1]["status"], "CANCELLED_END")
        self.assertGreater(r.equity[-1]["position"], 0)
        self.assertEqual(r.events[-1]["phase"], "CANCEL")

    def test_remainder_expires_and_target_replaces_it(self):
        bars = fixture([100]*4, [100]*4)
        r = simulate(bars, free(participation=0.02), start=0, targets=[10, 0, 0, 0])
        self.assertEqual([f["quantity"] for f in r.fills], [2, -2])
        self.assertEqual(r.orders[0]["unfilled"], 8)
        self.assertEqual(r.orders[0]["status"], "PARTIAL")

    def test_future_price_changes_do_not_change_history(self):
        bars = fixture([100, 102, 103, 90, 80, 120, 150, 100, 90])
        changed = bars[:5] + [replace(b, open=p, high=p, low=p, close=p) for b, p in zip(bars[5:], [1000, 2000, 3000, 4000])]
        a = simulate(bars, free(), start=0)
        b = simulate(changed, free(), start=0)
        self.assertEqual(a.equity[:5], b.equity[:5])
        self.assertEqual(a.orders[:4], b.orders[:4])
        self.assertEqual(signals(bars, 1, 2)[:5], signals(changed, 1, 2)[:5])

    def test_equity_reconciles_cash_and_inventory(self):
        r = simulate(fixture([100, 105, 110, 120, 90, 80, 100, 110]), free(minimum_commission=1), start=0)
        cash, shares = 1000, 0
        fills = {f["date"]: f for f in r.fills}
        for row in r.equity:
            if row["date"] in fills:
                f = fills[row["date"]]
                cash -= f["quantity"]*f["price"]+f["commission"]
                shares += f["quantity"]
            self.assertAlmostEqual(row["cash"], cash)
            self.assertEqual(row["position"], shares)
            self.assertAlmostEqual(row["equity"], cash+shares*row["close"])
            self.assertGreaterEqual(cash, 0)

    def test_fixed_fill_cost_identity(self):
        bars = fixture([100, 110, 120, 100, 90])
        config = free(initial_cash=10000, spread_bps=10, slippage_bps=2, minimum_commission=1)
        targets = [0, 10, 10, 0, 0]
        net = simulate(bars, config, start=0, targets=targets)
        gross = simulate(bars, free(initial_cash=10000), start=0, targets=targets)
        drag = gross.equity[-1]["equity"]-net.equity[-1]["equity"]
        self.assertAlmostEqual(drag, cost_summary(net.fills)["total_cost"])

    def test_fractional_reference_by_hand(self):
        bars = fixture([100, 110, 120, 132])
        rows = idealized(bars, free(), 0, 4)
        self.assertAlmostEqual(rows[-1]["equity"], 1100)

    def test_invalid_target(self):
        with self.assertRaises(ValueError):
            simulate(fixture([100]*3), free(), start=0, targets=[0, -1, 0])


class DataAndMetricsTests(unittest.TestCase):
    def test_metrics_known_path(self):
        stats = summarize([{"equity": x} for x in (100, 120, 90, 108)], 100, 3)
        self.assertAlmostEqual(stats["total_return"], .08)
        self.assertAlmostEqual(stats["cagr"], .08)
        self.assertAlmostEqual(stats["max_drawdown"], -.25)

    def test_bankrupt_account_stays_zero(self):
        stats = summarize([{"equity": x} for x in (100, 0, 0, 0)], 100)
        self.assertEqual(stats["total_return"], -1)
        self.assertEqual(stats["max_drawdown"], -1)

    def test_flat_sharpe_is_undefined(self):
        stats = summarize([{"equity":100}]*10, 100)
        self.assertIsNone(stats["sharpe"])
        self.assertEqual(stats["volatility"], 0)

    def test_config_rejects_bad_inputs(self):
        for kw in ({"fast":60}, {"slow":2.5}, {"initial_cash":float("nan")},
                   {"participation":0}, {"allocation":2}, {"spread_bps":-1},
                   {"minimum_commission":True}, {"impact_bps":10000}, {"unknown":1}):
            with self.subTest(kw=kw), self.assertRaises((TypeError, ValueError)):
                Config(**kw)

    def test_csv_validation(self):
        header = "date,open,high,low,close,volume\n"
        valid = "2020-01-01,10,12,9,11,100\n2020-01-02,11,12,10,11,100\n2020-01-03,11,12,10,11,100\n"
        changes = [valid.replace("10,12,9", "nan,12,9"), valid.replace("10,12,9", "13,12,9"),
                   valid.replace("2020-01-02", "2020-01-01"), valid.replace(",100", ",-1"),
                   valid.replace(",100", ",1.5"), valid.replace("2020-01-02", "2020-02-30")]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"bars.csv"
            path.write_text(header+valid)
            self.assertEqual(len(load_bars(path)), 3)
            for content in changes:
                path.write_text(header+content)
                with self.assertRaises(ValueError):
                    load_bars(path)

    def test_demo_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp)/"a.csv", Path(tmp)/"b.csv"
            generate_demo(a); generate_demo(b)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(len(load_bars(a)), 900)


class ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.path = generate_demo(Path(cls.temp.name)/"synthetic.csv")
        cls.bars = load_bars(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_holdout_does_not_change_selected_parameters(self):
        a = evaluate(self.bars, Config(), select=True)
        split = a["split"]
        changed = self.bars[:split] + [replace(b, open=b.open*2, high=b.high*2, low=b.low*2, close=b.close*2) for b in self.bars[split:]]
        b = evaluate(changed, Config(), select=True)
        self.assertEqual(a["candidates"], b["candidates"])
        self.assertEqual(a["config"], b["config"])
        self.assertEqual(a["net"].equity[0]["position"], 0)
        self.assertGreater(a["net"].fills[0]["date"], a["net"].equity[0]["date"])

    def test_report_artifacts_and_no_overwrite(self):
        x = evaluate(self.bars, Config())
        output = Path(self.temp.name)/"report"
        report = write_report(output, self.path, x, "python", True, False)
        self.assertIn("SYNTHETIC DEMO", report.read_text(encoding="utf-8"))
        self.assertIn("\u25cf", (output/"equity.svg").read_text(encoding="utf-8"))
        self.assertTrue((output/"net_fills.csv").exists())
        from xml.etree import ElementTree
        self.assertEqual(ElementTree.parse(output/"equity.svg").getroot().tag,
                         "{http://www.w3.org/2000/svg}svg")
        self.assertEqual(json.loads((output/"manifest.json").read_text())["split_index"], 585)
        with self.assertRaises(FileExistsError):
            write_report(output, self.path, x, "python", True, False)

    def test_cost_sweep_one_matches_net(self):
        x = evaluate(self.bars, Config())
        row = next(r for r in x["sensitivity"] if r["cost_multiple"] == 1)
        self.assertAlmostEqual(row["final_equity"], x["metrics"]["net_execution"]["final_equity"])

    def test_extreme_cost_scenarios_excluded(self):
        x = evaluate(self.bars, Config(impact_bps=3000))
        self.assertEqual([r["cost_multiple"] for r in x["sensitivity"]], [0, .5, 1, 2])

    def test_matched_order_replay_reuses_schedule(self):
        x = evaluate(self.bars, Config())
        self.assertEqual([r["target"] for r in x["net"].orders], [r["target"] for r in x["gross"].orders])


class NativeParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        suffix = ".dll" if sys.platform == "win32" else ".dylib" if sys.platform == "darwin" else ".so"
        library = ROOT/"build"/("execution"+suffix)
        if not library.exists():
            raise unittest.SkipTest("Build C++ kernel with python scripts/build_native.py to run parity tests")
        cls.native = NativeBroker(library)

    def test_1000_random_fills(self):
        rng = random.Random(28)
        reference = PythonBroker()
        for _ in range(1000):
            config = Config(participation=rng.uniform(.001, 1), spread_bps=rng.uniform(0, 30),
                            slippage_bps=rng.uniform(0, 20), impact_bps=rng.uniform(0, 100),
                            minimum_commission=rng.uniform(0, 5), commission_per_share=rng.uniform(0, .1))
            args = (rng.randrange(10000), rng.randrange(10000), rng.uniform(0, 1e6),
                    rng.uniform(.1, 1000), rng.randrange(100000), config)
            a, b = reference.execute(*args), self.native.execute(*args)
            self.assertEqual(a.quantity, b.quantity)
            for name in ("price", "commission", "spread_cost", "slippage_cost", "impact_cost"):
                self.assertTrue(math.isclose(getattr(a, name), getattr(b, name), rel_tol=1e-12, abs_tol=1e-9))

    def test_whole_run_parity(self):
        with tempfile.TemporaryDirectory() as tmp:
            bars = load_bars(generate_demo(Path(tmp)/"bars.csv"))
            a, b = simulate(bars, Config()), simulate(bars, Config(), self.native)
            self.assertEqual(a.orders, b.orders)
            for x, y in zip(a.equity, b.equity):
                self.assertAlmostEqual(x["equity"], y["equity"], places=7)

    def test_native_rejects_invalid_input(self):
        with self.assertRaises(ValueError):
            self.native.execute(-1, 0, 1000, 100, 100, Config())


if __name__ == "__main__":
    unittest.main()
