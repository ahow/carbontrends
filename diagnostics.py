#!/usr/bin/env python3
"""Targeted diagnostics that the accuracy harness does not cover.

1. Cap binding    - how often does cap_to_median override the last reported
                    value, and in which direction?
2. Band coverage  - do the stated confidence bands actually contain the
                    realised value at the advertised rate?

Run after backtest_methodology.py. Both checks informed the recommendation to
re-anchor the extrapolation cap and to rebase the bands on empirical quantiles.
"""
import numpy as np
import methodology as M
from backtest_methodology import (build_company_series, sector_map, load_real_data,
                                  compute_sector_growth, compute_sector_thresholds,
                                  MIN_HISTORY, MAX_HORIZON)


def cap_binding(series, i2s):
    print("\n=== CAP BINDING (extrapolation) ===")
    print("cap_to_median clamps forward estimates to [median/1.5, median*1.5] of the")
    print("current regime. Where the last reported value already sits outside that")
    print("band, the cap overrides the company's own most recent observation.\n")
    up = dn = tot = 0
    worst = []
    for isin, ints in series.items():
        yrs = sorted(ints)
        if len(yrs) < MIN_HISTORY:
            continue
        cls = M.classify_series(yrs, [ints[y] for y in yrs],
                                jump_threshold_log=M.DEFAULT_JUMP_LOG,
                                confirm_year=max(yrs), split_breaks=True)
        if len(cls.values) < 2:
            continue
        med = float(np.median(cls.values))
        last = float(cls.values[-1])
        tot += 1
        if last < med / 1.5:
            up += 1
            worst.append((last / med, isin, last, med))
        elif last > med * 1.5:
            dn += 1
    print(f"  companies assessed: {tot}")
    print(f"  last value BELOW floor -> forced UP:   {up:5d} ({100*up/tot:5.1f}%)")
    print("     these are the fastest decarbonisers; the cap raises their forecast")
    print("     above their own most recent reported intensity")
    print(f"  last value ABOVE ceiling -> forced DOWN: {dn:5d} ({100*dn/tot:5.1f}%)")
    for ratio, isin, last, med in sorted(worst)[:5]:
        print(f"     e.g. {isin}: last={last:.3e}  regime median={med:.3e}  "
              f"last is {ratio*100:.0f}% of median")


def band_coverage(series, i2s):
    print("\n=== CONFIDENCE-BAND COVERAGE ===")
    print("Stated bands are median absolute error, so they are ~50% intervals.\n")
    thr_cache, grw_cache = {}, {}
    for horizon in range(1, MAX_HORIZON + 1):
        errs = []
        for isin, ints in series.items():
            yrs = sorted(ints)
            if len(yrs) < MIN_HISTORY:
                continue
            vis = yrs[:-horizon]
            if len(vis) < 2:
                continue
            target = yrs[-1]
            if target - vis[-1] != horizon:
                continue
            cutoff = vis[-1]
            if cutoff not in thr_cache:
                thr_cache[cutoff] = compute_sector_thresholds(series, i2s, cutoff)
                grw_cache[cutoff] = compute_sector_growth(series, i2s, cutoff)
            sec = i2s.get(isin, "UNKNOWN")
            g = grw_cache[cutoff].get(sec)
            res = M.estimate_intensity_series(
                {y: ints[y] for y in vis}, [target],
                jump_threshold_log=thr_cache[cutoff].get(sec, M.DEFAULT_JUMP_LOG),
                sector_log_growth=float(np.log(g)) if g and g > 0 else None)
            e = res.get(target)
            if e and ints[target] > 0:
                errs.append(abs(e.value - ints[target]) / ints[target])
        a = np.array(errs)
        stated = M.band_for(horizon) if hasattr(M, "band_for") else None
        line = f"  h=+{horizon}: n={len(a)}"
        if stated:
            line += f"  stated band=+-{stated*100:.0f}% -> actual coverage {100*(a<=stated).mean():.1f}%"
        print(line)
        print(f"          empirical quantiles  p50={np.percentile(a,50)*100:5.1f}%"
              f"  p80={np.percentile(a,80)*100:6.1f}%"
              f"  p90={np.percentile(a,90)*100:6.1f}%"
              f"  p95={np.percentile(a,95)*100:6.1f}%")


if __name__ == "__main__":
    data = load_real_data()
    if data is None:
        raise SystemExit("no persisted carbon data found")
    series = build_company_series(data)
    i2s = sector_map(data)
    cap_binding(series, i2s)
    band_coverage(series, i2s)
