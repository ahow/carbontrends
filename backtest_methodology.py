#!/usr/bin/env python3
"""
Backtest harness for the carbon-intensity estimation methodology.

Key differences from the legacy evaluate_estimation_accuracy.py:
  * Loads the REAL dataset (persistent_data/carbon_data.pkl), not sample data.
  * Holds out the LAST K years (recent-year / nowcasting scenario) - which is
    what the app actually does in production (data ends 2023, "today" needs
    2024-2026) - instead of random middle years.
  * Also reports an interpolation scenario (hide one middle year) for context.
  * Compares estimators head-to-head so each methodology change can be judged
    against the baseline rather than asserted.

Run: python3 backtest_methodology.py
"""

from __future__ import annotations

import os
import pickle
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import methodology as M

DATA_PATH = "persistent_data/carbon_data.pkl"
MIN_HISTORY = 6          # need a decent history to hold out recent years
MAX_HORIZON = 3          # hold out last 1..3 years


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_real_data() -> Optional[Dict[str, pd.DataFrame]]:
    if not os.path.exists(DATA_PATH):
        print(f"No data at {DATA_PATH}")
        return None
    with open(DATA_PATH, "rb") as f:
        return pickle.load(f)


def company_intensities(carbon_row: pd.Series, sales_row: pd.Series,
                        year_cols: List[int]) -> Dict[int, float]:
    out: Dict[int, float] = {}
    for y in year_cols:
        c = carbon_row.get(y)
        s = sales_row.get(y)
        if pd.notna(c) and pd.notna(s) and c > 0 and s > 0:
            out[int(y)] = float(c) / float(s)
    return out


def build_company_series(data: Dict[str, pd.DataFrame]) -> Dict[str, Dict[int, float]]:
    """Map ISIN -> {year: intensity} for every company with usable data."""
    carbon = data["carbon"].set_index("ISIN")
    sales = data["sales"].set_index("ISIN")
    year_cols = [c for c in carbon.columns if str(c).isdigit()]
    common = carbon.index.intersection(sales.index)
    series: Dict[str, Dict[int, float]] = {}
    for isin in common:
        ints = company_intensities(carbon.loc[isin], sales.loc[isin], year_cols)
        if len(ints) >= 2:
            series[isin] = ints
    return series


def sector_map(data: Dict[str, pd.DataFrame]) -> Dict[str, str]:
    ref = data["reference"]
    col = "Subsector" if "Subsector" in ref.columns else "Sector"
    return dict(zip(ref["ISIN"], ref[col]))


# ---------------------------------------------------------------------------
# Sector trend (computed only from visible data to avoid leakage)
# ---------------------------------------------------------------------------

def _sector_log_changes(series, isin_to_sector, cutoff_year):
    """Collect year-over-year log changes per sector using years <= cutoff."""
    bucket: Dict[str, List[float]] = {}
    for isin, ints in series.items():
        sec = isin_to_sector.get(isin, "UNKNOWN")
        vis_years = sorted(y for y in ints if y <= cutoff_year)
        vis_vals = [ints[y] for y in vis_years]
        for i in range(1, len(vis_years)):
            if (vis_years[i] - vis_years[i - 1] == 1
                    and vis_vals[i - 1] > 0 and vis_vals[i] > 0):
                bucket.setdefault(sec, []).append(np.log(vis_vals[i] / vis_vals[i - 1]))
    return bucket


def compute_sector_growth(series, isin_to_sector, cutoff_year) -> Dict[str, float]:
    """Median per-year log-growth factor per sector, using only years <= cutoff."""
    bucket = _sector_log_changes(series, isin_to_sector, cutoff_year)
    return {sec: float(np.exp(np.median(v))) for sec, v in bucket.items() if v}


def compute_sector_thresholds(series, isin_to_sector, cutoff_year) -> Dict[str, float]:
    """Sector-aware jump thresholds (log-space) from visible data only."""
    bucket = _sector_log_changes(series, isin_to_sector, cutoff_year)
    return {sec: M.sector_jump_threshold(v) for sec, v in bucket.items()}


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def summarize(label: str, errors: List[float]) -> None:
    if not errors:
        print(f"  {label:<28} (no cases)")
        return
    arr = np.abs(np.array(errors))
    over50 = (arr > 0.5).mean() * 100
    print(f"  {label:<28} n={len(arr):<5} "
          f"mean={arr.mean()*100:6.2f}%  median={np.median(arr)*100:6.2f}%  "
          f">50%={over50:5.1f}%")


