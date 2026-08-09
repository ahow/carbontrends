#!/usr/bin/env python3
"""Precompute backtest accuracy/bias by horizon and dump to JSON for the API.

The full harness takes ~25 minutes, so the dashboard reads a committed JSON
artefact rather than recomputing. Re-run this whenever the estimator or the
underlying data changes; the dashboard surfaces `generated_at` so a stale
artefact is visible rather than silent.
"""
import json, time, datetime as dt
import numpy as np
import methodology as M
from backtest_methodology import (build_company_series, sector_map, load_real_data,
                                  compute_sector_growth, compute_sector_thresholds,
                                  MIN_HISTORY)

OUT = "precomputed/backtest.json"
HORIZONS = (1, 2, 3)

VARIANTS = {
    "legacy":  dict(cap_mode="median", drift_offset=0.0),
    "current": dict(cap_mode="anchor", drift_offset=0.0),
    "drift":   dict(cap_mode="anchor", drift_offset=0.045),
}


def stats(errs):
    if not errs:
        return None
    s = np.array(errs, float)
    a = np.abs(s)
    return {
        "n": int(len(a)),
        "median_abs": float(np.median(a)),
        "p90_abs": float(np.percentile(a, 90)),
        "share_over_50": float((a > 0.5).mean()),
        "median_signed": float(np.median(s)),
        "q80": float(np.percentile(a, 80)),
        "q90": float(np.percentile(a, 90)),
        "q95": float(np.percentile(a, 95)),
    }


def main():
    t0 = time.time()
    data = load_real_data()
    series = build_company_series(data)
    i2s = sector_map(data)
    ctx_cache = {}

    out = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "n_companies": len(series),
        "horizons": {},
        "benchmarks": {},
        "notes": {
            "horizon": ("Last K reported years hidden jointly; target is the final "
                        "year, so the gap between last visible year and target "
                        "really is K."),
            "bias": ("Median signed error. Positive means the model reads HIGH, "
                     "i.e. it understates decarbonisation."),
        },
    }

    for h in HORIZONS:
        per_variant = {k: [] for k in VARIANTS}
        persistence = []
        for isin, ints in series.items():
            yrs = sorted(ints)
            if len(yrs) < MIN_HISTORY:
                continue
            vis = yrs[:-h]
            if len(vis) < 2:
                continue
            target = yrs[-1]
            if target - vis[-1] != h:
                continue
            actual = ints[target]
            if actual <= 0:
                continue
            cutoff = vis[-1]
            if cutoff not in ctx_cache:
                ctx_cache[cutoff] = (compute_sector_thresholds(series, i2s, cutoff),
                                     compute_sector_growth(series, i2s, cutoff))
            thr_m, grw_m = ctx_cache[cutoff]
            sec = i2s.get(isin, "UNKNOWN")
            g = grw_m.get(sec)
            slg = float(np.log(g)) if g and g > 0 else None
            rep = {y: ints[y] for y in vis}
            persistence.append((ints[vis[-1]] - actual) / actual)
            for name, kw in VARIANTS.items():
                r = M.estimate_intensity_series(
                    rep, [target],
                    jump_threshold_log=thr_m.get(sec, M.DEFAULT_JUMP_LOG),
                    sector_log_growth=slg, **kw)
                e = r.get(target)
                if e and e.value > 0:
                    per_variant[name].append((e.value - actual) / actual)
        out["horizons"][str(h)] = {k: stats(v) for k, v in per_variant.items()}
        out["benchmarks"][str(h)] = {"persistence": stats(persistence)}
        print(f"horizon {h} done  ({time.time()-t0:.0f}s)", flush=True)

    import os
    os.makedirs("precomputed", exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print(f"wrote {OUT} in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
