"""
Carbon intensity estimation methodology.

Pure, testable functions shared by the live calculator (carbon_calculator.py)
and the backtest harness (backtest_methodology.py), so the backtest measures
the exact code path used in production.

All series operate on carbon intensity (tCO2e per USD of sales), which is
strictly positive and multiplicative in nature. Working in log-space therefore
gives non-negativity for free and treats percentage moves symmetrically.

Layers (per methodology review):
  L1  classify_series        - Clean / Structural Break / Spike-Reversal
  L2  interpolate_series      - log-space PCHIP interpolation within range
  L3  extrapolate_series      - shrinkage toward sector trend out of range
  ..  estimate_intensities    - full pipeline tying the layers together
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple
from dataclasses import dataclass, field

import numpy as np

try:
    from scipy.stats import theilslopes
    from scipy.interpolate import PchipInterpolator, CubicSpline
    _HAVE_SCIPY = True
except Exception:  # pragma: no cover - scipy is expected to be present
    _HAVE_SCIPY = False


# ---------------------------------------------------------------------------
# Trend estimators
# ---------------------------------------------------------------------------

def ols_trend(years: Sequence[float], values: Sequence[float]) -> Tuple[float, float]:
    """Ordinary least-squares slope/intercept. Mirrors the legacy method."""
    x = np.asarray(years, dtype=float)
    y = np.asarray(values, dtype=float)
    if len(x) < 2:
        return 0.0, float(y[0]) if len(y) else 0.0
    slope, intercept = np.polyfit(x, y, 1)
    return float(slope), float(intercept)


def robust_trend(years: Sequence[float], values: Sequence[float]) -> Tuple[float, float]:
    """Theil-Sen robust slope/intercept - resistant to outliers.

    Falls back to OLS when scipy is unavailable or there are <3 points.
    """
    x = np.asarray(years, dtype=float)
    y = np.asarray(values, dtype=float)
    if len(x) < 3 or not _HAVE_SCIPY:
        return ols_trend(x, y)
    try:
        slope, intercept, _, _ = theilslopes(y, x)
        return float(slope), float(intercept)
    except Exception:
        return ols_trend(x, y)


def annual_pct_changes(years: Sequence[int], values: Sequence[float]) -> List[float]:
    """Year-over-year fractional changes for consecutive reported years only."""
    yrs = list(years)
    vals = list(values)
    out: List[float] = []
    for i in range(1, len(yrs)):
        if yrs[i] - yrs[i - 1] == 1 and vals[i - 1] > 0:
            out.append((vals[i] - vals[i - 1]) / vals[i - 1])
    return out


def median_log_growth(years: Sequence[int], values: Sequence[float]) -> Optional[float]:
    """Median per-year growth in log-space over consecutive reported years.

    Returns a multiplicative growth factor (e.g. 0.97 == -3%/yr) or None.
    """
    yrs = list(years)
    vals = list(values)
    logs = []
    for i in range(1, len(yrs)):
        if yrs[i] - yrs[i - 1] == 1 and vals[i - 1] > 0 and vals[i] > 0:
            logs.append(np.log(vals[i] / vals[i - 1]))
    if not logs:
        return None
    return float(np.exp(np.median(logs)))


# ---------------------------------------------------------------------------
# Capping helpers
# ---------------------------------------------------------------------------

def cap_to_median(value: float, median: float, is_extrapolation: bool,
                  extrap_factor: float = 1.5, interp_factor: float = 2.0) -> float:
    """Legacy adaptive capping around the series median."""
    factor = extrap_factor if is_extrapolation else interp_factor
    lo = median / factor
    hi = median * factor
    capped = float(np.clip(value, lo, hi))
    if capped <= 0:
        capped = median * 0.5
    return capped


# ---------------------------------------------------------------------------
# Layer 1: classification (Clean / Structural Break / Spike-Reversal)
# ---------------------------------------------------------------------------

# Default jump threshold in log-space. log(1.5) ~ 0.405 => a +50% / -33% move.
DEFAULT_JUMP_LOG = float(np.log(1.5))


@dataclass
class Classification:
    years: List[int]                 # cleaned years (spikes removed, pre-break dropped)
    values: List[float]              # cleaned values aligned with years
    labels: Dict[int, str] = field(default_factory=dict)   # year -> clean|spike|break
    break_year: Optional[int] = None  # first year of the retained post-break regime


def sector_jump_threshold(yoy_log_changes: Sequence[float],
                          floor_log: float = DEFAULT_JUMP_LOG,
                          z: float = 3.0) -> float:
    """Sector-aware jump threshold: max(physical floor, z * robust sigma).

    Robust sigma = 1.4826 * MAD of the sector's year-over-year log changes, so a
    volatile sector (tech) tolerates bigger moves than a stable one (utilities).
    """
    arr = np.asarray(list(yoy_log_changes), dtype=float)
    if arr.size == 0:
        return floor_log
    mad = np.median(np.abs(arr - np.median(arr)))
    robust_sigma = 1.4826 * mad
    return float(max(floor_log, z * robust_sigma))


def classify_series(years: Sequence[int], values: Sequence[float],
                    jump_threshold_log: float = DEFAULT_JUMP_LOG,
                    confirm_year: Optional[int] = None,
                    split_breaks: bool = True) -> Classification:
    """Classify a single company's intensity series.

    * Spike/Reversal: a 1-year jump that reverts toward the prior level -> the
      anomalous year is dropped (interpolate through the gap).
    * Structural Break: a jump whose new level is sustained 2+ years -> split and
      retain only the most recent regime (reflects current company structure).
    * Recent break in the last observable year cannot be confirmed sustained, so
      it is left in place (treated as uncertain, not split).

    `confirm_year` is the latest year that can be used to confirm persistence
    (typically the last visible/reported year). Defaults to max(years).
    """
    yrs = [int(y) for y in years]
    vals = [float(v) for v in values]
    labels: Dict[int, str] = {y: "clean" for y in yrs}
    n = len(yrs)
    if n < 3:
        return Classification(years=list(yrs), values=list(vals), labels=labels)

    if confirm_year is None:
        confirm_year = max(yrs)

    logs = np.log(np.asarray(vals, dtype=float))

    # --- Pass 1: spike/reversal detection on interior points ---------------
    keep = [True] * n
    for i in range(1, n - 1):
        up = logs[i] - logs[i - 1]
        down = logs[i + 1] - logs[i]
        if (abs(up) > jump_threshold_log and abs(down) > jump_threshold_log
                and up * down < 0
                and abs(logs[i + 1] - logs[i - 1]) < jump_threshold_log):
            keep[i] = False
            labels[yrs[i]] = "spike"

    c_years = [yrs[i] for i in range(n) if keep[i]]
    c_vals = [vals[i] for i in range(n) if keep[i]]
    c_logs = np.log(np.asarray(c_vals, dtype=float))

    # --- Pass 2: structural break detection on the de-spiked series --------
    m = len(c_years)
    break_idx: Optional[int] = None
    for i in range(1, m):
        jump = c_logs[i] - c_logs[i - 1]
        if abs(jump) <= jump_threshold_log:
            continue
        post = c_logs[i:]
        if len(post) < 2:
            continue  # cannot confirm persistence with <2 post-break points
        # Sustained if the post-break level does NOT revert toward pre-break.
        post_mean = float(np.mean(post))
        reverts = abs(post_mean - c_logs[i - 1]) < abs(jump) / 2.0
        confirmable = c_years[i] <= confirm_year - 1  # need a following year to confirm
        if not reverts and confirmable:
            break_idx = i  # keep scanning; we want the LAST sustained break

    if break_idx is not None and split_breaks:
        kept_years = c_years[break_idx:]
        kept_vals = c_vals[break_idx:]
        for y in c_years[:break_idx]:
            labels[y] = "break"
        return Classification(years=kept_years, values=kept_vals,
                              labels=labels, break_year=c_years[break_idx])

    return Classification(years=c_years, values=c_vals, labels=labels)


# ---------------------------------------------------------------------------
# Log-space interpolation (PCHIP) and extrapolation (robust log-trend)
# ---------------------------------------------------------------------------

def interpolate_log_pchip(years: Sequence[int], values: Sequence[float],
                          target_year: int) -> Optional[float]:
    """Shape-preserving interpolation of a single in-range target in log-space.

    PCHIP avoids the overshoot of natural cubic splines, and log-space keeps
    estimates strictly positive and treats up/down moves symmetrically.
    Only valid for targets strictly inside the observed range.
    """
    x = np.asarray(years, dtype=float)
    y = np.asarray(values, dtype=float)
    if len(x) < 2:
        return None
    if target_year <= x.min() or target_year >= x.max():
        return None  # not an interpolation target
    logy = np.log(y)
    if _HAVE_SCIPY and len(x) >= 2:
        try:
            f = PchipInterpolator(x, logy, extrapolate=False)
            est = float(f(target_year))
            if np.isnan(est):
                est = float(np.interp(target_year, x, logy))
        except Exception:
            est = float(np.interp(target_year, x, logy))
    else:
        est = float(np.interp(target_year, x, logy))
    return float(np.exp(est))


def extrapolate_log_trend(years: Sequence[int], values: Sequence[float],
                          target_year: int,
                          robust: bool = True) -> Optional[float]:
    """Extrapolate an out-of-range target using a trend in log-space.

    A trend on log(intensity) is multiplicative (constant %/yr), which is more
    physically realistic for emissions intensity and cannot go negative.
    """
    x = np.asarray(years, dtype=float)
    y = np.asarray(values, dtype=float)
    if len(x) < 2:
        return float(y[0]) if len(y) else None
    logy = np.log(y)
    slope, intercept = (robust_trend(x, logy) if robust else ols_trend(x, logy))
    return float(np.exp(slope * target_year + intercept))


# Confidence in the company's own trend decays with extrapolation horizon, so
# weight shifts toward the sector trend further out.
HORIZON_WEIGHTS = {1: 0.8, 2: 0.5, 3: 0.3}
HORIZON_WEIGHT_FLOOR = 0.2


def horizon_weight(horizon: int) -> float:
    return HORIZON_WEIGHTS.get(horizon, HORIZON_WEIGHT_FLOOR)


def extrapolate_shrinkage(years: Sequence[int], values: Sequence[float],
                          target_year: int,
                          sector_log_growth: Optional[float],
                          robust: bool = True) -> Optional[float]:
    """Extrapolate by blending the company's own log-trend toward the sector's.

    blended_growth = w * company_growth + (1 - w) * sector_growth   (per year)
    where w decays with the horizon beyond the last observation. Anchored at the
    most recent observed value, compounded multiplicatively over the horizon.
    """
    x = np.asarray(years, dtype=float)
    y = np.asarray(values, dtype=float)
    if len(x) < 2:
        return float(y[0]) if len(y) else None
    logy = np.log(y)
    last_idx = int(np.argmax(x))
    last_year = float(x[last_idx])
    last_val = float(y[last_idx])
    horizon = int(round(target_year - last_year))
    if horizon <= 0:
        # not actually an extrapolation; fall back to plain log-trend
        return extrapolate_log_trend(x, y, target_year, robust=robust)
    company_growth, _ = (robust_trend(x, logy) if robust else ols_trend(x, logy))
    if sector_log_growth is None:
        sector_log_growth = company_growth
    w = horizon_weight(horizon)
    blended = w * company_growth + (1.0 - w) * sector_log_growth
    return float(last_val * np.exp(blended * horizon))


# ---------------------------------------------------------------------------
# Full validated pipeline (single entry point used by app + backtest)
# ---------------------------------------------------------------------------

@dataclass
class IntensityEstimate:
    value: float
    quality: str        # reported | interpolated | spike_filled | extrapolated
    horizon: int = 0     # years beyond last reported (extrapolation only)


def estimate_intensity_series(
        reported: Dict[int, float],
        target_years: Sequence[int],
        jump_threshold_log: float = DEFAULT_JUMP_LOG,
        sector_log_growth: Optional[float] = None,
) -> Dict[int, IntensityEstimate]:
    """Estimate intensity for every target year from reported points.

    Implements the validated pipeline:
      * spike removal (Category C) before any fitting,
      * log-space PCHIP for interior gaps (and spike-filled years),
      * regime-split + shrinkage-toward-sector for forward extrapolation,
      * adaptive median cap on every estimate.
    """
    out: Dict[int, IntensityEstimate] = {}
    years = sorted(reported)
    if not years:
        return out

    if len(reported) < 2:
        only = float(reported[years[0]])
        for ty in target_years:
            out[int(ty)] = IntensityEstimate(only, "reported" if ty in reported
                                             else "extrapolated")
        return out

    last_year = years[-1]

    # De-spiked series for interpolation (keep full history, no regime split).
    interp_cls = classify_series(years, [reported[y] for y in years],
                                 jump_threshold_log=jump_threshold_log,
                                 confirm_year=last_year, split_breaks=False)
    interp_years = interp_cls.years
    interp_vals = interp_cls.values
    spike_years = {y for y, lab in interp_cls.labels.items() if lab == "spike"}

    # Regime-split series for extrapolation (post-break reflects current state).
    extrap_cls = classify_series(years, [reported[y] for y in years],
                                 jump_threshold_log=jump_threshold_log,
                                 confirm_year=last_year, split_breaks=True)
    extrap_years = extrap_cls.years
    extrap_vals = extrap_cls.values

    # Cap interpolations against full-history median, but extrapolations against
    # the current-regime (post-break) median - matching the validated harness.
    interp_median = (float(np.median(interp_vals)) if interp_vals
                     else float(np.median(list(reported.values()))))
    extrap_median = (float(np.median(extrap_vals)) if extrap_vals
                     else interp_median)

    for ty in target_years:
        ty = int(ty)
        if ty in reported and ty not in spike_years:
            out[ty] = IntensityEstimate(float(reported[ty]), "reported")
            continue

        if ty <= last_year:
            est = interpolate_log_pchip(interp_years, interp_vals, ty)
            if est is None:
                est = float(np.interp(ty, interp_years, interp_vals))
            quality = "spike_filled" if ty in spike_years else "interpolated"
            est = cap_to_median(est, interp_median, is_extrapolation=False)
            horizon = 0
        else:
            est = extrapolate_shrinkage(extrap_years, extrap_vals, ty,
                                        sector_log_growth, robust=True)
            quality = "extrapolated"
            horizon = ty - last_year
            if est is None:
                continue
            est = cap_to_median(est, extrap_median, is_extrapolation=True)

        if est is None:
            continue
        out[ty] = IntensityEstimate(est, quality, horizon)

    return out


# Empirical relative error by extrapolation horizon (from backtest_methodology.py
# median errors), used to draw confidence bands that widen with the horizon.
REPORTED_BAND = 0.08          # +-8% measurement uncertainty on reported years
INTERPOLATED_BAND = 0.11      # interior-gap median error
EXTRAP_BAND_BY_HORIZON = {1: 0.16, 2: 0.17, 3: 0.18}
EXTRAP_BAND_FLOOR = 0.20


def band_for(quality: str, horizon: int = 0) -> float:
    """Relative half-width of the confidence band for an estimate."""
    if quality == "reported":
        return REPORTED_BAND
    if quality in ("interpolated", "spike_filled"):
        return INTERPOLATED_BAND
    return EXTRAP_BAND_BY_HORIZON.get(horizon, EXTRAP_BAND_FLOOR)


# ---------------------------------------------------------------------------
# Baseline estimator (legacy: OLS linear + adaptive median cap)
# ---------------------------------------------------------------------------

def estimate_linear_baseline(years: Sequence[int], values: Sequence[float],
                             target_year: int) -> Optional[float]:
    """Reproduce the legacy production estimator for a single target year."""
    x = np.asarray(years, dtype=float)
    y = np.asarray(values, dtype=float)
    if len(x) < 2:
        return float(y[0]) if len(y) else None
    slope, intercept = ols_trend(x, y)
    est = slope * target_year + intercept
    median = float(np.median(y))
    is_extrap = target_year < x.min() or target_year > x.max()
    return cap_to_median(est, median, is_extrap)
