# Carbon Attribution Dashboard — Technical Specification

A developer-oriented description of the application in enough detail to recreate it from scratch.

---

## 1. Purpose

A Streamlit dashboard that answers: **"If I invest $X in company Y, how many tonnes of CO2e am I responsible for, month by month, over time?"**

It ingests company-level carbon, sales, and enterprise-value (EV) data from Excel, fills gaps in reported emissions using a statistically validated estimation pipeline, attributes emissions to an investment via EV ownership, renders smooth monthly charts with confidence bands, and analyzes carbon-intensity changes across portfolio snapshots.

## 2. Tech stack & run

- Python >= 3.11
- Dependencies (`pyproject.toml`): `streamlit >= 1.48`, `pandas >= 2.3`, `numpy >= 2.3`, `scipy >= 1.16`, `plotly >= 6.3`, `openpyxl >= 3.1`
- Run: `streamlit run app.py --server.port 5000`

## 3. Module map

| File | Role |
|---|---|
| `app.py` | Streamlit UI: tabs, session state, upload wiring |
| `data_processor.py` | Excel ingestion & normalization for carbon data and portfolio files |
| `carbon_calculator.py` | Per-company attribution: intensity series → annual rows → monthly smoothed rows |
| `methodology.py` | The validated estimation pipeline (pure functions, no Streamlit/pandas state) |
| `visualization.py` | Plotly chart builders |
| `portfolio_analyzer.py` | Period-over-period portfolio carbon-exposure changes |
| `data_persistence.py` | Pickle/JSON persistence under `persistent_data/` |
| `backtest_methodology.py` | Offline holdout harness that validates the estimation pipeline |

## 4. Data inputs

### 4.1 Carbon workbook (`.xlsx`/`.xls`, read with openpyxl)

Four required sheets, named exactly:

- **`Reference`** — one row per company. Required: `ISIN` plus `Company` or `Name` (`Name` is renamed to `Company`). Optional: `Sector`, `Subsector`, `Industry`, `Subindustry`, `Country` (missing → `"Unknown"`).
- **`Carbon`** — `ISIN` + year columns; values are annual emissions in tonnes CO2e.
- **`Sales`** — `ISIN` + year columns; annual revenue in USD.
- **`EV`** — `ISIN` + year columns; enterprise value in USD.

Year columns are any columns coercible to an integer in 2000–2030; values are coerced numeric (invalid → NaN). Carbon and Reference must be non-empty; Sales/EV may be partial. Zero/missing values are treated as absent. Internally stored as dict `{reference, carbon, sales, ev}`.

### 4.2 Portfolio workbook

Multiple sheets named `DD.MM.YY` (e.g. `01.07.20`), each with `ISIN` and `TotalNominal`. Each sheet becomes a dated snapshot with `Weight = TotalNominal / sum(TotalNominal)`.

### 4.3 Persistence

- `persistent_data/carbon_data.pkl` + `carbon_data_metadata.json`
- `persistent_data/portfolios/<name>.pkl` + `portfolio_library.json`

Persisted data auto-loads at app startup and reconstructs the calculator/chart/analyzer objects.

## 5. Core math: attribution

For a company and an investment amount `A`:

1. **Reported intensity** per year: `I_y = Carbon_y / Sales_y`, only where both are positive.
2. **Target years**: every year from the first reported year through `max(last reported, CURRENT_YEAR)` where `CURRENT_YEAR = 2026` — i.e. the pipeline also *nowcasts* forward to the present.
3. **Estimated intensities** come from `methodology.estimate_intensity_series` (§6).
4. **Missing sales**: carried forward flat from the most recent reported year. **Missing EV**: `np.interp` between available EV points (min $1,000,000); a single EV point is held constant; no EV at all → `EV = 2.0 × sales`.
5. **Reconstructed emissions**: `Carbon_y = I_est × Sales_y`.
6. **Attribution (EV ownership, not equity market cap):**
   - `ownership = A / enterprise_value`
   - `annual_emissions_attributed = ownership × carbon_emissions`

Each annual row records `year`, `carbon_emissions`, `enterprise_value`, `data_quality` (`reported`/`estimated`), `estimate_quality` (`reported`, `interpolated`, `spike_filled`, `extrapolated`), and `band_rel` (relative confidence half-width, §6.6).

## 6. Estimation methodology (`methodology.py`)

All estimation operates on strictly positive intensities in **log space**. The single production entry point is `estimate_intensity_series(years, values, target_years, sector_jump_threshold, sector_log_growth)` — the app and the backtest share this exact code path (this parity is deliberately enforced; see §8).

