"""Portable HTML/SVG report and machine-readable experiment artifacts."""
import csv
from dataclasses import asdict
import hashlib
import html
import json
from pathlib import Path
import platform
from . import __version__
from .metrics import summarize

COLORS = {"ideal_signal": "#4878d0", "gross_execution": "#ac7b31",
          "net_execution": "#00856a", "buy_and_hold": "#89929f"}


def write_csv(path, rows):
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        if rows:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)


def chart(curves, drawdown=False):
    series = {}
    for name, rows in curves.items():
        values = [r["equity"] for r in rows]
        if drawdown:
            peak = values[0]
            transformed = []
            for value in values:
                peak = max(peak, value)
                transformed.append(100 * (value / peak - 1))
            values = transformed
        series[name] = values
    width, height = 1000, 340
    lo = min(min(v) for v in series.values())
    hi = max(max(v) for v in series.values())
    if hi == lo:
        hi, lo = hi+1, lo-1
    pad = (hi-lo)*0.06
    lo, hi = lo-pad, hi+pad
    def y(value):
        return 50 + (hi-value)/(hi-lo)*230
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" font-family="system-ui, sans-serif" viewBox="0 0 {width} {height}" role="img" aria-label="{ "Drawdown" if drawdown else "Equity" } chart">']
    for index, (name, color) in enumerate(COLORS.items()):
        parts.append(f'<text x="{85+index*225}" y="20" fill="{color}" font-size="13">● {name.replace("_", " ").title()}</text>')
    for j in range(5):
        value = lo+(hi-lo)*j/4
        label = f"{value:.1f}%" if drawdown else f"${value:,.0f}"
        parts.append(f'<line x1="85" y1="{y(value):.2f}" x2="980" y2="{y(value):.2f}" stroke="#e5e9ee"/><text x="75" y="{y(value)+4:.2f}" text-anchor="end" fill="#647080" font-size="12">{label}</text>')
    for name, values in series.items():
        points = " ".join(f"{85+i/(len(values)-1)*895:.2f},{y(value):.2f}" for i, value in enumerate(values))
        parts.append(f'<polyline fill="none" stroke="{COLORS[name]}" stroke-width="2" points="{points}"/>')
    dates = next(iter(curves.values()))
    for fraction in (0, 0.5, 1):
        index = round(fraction*(len(dates)-1))
        anchor = "start" if fraction == 0 else "end" if fraction == 1 else "middle"
        parts.append(f'<text x="{85+fraction*895}" y="310" text-anchor="{anchor}" fill="#647080" font-size="12">{dates[index]["date"]}</text>')
    parts.append("</svg>")
    return "".join(parts)


def write_report(output, data_path, experiment, backend, synthetic, selected):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    x = experiment
    config = x["config"]
    manifest = dict(schema_version=1, engine_version=__version__, python=platform.python_version(),
                    backend=backend, data_file=Path(data_path).name,
                    data_sha256=hashlib.sha256(Path(data_path).read_bytes()).hexdigest(),
                    synthetic=synthetic, selected_on_training=selected, config=asdict(config),
                    warmup_index=x["warmup"], split_index=x["split"],
                    train_start=x["train"].equity[0]["date"], train_end=x["train"].equity[-1]["date"],
                    holdout_start=x["net"].equity[0]["date"], holdout_end=x["net"].equity[-1]["date"])
    summary = dict(holdout=x["metrics"], training=summarize(x["train"].equity, config.initial_cash, config.annualization),
                   costs=x["costs"], attribution=x["attribution"])
    for name, payload in (("manifest.json", manifest), ("summary.json", summary)):
        (output/name).write_text(json.dumps(payload, indent=2, allow_nan=False)+"\n")
    for prefix, result in (("net", x["net"]), ("gross", x["gross"]), ("train", x["train"])):
        for name in ("equity", "orders", "fills", "events"):
            write_csv(output/f"{prefix}_{name}.csv", getattr(result, name))
    comparisons = []
    for i, row in enumerate(x["net"].equity):
        comparisons.append(dict(date=row["date"], **{name: rows[i]["equity"] for name, rows in x["curves"].items()}))
    write_csv(output/"comparison.csv", comparisons)
    write_csv(output/"cost_sensitivity.csv", x["sensitivity"])
    if x["candidates"]:
        write_csv(output/"training_candidates.csv", x["candidates"])
    equity_svg, drawdown_svg = chart(x["curves"]), chart(x["curves"], True)
    (output/"equity.svg").write_text(equity_svg)
    (output/"drawdown.svg").write_text(drawdown_svg)
    def number(value, percent=False):
        if value is None:
            return "—"
        return f"{value:.2%}" if percent else f"{value:,.2f}"
    metric_rows = "".join(f'<tr><td><span style="color:{COLORS[name]}">●</span> {name.replace("_", " ").title()}</td><td>${number(m["final_equity"])}</td><td>{number(m["total_return"], True)}</td><td>{number(m["cagr"], True)}</td><td>{number(m["sharpe"])}</td><td>{number(m["max_drawdown"], True)}</td></tr>' for name, m in x["metrics"].items())
    cost_rows = "".join(f'<tr><td>{name.replace("_", " ").title()}</td><td>${value:,.2f}</td></tr>' for name, value in x["costs"].items() if name in ("commission", "spread_cost", "slippage_cost", "impact_cost", "total_cost"))
    sweep_rows = "".join(f'<tr><td>{r["cost_multiple"]:g}×</td><td>{r["total_return"]:.2%}</td><td>${r["total_cost"]:,.2f}</td><td>{r["fill_count"]}</td></tr>' for r in x["sensitivity"])
    label = "SYNTHETIC DEMO · NOT MARKET PERFORMANCE" if synthetic else "USER-SUPPLIED CSV · PROVENANCE NOT VERIFIED"
    content = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Trading research | Experiment report</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;background:#f4f6f8;color:#172535;font:15px/1.6 system-ui,sans-serif}} main{{max-width:1160px;margin:0 auto;padding:48px 24px}} header{{margin-bottom:32px}} .eyebrow{{font-size:12px;letter-spacing:1.5px;font-weight:700;color:#00856a}} h1{{font-size:40px;line-height:1.15;letter-spacing:-1.5px;margin:12px 0}} h2{{font-size:20px;margin:0 0 16px}} p{{color:#5a6878}} .tag{{display:inline-block;padding:5px 10px;background:#e3eee9;color:#236149;font-size:11px;font-weight:700;letter-spacing:.6px;border-radius:4px}} section{{background:white;border:1px solid #dfe5ea;border-radius:10px;padding:24px;margin:20px 0;overflow-x:auto}} table{{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}} th,td{{text-align:right;padding:12px;border-bottom:1px solid #e9edf1;white-space:nowrap}} th:first-child,td:first-child{{text-align:left}} th{{font-size:12px;color:#647080}} svg{{width:100%;min-width:520px}} .grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}} .grid section{{margin:0}} code{{font-size:12px;overflow-wrap:anywhere}} a{{color:#007c66}} details{{margin:24px 0}} pre{{white-space:pre-wrap;background:#e9eef2;padding:16px;font-size:12px}} @media(max-width:750px){{.grid{{grid-template-columns:1fr}}h1{{font-size:30px}}main{{padding:24px 12px}}section{{padding:16px}}}}