# ---------------------------------------------------------------------------
# Estimator registry
# ---------------------------------------------------------------------------

Estimator = Callable[[List[int], List[float], int, dict], Optional[float]]

_THRESHOLD_CACHE: Dict[int, Dict[str, float]] = {}
_GROWTH_CACHE: Dict[int, Dict[str, float]] = {}


def est_baseline(years, values, target, ctx):
    """Legacy: OLS linear trend + adaptive median cap."""
    return M.estimate_linear_baseline(years, values, target)


def est_robust(years, values, target, ctx):
    """Theil-Sen robust trend (linear space) + same adaptive median cap."""
    x = np.asarray(years, float)
    y = np.asarray(values, float)
    if len(x) < 2:
        return float(y[0]) if len(y) else None
    slope, intercept = M.robust_trend(x, y)
    est = slope * target + intercept
    median = float(np.median(y))
    is_extrap = target < x.min() or target > x.max()
    return M.cap_to_median(est, median, is_extrap)


def _pchip_or_logtrend(x, y, target):
    if target <= x.min() or target >= x.max():
        return M.extrapolate_log_trend(x, y, target, robust=True)
    return M.interpolate_log_pchip(x, y, target)


def est_pchip_log(years, values, target, ctx):
    """Log-space PCHIP for in-range; robust log-trend for out-of-range; + cap."""
    x = np.asarray(years, float)
    y = np.asarray(values, float)
    est = _pchip_or_logtrend(x, y, target)
    if est is None:
        return None
    median = float(np.median(y))
    is_extrap = target < x.min() or target > x.max()
    return M.cap_to_median(est, median, is_extrap)


def est_classified(years, values, target, ctx):
    """Target-aware Layer-1: always drop spikes; split regimes only when
    extrapolating forward (post-break regime reflects current structure).
    Then pchip-log (interp) / robust log-trend (extrap) + cap."""
    thr = ctx.get("jump_threshold", M.DEFAULT_JUMP_LOG)
    extrapolating = target > max(years)
    cls = M.classify_series(years, values, jump_threshold_log=thr,
                            confirm_year=max(years),
                            split_breaks=extrapolating)
    cy, cv = cls.years, cls.values
    if len(cy) < 2:
        cy, cv = list(years), list(values)
    x = np.asarray(cy, float)
    y = np.asarray(cv, float)
    est = _pchip_or_logtrend(x, y, target)
    if est is None:
        return None
    median = float(np.median(y))
    is_extrap = target < x.min() or target > x.max()
    return M.cap_to_median(est, median, is_extrap)


def est_full(years, values, target, ctx):
    """Full pipeline: spike removal + (regime split for extrap), then
    pchip-log interpolation / shrinkage-toward-sector extrapolation + cap."""
    thr = ctx.get("jump_threshold", M.DEFAULT_JUMP_LOG)
    extrapolating = target > max(years)
    cls = M.classify_series(years, values, jump_threshold_log=thr,
                            confirm_year=max(years),
                            split_breaks=extrapolating)
    cy, cv = cls.years, cls.values
    if len(cy) < 2:
        cy, cv = list(years), list(values)
    x = np.asarray(cy, float)
    y = np.asarray(cv, float)
    if extrapolating:
        sg = ctx.get("sector_growth")
        sector_log_growth = float(np.log(sg)) if sg and sg > 0 else None
        est = M.extrapolate_shrinkage(x, y, target, sector_log_growth, robust=True)
    else:
        est = M.interpolate_log_pchip(x, y, target)
    if est is None:
        return None
    median = float(np.median(y))
    is_extrap = target < x.min() or target > x.max()
    return M.cap_to_median(est, median, is_extrap)


def est_pipeline(years, values, target, ctx):
    """Shared production entry point: methodology.estimate_intensity_series."""
    reported = {int(y): float(v) for y, v in zip(years, values)}
    thr = ctx.get("jump_threshold", M.DEFAULT_JUMP_LOG)
    sg = ctx.get("sector_growth")
    slg = float(np.log(sg)) if sg and sg > 0 else None
    res = M.estimate_intensity_series(reported, [target],
                                      jump_threshold_log=thr, sector_log_growth=slg)
    est = res.get(int(target))
    return est.value if est else None


