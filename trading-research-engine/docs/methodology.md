# Research methodology and mathematics

## Signal and information timing

For closing price $C_t$, the trailing mean over $n$ observations is

$$M_n(t)=\frac{1}{n}\sum_{j=0}^{n-1} C_{t-j}.$$

The position signal is $s_t=1$ when $M_f(t)>M_s(t)$ and zero otherwise, with $f<s$. Before $s$ observations exist, the signal is zero. Equality also means flat. The signal has no prediction model fitted to future prices.

At a completed close, equity $E_t$, target allocation $a$, and close $C_t$ determine

$$T_t=\left\lfloor\frac{aE_t}{C_t}\right\rfloor s_t.$$

This target becomes eligible at **open $O_{t+1}$**, never at the close used to compute the signal. A gap can alter exposure, affordability, and fill quantity. Allocation is a sizing target at the decision close, not a continuous intraday risk bound.

## Liquidity and partial fills

For requested signed shares $D=T_t-Q_t$ and maximum reference-volume participation $p$:

$$q_0=\min(|D|,\lfloor pV_t\rfloor).$$

The simulator uses **previous-bar volume $V_t$** for an order at $O_{t+1}$. Using the next day's full realized volume at its open would leak future information. Previous volume is only a causal proxy for opening capacity. It is not an exchange matching model or a claim about actual available liquidity.

Sells are additionally capped by held inventory. Buys are capped by affordability after all costs. Unfilled shares expire after the attempt. Zero reference volume produces no fill.

## Transaction price

Let $u$ be +1 for a buy and -1 for a sell; $q$ is the absolute filled quantity; $O$ is the next open; $V$ is prior volume. With full spread $b$, fixed slippage $l$, and linear participation coefficient $k$, all quoted in basis points:

$$P=O\left[1+u\left(\frac{b}{20000}+\frac{l}{10000}+\frac{k}{10000}\frac{q}{\max(V,1)}\right)\right].$$

One basis point is 0.01%, or 0.0001 in decimal form. A full 4 bp spread means paying 2 bp per side, not 4. Impact increases with participation. These coefficients are assumptions, not calibrated estimates.

Commission is

$$F(q)=\begin{cases}0&q=0\\\max(F_{min},cq)&q>0.\end{cases}$$

Buy affordability requires $qP(q)+F(q)\leq B$, where $B$ is cash. Under nonnegative configured costs, purchase expense is monotone in $q$, permitting integer binary search for the largest affordable quantity. Sells are rejected if even their proceeds plus existing cash cannot cover commission.

For example, 10 shares at a $100 reference, a 20 bp full spread, zero slippage/impact, and a $1 commission cost $1,002 to buy: fill price $100.10, notional $1,001, fee $1. The same sale produces $998: fill price $99.90, notional $999, fee $1.

The cost ledger records positive cost magnitudes:

$$K_{spread}=qO\frac{b}{20000},\quad K_{slip}=qO\frac{l}{10000},\quad K_{impact}=qO\frac{k}{10000}\frac{q}{\max(V,1)}.$$

Their sum plus commission is the direct cost. Price adjustments can lie outside a daily OHLC range; this is an adverse-cost model around the reference open, not a reconstruction of actual intraday prints.

## Comparison design

**Ideal signal:** independent fractional-share replay with no volume cap or costs. Its own equity sizes its own targets. It retains next-open timing and cash constraints.

**Net execution:** the full event-driven model, including integer shares and costs. Its realized close equity sizes subsequent targets.

**Gross execution:** replay exactly the target share counts recorded in the net run with zero costs. Liquidity and integer-share policies stay fixed. This avoids an unacknowledged re-sizing confound from independently compounding a different gross portfolio.

If gross and net fills have identical quantities and dates, their final equity difference equals the direct cost ledger, up to floating-point error. If affordability changes the fill sequence, the difference also contains a fill-path effect:

$$E_{gross}-E_{net}=K_{direct}+R_{fill\ path}.$$

The report labels the residual rather than calling it a fee. It can be negative. Zero-cost execution is a controlled counterfactual, not an independent implementable strategy with its own equity sizing.

**Buy-and-hold:** 100% fractional exposure purchased at the first open after the holdout's initial close. No costs or liquidity cap. Because strategy allocation defaults to 95%, this benchmark is not risk-matched.

## Training and holdout

The first `floor(N * train_fraction)` bars form the training segment. The remainder is holdout. Default fraction: 0.65. At least 30 training bars after warm-up and 30 holdout bars are required.

Default runs use fixed 20/60 windows; they do not optimize anything. `--select` evaluates only the predetermined pairs 10/40, 20/60, 40/120 on training net Sharpe. Candidates all begin at bar index 119. Undefined Sharpe ranks last; exact ties use the first candidate in the documented order.

Holdout starts with initial cash and zero inventory. Prior closes warm the selected strategy but do not transfer training positions, equity, or pending orders. The first holdout bar supplies a decision; the first possible fill is the following open. This intentional one-bar entry delay is shared by all comparators.

This is one chronological holdout, not walk-forward validation, cross-validation, statistical significance testing, or evidence of robustness across markets. Parameter selection can overfit training. Reusing holdout after changing research choices overfits holdout. Cost multiples that would make the worst-case sell-price adjustment reach 100% are excluded as outside the model. The cost sweep does not select a strategy and must not be interpreted as a probability distribution.

## Metrics

For consecutive equity values, daily return is $r_t=E_t/E_{t-1}-1$. There are $n-1$ return observations for $n$ equity rows. The first row equals initial cash because there is no pre-existing position or eligible order.

- Total return: $E_{last}/E_0-1$.
- CAGR: $(E_{last}/E_0)^{A/(n-1)}-1$, using configured bars per year $A$.
- Annualized volatility: sample standard deviation of daily returns times $\sqrt A$.
- Sharpe: mean daily return divided by sample standard deviation, times $\sqrt A$, assuming zero risk-free return.
- Maximum drawdown: minimum of $E_t/\max_{j\leq t}E_j-1$, expressed as a nonpositive number.

Sharpe is null when standard deviation is zero. Short-sample annualized results can be unstable. These are equally spaced bar-based metrics, not exact calendar-day annualization. Missing sessions are not imputed. No trade-level win rate is fabricated from individual fills, which can include partial entry/exit and rebalancing.

## Model boundaries

- One instrument, daily bars, long/flat, whole shares in the executed portfolios.
- Market-style next-open fills; no limit orders, queue position, intraday stops, latency distributions, or auction reconstruction.
- No futures/options, shorts, borrow fees, leverage, funding, dividends, cash interest, taxes, or corporate-action handling.
- Previous volume is a capacity assumption. Costs are configurable but uncalibrated.
- No forced liquidation: end equity includes mark-to-market holdings and excludes the cost of a hypothetical exit.
- No real-data proof is bundled; synthetic regimes are known by construction.
- A moving-average example demonstrates the infrastructure. Opening-reversal signals and options execution require different event contracts.
- No claims of live deployment, historical outperformance, production readiness, or native speedups.