</style></head><body><main>
<header><div class="eyebrow">RESEARCH / EXECUTION</div><h1>From signal to simulated fills.</h1><span class="tag">{label}</span><p>Holdout: {manifest['holdout_start']} → {manifest['holdout_end']} · MA {config.fast}/{config.slow} · {backend.upper()} execution · Starting cash ${config.initial_cash:,.0f}</p></header>
<section><h2>Holdout performance</h2><table><thead><tr><th>Model</th><th>Final equity</th><th>Return</th><th>CAGR</th><th>Sharpe</th><th>Max drawdown</th></tr></thead><tbody>{metric_rows}</tbody></table><p>All models start flat. First possible fill: the next open. Buy-and-hold uses 100% exposure; the signal targets {config.allocation:.0%}. Sharpe assumes zero risk-free return and {config.annualization} bars/year. CAGR is an annualized estimate, especially unstable for short samples.</p></section>
<section><h2>Equity through the holdout</h2>{equity_svg}</section>
<section><h2>Drawdown from the running peak</h2>{drawdown_svg}</section>
<div class="grid"><section><h2>Execution cost ledger</h2><table>{cost_rows}</table><p>Gross minus net: ${x['attribution']['gross_minus_net']:,.2f}. Fill-path residual: ${x['attribution']['fill_path_residual']:,.2f}. Gross replay uses net-run targets; affordability may change filled quantities.</p></section>
<section><h2>Cost sensitivity</h2><table><tr><th>Cost scale</th><th>Return</th><th>Direct costs</th><th>Fills</th></tr>{sweep_rows}</table><p>The target schedule is fixed. Spread, slippage, impact and commissions scale together. These are scenarios, not confidence intervals. Scales that imply a nonpositive sell price are excluded.</p></section></div>
<section><h2>What this experiment establishes</h2><p>The simulator separates a signal's idealized return from integer-share, cash-limited execution and explicit costs. Previous-bar volume supplies a causal liquidity proxy; it is not an observed opening auction capacity. The test period is untouched by parameter selection in this run. Repeatedly changing settings after seeing this report invalidates that interpretation.</p><p>No short selling, options, live routing, order-book queues, corporate-action processing, exchange calendars, dividends, cash interest or borrow fees are modeled. Remaining shares are marked at the last close, not forcibly sold. Input bars must be on a consistent price basis.</p><a href="comparison.csv">Equity CSV</a> · <a href="net_fills.csv">Fill ledger</a> · <a href="net_orders.csv">Orders</a> · <a href="net_events.csv">Events</a> · <a href="summary.json">Summary JSON</a></section>
<details><summary>Reproduction manifest</summary><pre>{html.escape(json.dumps(manifest, indent=2))}</pre></details>
<footer><p>Trading Research &amp; Execution Engine · v{__version__} · Offline report, no external scripts or services.</p></footer>
</main></body></html>"""
    (output/"report.html").write_text(content, encoding="utf-8")
    return output/"report.html"