### 6.1 Building blocks

- `ols_trend`: `np.polyfit(x, y, 1)`; <2 points → slope 0, intercept = first value.
- `robust_trend`: Theil–Sen (`scipy.stats.theilslopes`) for ≥3 points, OLS fallback.
- `median_log_growth`: median of consecutive-year log ratios `log(I_y / I_{y-1})`, returned as a multiplicative factor.
- Adaptive cap `cap_to_median(v, median, is_extrapolation)`: interpolation clamps to `[median/2, median×2]`; extrapolation clamps tighter, `[median/1.5, median×1.5]`; non-positive results become `median×0.5`.

### 6.2 Series classification (`classify_series`)

Jump threshold defaults to `DEFAULT_JUMP_LOG = log(1.5) ≈ 0.4055` (>50% up or >33% down move), or a sector-specific threshold when available.

- **Pass 1 — spike removal**: an interior year is a *spike* if both adjacent log moves exceed the threshold with opposite signs, and its two neighbors differ by less than the threshold. Spike years are removed (later re-filled and labelled `spike_filled`).
- **Pass 2 — structural break (regime) detection**: a jump is a *sustained break* if the post-jump mean does not revert toward the prior level (`|post_mean − prev| ≥ |jump|/2`), there are ≥2 post-jump points, and the jump is confirmable (jump year ≤ last-year − 1; a final-year break cannot be confirmed). The last sustained break wins. With `split_breaks=True`, pre-break points are labelled `break` and discarded — only the current regime is kept.

**Critical design decision (target-aware classification)**: production classifies twice —
- de-spiked **full history** (`split_breaks=False`) for **interpolation** targets;
- de-spiked **current regime** (`split_breaks=True`) for **forward extrapolation** targets.

This recovers interpolation accuracy (pre-break points are still valid neighbors for interior gaps) while extrapolation ignores the obsolete regime.

### 6.3 Interpolation (interior gaps and spike re-fill)

`interpolate_log_pchip`: `scipy.interpolate.PchipInterpolator(x, log(values), extrapolate=False)`, exponentiated; fallback to linear interpolation in log space. Shape-preserving PCHIP avoids the overshoot/negative-value artifacts of natural cubic splines. Targets outside the observed range use a robust (Theil–Sen) log-trend instead.

### 6.4 Forward extrapolation with sector shrinkage (`extrapolate_shrinkage`)

Anchor at the latest observed value; for horizon `h`:

```
g = w(h) × g_company + (1 − w(h)) × g_sector      # blended log growth
estimate = last_value × exp(g × h)
```

Weights `w = {1: 0.8, 2: 0.5, 3: 0.3}`, floor `0.2` for `h ≥ 4`. `g_company` is the company's median log growth in the current regime; `g_sector` is the sector's median log change (§6.5). If no sector growth exists, use company growth alone.

### 6.5 Sector context (built by the caller)

Sector key: `Subsector` if present else `Sector`. Pool `log(I_y / I_{y-1})` over consecutive years across all companies in a sector, then:

- sector growth = `exp(median(pool))`
- sector jump threshold = `max(log(1.5), 3 × 1.4826 × MAD(pool))`

Defaults when a sector lacks data: threshold `log(1.5)`, no growth.

### 6.6 Capping and confidence bands

- Every estimate is capped via `cap_to_median`. **Interpolation** caps use the **full-history median**; **extrapolation** caps use the **post-break (current-regime) median**. Using the wrong median lets the tail escape (this exact bug produced a 15× worse mean error during development).
- Empirically calibrated relative half-widths (`band_for`): `reported = 0.08`, `interpolated = 0.11`, extrapolated by horizon `{1: 0.16, 2: 0.17, 3: 0.18}`, floor `0.20` beyond. Monthly `lower/upper = value × (1 ∓ band)`.
- Single-report companies: value held constant for all targets (`reported` at the source year, `extrapolated` elsewhere).

### 6.7 Validated accuracy (7,134 companies, ≥6 reported years)

| Scenario | Baseline (OLS+cap) median abs err | Full pipeline | Mean (tail) |
|---|---|---|---|
| Interpolation (interior gap) | 17.4% | **10.6%** | 163% → 112% |
| Extrapolation +1yr | 28.6% | **16.2%** | 406% → 60% |
| Extrapolation +3yr | 27.9% | **17.9%** | 923% → 61% |

## 7. Monthly smoothing (annual-total preserving)

In `carbon_calculator._generate_monthly_smooth_data`:

