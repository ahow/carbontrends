---
name: Carbon intensity estimation methodology
description: Why the carbon-intensity pipeline is structured as it is, and the non-obvious rules that keep production matching the validated backtest.
---

# Carbon intensity estimation pipeline

The single production entry point is `methodology.estimate_intensity_series`. The calculator (`carbon_calculator.py`) and the offline validator (`backtest_methodology.py`) BOTH call it, so numbers match by construction. Parity was confirmed numerically (identical median/mean by horizon, maxdiff=0).

## Validate against REAL data, not sample data
- `backtest_methodology.py` loads `persistent_data/carbon_data.pkl` (carbon years ~2008-2023). Earlier "~6.4%" baseline claims came from SAMPLE data + middle-year holdout and were misleading.
- Real-data baseline (recent-year holdout, n=7134): median ~28% but **mean is catastrophic (400-900%)** because of a few wild extrapolations. Judge changes by BOTH median and the mean tail.
- No leakage: sector trends/thresholds for a holdout must be computed only from years <= cutoff.

## Non-obvious rules (each one cost iterations to get right)
- **Target-aware classification**: spikes are ALWAYS removed; structural-break regime-splitting is applied ONLY when extrapolating (`split_breaks=True`). Splitting during interpolation throws away usable history and hurts interior-gap accuracy.
- **Regime-appropriate median for capping**: interpolation caps against the full-history median; extrapolation caps against the POST-BREAK (current-regime) median. Using the full-history median for extrapolation caps lets the tail escape (mean jumped 60%->322%). This is the easiest bug to reintroduce.
- **Shrinkage extrapolation**: blend company log-trend toward sector log-trend, weight decays with horizon (`HORIZON_WEIGHTS` 0.8/0.5/0.3, floor 0.2), anchored at last observed value, compounded multiplicatively. This is what collapsed the mean tail.
- **Sector granularity**: use `Subsector` (well populated) for trends/thresholds. `compute_sector_growth` returns a multiplicative factor `exp(median log change)`; shrinkage needs `log()` of it.

## Monthly smoothing
- Use log-space PCHIP (`_build_curve_interpolant`), NOT cubic spline — spline overshoots and can dip negative. Exact annual totals are preserved by the per-year proportional scaling step (keep it; it is what makes totals conserve).

## Known non-blocking gaps (architect review, deferred as out of scope)
- `_get_company_data` drops zero values (`value != 0`), so true-zero carbon years are treated as missing. Pre-existing; revisit if zero-emitters matter.
- Band-width constants in `band_for` are static (from backtest medians); recalibrate periodically if dataset composition shifts.
