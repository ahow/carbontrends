#!/usr/bin/env python3
"""Refresh enterprise values from FMP and write precomputed/market_refresh.json.

Applies FMP's EV *change* to the dataset's own EV level (see fmp_live.py for
why levels are not spliced). Run after each data refresh, or on a schedule.

Usage:
    FMP_API_KEY=... python refresh_market_data.py            # portfolio holdings
    FMP_API_KEY=... python refresh_market_data.py --all      # whole universe
    FMP_API_KEY=... python refresh_market_data.py --limit 50
"""
from __future__ import annotations

import argparse, datetime as dt, json, sys, time
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import fmp_live
from data_persistence import DataPersistence
from precompute_portfolio import load_holdings, HOLDINGS_FILE

OUT = ROOT / "precomputed" / "market_refresh.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="whole universe, not just holdings")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-fx", action="store_true", help="skip the FX adjustment")
    args = ap.parse_args()

    if not fmp_live.available():
        raise SystemExit("FMP_API_KEY not set")

    data = DataPersistence().load_carbon_data()
    if data is None:
        raise SystemExit("no carbon dataset")
    ev = data["ev"].set_index("ISIN")
    ev_years = sorted(int(c) for c in ev.columns if str(c).isdigit())

    if args.all:
        isins = [i for i in ev.index]
    else:
        periods = load_holdings(HOLDINGS_FILE)
        isins = sorted({i for p in periods.values() for i in p})
    if args.limit:
        isins = isins[: args.limit]

    print(f"refreshing {len(isins)} companies (fx={'off' if args.no_fx else 'on'})")
    results, t0 = {}, time.time()
    stats = {"fmp_ratio": 0, "dataset": 0, "unavailable": 0}

    for n, isin in enumerate(isins, 1):
        if isin not in ev.index:
            continue
        row = ev.loc[isin]
        have = [y for y in ev_years if pd.notna(row.get(y)) and row.get(y) > 0]
        if not have:
            continue
        base_year = max(have)
        r = fmp_live.refresh_ev(isin, base_year, float(row[base_year]),
                                apply_fx=not args.no_fx)
        results[isin] = r.to_dict()
        stats[r.source] = stats.get(r.source, 0) + 1
        if n % 10 == 0:
            print(f"  {n}/{len(isins)}  ({time.time()-t0:.0f}s)  "
                  f"refreshed={stats['fmp_ratio']}", flush=True)

    # Second pass over everything that did not come back cleanly. Sampled
    # failures resolve correctly when retried individually, so most of them are
    # transport flakiness rather than missing data, and a single retry recovers
    # a large share of them.
    retry = [i for i, v in results.items() if v["source"] != "fmp_ratio"
             and "not resolvable" not in v["note"] or v["source"] == "unavailable"]
    retry = [i for i, v in results.items() if v["source"] != "fmp_ratio"]
    if retry:
        print(f"\nsecond pass over {len(retry)} companies that did not resolve")
        recovered = 0
        for n, isin in enumerate(retry, 1):
            time.sleep(0.4)
            row = ev.loc[isin]
            have = [y for y in ev_years if pd.notna(row.get(y)) and row.get(y) > 0]
            if not have:
                continue
            r = fmp_live.refresh_ev(isin, max(have), float(row[max(have)]),
                                    apply_fx=not args.no_fx)
            if r.source == "fmp_ratio":
                prev = results[isin]["source"]
                results[isin] = r.to_dict()
                stats["fmp_ratio"] += 1
                stats[prev] = max(0, stats.get(prev, 1) - 1)
                recovered += 1
            if n % 15 == 0:
                print(f"  retry {n}/{len(retry)}  recovered={recovered}", flush=True)
        print(f"  second pass recovered {recovered}")

    applied = [v for v in results.values() if v["source"] == "fmp_ratio"]
    moves = sorted((v["ev_usd"] / v["base_ev_usd"] - 1) * 100 for v in applied)
    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "fx_applied": not args.no_fx,
        "counts": stats,
        "companies": results,
        "summary": {
            "n_refreshed": len(applied),
            "median_move_pct": moves[len(moves) // 2] if moves else None,
            "p10_move_pct": moves[int(len(moves) * 0.1)] if moves else None,
            "p90_move_pct": moves[int(len(moves) * 0.9)] if moves else None,
        },
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1))

    print(f"\nwrote {OUT} in {time.time()-t0:.0f}s")
    print(f"  refreshed {len(applied)}, fell back to dataset {stats['dataset']}")
    if moves:
        s = payload["summary"]
        print(f"  EV move vs dataset: median {s['median_move_pct']:+.1f}%  "
              f"p10 {s['p10_move_pct']:+.1f}%  p90 {s['p90_move_pct']:+.1f}%")
        reasons = {}
        for v in results.values():
            if v["source"] != "fmp_ratio" and v["note"]:
                reasons[v["note"]] = reasons.get(v["note"], 0) + 1
        if reasons:
            print("  fallback reasons:")
            for k, c in sorted(reasons.items(), key=lambda x: -x[1])[:6]:
                print(f"    {c:4d}  {k}")


if __name__ == "__main__":
    main()