1. Display window spans at least 2019–2025, extended to cover data; months generated at `freq='MS'`.
2. Annual attributed totals become control points at year midpoints `year + 0.5`.
3. Interpolant: log-space PCHIP when all values positive, else linear-space PCHIP (`_build_curve_interpolant`), with extrapolation enabled.
4. Month value: evaluate at `year + (month − 0.5)/12`, divide by 12, floor at 0.
5. **Exact conservation**: for each year with an annual target, all 12 monthly values are proportionally rescaled by `annual_target / sum(months)`; a zero sum distributes `target/12` equally. An integrity check raises a warning if any annual sum deviates by more than `0.001`.
6. Confidence bands: `monthly × (1 ± band_rel)` carried into `monthly_emissions_lower/upper`.

Output columns: `year`, `month`, `date`, `ownership_percentage`, `enterprise_value`, `monthly_emissions_attributed`, `monthly_emissions_lower`, `monthly_emissions_upper`, `data_quality`.

## 8. Backtest harness (`backtest_methodology.py`)

Run with `python3 backtest_methodology.py` (optionally `SKIP_INTERP=1` to skip the slower interpolation scenario). It:

- loads `persistent_data/carbon_data.pkl`, builds ISIN → `{year: intensity}` from positive carbon/sales (≥2 years), and keeps companies with ≥6 reported years (`MIN_HISTORY=6`);
- **recent-year holdout** (nowcasting): hides each company's last 1–3 years (`MAX_HORIZON=3`) and predicts them; sector thresholds/growth are recomputed using only years ≤ target−1 (cached per cutoff) to prevent leakage;
- **middle-year holdout** (interpolation): hides each interior year and predicts it;
- compares a registry of estimators, from `baseline (OLS+cap)` up to `pipeline (shared API)` — the last one calls the exact production `estimate_intensity_series`, so any drift between app and backtest shows up as a parity failure;
- reports per estimator: `n`, mean abs %, median abs %, and share of errors >50% (relative error is signed `(est − actual)/actual`).

## 9. UI (`app.py`)

Wide-layout Streamlit app, six tabs:

1. **About** — methodology explanation.
2. **Data Upload** — carbon workbook upload; initializes and persists all components.
3. **Company Analysis** — company selectbox, investment amount input, metadata, summary cards, annual table, main chart, CSV download.
4. **Portfolio Analysis** — pick a saved portfolio; period-over-period exposure analysis, summary stats, chart.
5. **Portfolio Library** — create/select/update/delete portfolio snapshots.
6. **System Status** — component health, data counts, cache clear, reload, health check.

Session-state keys: `data_processor`, `calculator`, `chart_builder`, `portfolio_analyzer`, `data_persistence`, `current_portfolio`.

### Charts (`visualization.py`, Plotly)

Main chart: shaded green confidence band (drawn first, behind), smooth green monthly line (`#2ecc71`), blue reported annual step (`#3498db`, `shape='hv'`, value = mean monthly per year), gray dashed steps for estimated periods (`#95a5a6`, split into contiguous runs). Unified hover, yearly ticks, 1Y/3Y/5Y/All range buttons, range slider, height 500. Additional builders: sector bar chart, portfolio exposure overlay, stacked data-quality chart, ownership chart.

## 10. Portfolio analysis (`portfolio_analyzer.py`)

For each pair of adjacent snapshot dates, per holding: run company attribution with a fixed $1,000,000, read (or linearly interpolate) monthly endpoints, back out company emissions (`monthly_attributed / ownership`), compute carbon-per-EV, and take `(end − start) × 1,000,000`. Weight per-holding changes by portfolio `Weight` and sum. Output: `period_start`, `period_end`, `portfolio_carbon_change`, `weighted_exposure`, `num_holdings`, `period_months`, plus summary stats (mean/total/max/min/std).

**Known defect**: `_find_company_by_isin` looks up a `Name` column while ingestion normalizes it to `Company`, so this path can fail with standard files.

## 11. Recreation checklist

1. Implement `methodology.py` first as pure functions with the exact constants in §6 — it is the heart of the system.
2. Build the backtest harness next and reproduce the accuracy table (§6.7) before wiring anything into the app; keep a "pipeline (shared API)" estimator that calls the production entry point so parity is continuously verifiable.
3. Implement ingestion (§4), attribution (§5), and monthly smoothing (§7); assert annual-total conservation.
4. Add the UI and charts last. The tricky parts to get right, in order: regime-aware median selection for caps (§6.6), target-aware dual classification (§6.2), log-space PCHIP everywhere (never natural cubic splines), and sector-context computed without look-ahead leakage in the backtest.