ESTIMATORS: Dict[str, Estimator] = {
    "baseline (OLS+cap)": est_baseline,
    "robust (TheilSen+cap)": est_robust,
    "pchip-log (+log-trend)": est_pchip_log,
    "classified+pchip-log": est_classified,
    "full (+shrinkage)": est_full,
    "pipeline (shared API)": est_pipeline,
}


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

def run_recent_year_holdout(series, isin_to_sector):
    """Hold out the last K years per company; estimate them from the rest."""
    print("\n=== RECENT-YEAR HOLDOUT (nowcasting scenario) ===")
    for horizon in range(1, MAX_HORIZON + 1):
        print(f"\n-- Horizon +{horizon} year(s) beyond last visible --")
        per_est: Dict[str, List[float]] = {k: [] for k in ESTIMATORS}
        for isin, ints in series.items():
            yrs = sorted(ints)
            if len(yrs) < MIN_HISTORY:
                continue
            target = yrs[-horizon]
            visible_years = [y for y in yrs if y < target]
            if len(visible_years) < 2:
                continue
            visible_vals = [ints[y] for y in visible_years]
            cutoff = target - 1
            sector = isin_to_sector.get(isin, "UNKNOWN")
            if cutoff not in _THRESHOLD_CACHE:
                _THRESHOLD_CACHE[cutoff] = compute_sector_thresholds(series, isin_to_sector, cutoff)
                _GROWTH_CACHE[cutoff] = compute_sector_growth(series, isin_to_sector, cutoff)
            thresholds = _THRESHOLD_CACHE[cutoff]
            growth = _GROWTH_CACHE[cutoff]
            ctx = {
                "jump_threshold": thresholds.get(sector, M.DEFAULT_JUMP_LOG),
                "sector_growth": growth.get(sector),
            }
            actual = ints[target]
            for name, fn in ESTIMATORS.items():
                est = fn(visible_years, visible_vals, target, ctx)
                if est is not None and actual > 0:
                    per_est[name].append((est - actual) / actual)
        for name in ESTIMATORS:
            summarize(name, per_est[name])


def run_interpolation_holdout(series, isin_to_sector):
    """Hide one middle year; estimate it (legacy scenario, for context)."""
    print("\n=== MIDDLE-YEAR HOLDOUT (interpolation scenario) ===")
    per_est: Dict[str, List[float]] = {k: [] for k in ESTIMATORS}
    full_cutoff = 9999
    thresholds = compute_sector_thresholds(series, isin_to_sector, full_cutoff)
    growth = compute_sector_growth(series, isin_to_sector, full_cutoff)
    for isin, ints in series.items():
        yrs = sorted(ints)
        if len(yrs) < MIN_HISTORY:
            continue
        sector = isin_to_sector.get(isin, "UNKNOWN")
        ctx = {
            "jump_threshold": thresholds.get(sector, M.DEFAULT_JUMP_LOG),
            "sector_growth": growth.get(sector),
        }
        for i in range(1, len(yrs) - 1):
            target = yrs[i]
            visible_years = [y for y in yrs if y != target]
            visible_vals = [ints[y] for y in visible_years]
            actual = ints[target]
            for name, fn in ESTIMATORS.items():
                est = fn(visible_years, visible_vals, target, ctx)
                if est is not None and actual > 0:
                    per_est[name].append((est - actual) / actual)
    for name in ESTIMATORS:
        summarize(name, per_est[name])


def main():
    data = load_real_data()
    if data is None:
        return
    series = build_company_series(data)
    isin_to_sector = sector_map(data)
    print(f"Loaded {len(series)} companies with usable intensity series.")
    print(f"Companies with >= {MIN_HISTORY} reported years: "
          f"{sum(1 for v in series.values() if len(v) >= MIN_HISTORY)}")

    run_recent_year_holdout(series, isin_to_sector)
    if os.environ.get("SKIP_INTERP") != "1":
        run_interpolation_holdout(series, isin_to_sector)


if __name__ == "__main__":
    main()
