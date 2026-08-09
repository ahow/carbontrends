#!/usr/bin/env python3
"""Precompute portfolio series and the emissions-change decomposition.

WHY A DECOMPOSITION
-------------------
Attributed financed emissions are  v * C / EV  where v is the amount invested,
C is the company's absolute emissions and EV its enterprise value. A portfolio's
attributed emissions can therefore fall for three quite different reasons:

  1. the companies held actually emitted less        (real decarbonisation)
  2. their enterprise values rose                    (a market rally)
  3. the portfolio was reweighted toward cleaner names (allocation)

Only the first is decarbonisation in any meaningful sense. Reporting the total
alone lets a bull market read as climate progress -- the standard critique of
EV-denominated financed-emissions metrics.

The decomposition below is exact, not approximate. Between t0 and t1:

  emissions effect  = sum  v0 * (C1 - C0) / EV0
  valuation effect  = sum  v0 * C1 * (1/EV1 - 1/EV0)
  allocation effect = sum (v1 - v0) * C1 / EV1
  ------------------------------------------------
  total             = sum  v1*C1/EV1 - v0*C0/EV0

Each term telescopes into the next, so the three sum exactly to the change in
attributed emissions. Holdings that enter or exit are handled naturally by
v0 = 0 or v1 = 0.
"""
from __future__ import annotations

import json, sys, time, datetime as dt
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from carbon_calculator import CarbonCalculator
from data_persistence import DataPersistence
from api.variants import VARIANTS, params_for

OUT = ROOT / "precomputed" / "portfolio_cache.json"
HOLDINGS_FILE = ROOT / "uploaded_files" / "PortfolioHoldings.xlsx"


def load_holdings(path: Path):
    """Sheet name DD.MM.YY -> DataFrame[ISIN, TotalNominal]."""
    xl = pd.ExcelFile(path)
    periods = {}
    for sheet in xl.sheet_names:
        try:
            d, m, y = sheet.split(".")
            date = dt.date(2000 + int(y), int(m), int(d))
        except Exception:
            continue
        df = xl.parse(sheet)
        if "ISIN" not in df.columns or "TotalNominal" not in df.columns:
            continue
        df = df[["ISIN", "TotalNominal"]].dropna()
        df = df[df["TotalNominal"] > 0]
        periods[date] = df.set_index("ISIN")["TotalNominal"].to_dict()
    return dict(sorted(periods.items()))


def company_year_facts(calc, name, variant):
    """{year: (company_absolute_emissions, enterprise_value)} for one variant."""
    df = calc.calculate_attribution(name, 1_000_000.0, **params_for(variant))
    if df is None or len(df) == 0:
        return {}
    out = {}
    for year, g in df.groupby("year"):
        ev = float(g["enterprise_value"].iloc[0])
        own = float(g["ownership_percentage"].iloc[0])
        attributed = float(g["monthly_emissions_attributed"].sum())
        if own <= 0 or ev <= 0:
            continue
        # attributed = own * C  ->  C = attributed / own
        out[int(year)] = (attributed / own, ev, str(g["data_quality"].iloc[0]))
    return out


def main():
    t0 = time.time()
    dp = DataPersistence()
    data = dp.load_carbon_data()
    if data is None:
        raise SystemExit("no carbon data")
    calc = CarbonCalculator(data)
    ref = data["reference"]
    isin_to_name = dict(zip(ref["ISIN"], ref["Company"]))

    periods = load_holdings(HOLDINGS_FILE)
    all_isins = sorted({i for p in periods.values() for i in p})
    print(f"{len(periods)} periods, {len(all_isins)} distinct holdings")

    cache = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
             "portfolios": {}, "portfolios_meta": []}

    name = HOLDINGS_FILE.stem
    for variant in VARIANTS:
        facts = {}
        for n, isin in enumerate(all_isins, 1):
            cname = isin_to_name.get(isin)
            if not cname:
                continue
            try:
                f = company_year_facts(calc, cname, variant)
            except Exception:
                f = {}
            if f:
                facts[isin] = f
            if n % 20 == 0:
                print(f"  {variant}: {n}/{len(all_isins)}  ({time.time()-t0:.0f}s)", flush=True)

        series, decomp = [], []
        prev = None
        for date, holds in periods.items():
            yr = date.year
            total = 0.0
            covered = uncovered = 0
            for isin, v in holds.items():
                f = facts.get(isin, {}).get(yr)
                if not f:
                    uncovered += 1
                    continue
                C, EV, _q = f
                total += v * C / EV
                covered += 1
            quality = "reported"
            qs = [facts[i][yr][2] for i in holds if i in facts and yr in facts[i]]
            if qs and any(q != "reported" for q in qs):
                quality = "estimated" if all(q != "reported" for q in qs) else "mixed"
            series.append({"date": date.isoformat(), "value": total,
                           "holdings": len(holds), "covered": covered,
                           "uncovered": uncovered, "quality": quality})

            if prev is not None:
                p_date, p_holds, p_year = prev
                em = va = al = 0.0
                for isin in set(p_holds) | set(holds):
                    v0 = p_holds.get(isin, 0.0)
                    v1 = holds.get(isin, 0.0)
                    f0 = facts.get(isin, {}).get(p_year)
                    f1 = facts.get(isin, {}).get(yr)
                    if not f0 or not f1:
                        continue
                    C0, EV0, _ = f0
                    C1, EV1, _ = f1
                    em += v0 * (C1 - C0) / EV0
                    va += v0 * C1 * (1.0 / EV1 - 1.0 / EV0)
                    al += (v1 - v0) * C1 / EV1
                decomp.append({"from": p_date.isoformat(), "to": date.isoformat(),
                               "emissions": em, "valuation": va, "allocation": al,
                               "total": em + va + al})
            prev = (date, holds, yr)

        # Cumulative decomposition over the whole period.
        cum = {k: float(sum(d[k] for d in decomp)) for k in
               ("emissions", "valuation", "allocation", "total")}
        first, last = series[0]["value"], series[-1]["value"]
        cache["portfolios"][f"{name}::{variant}"] = {
            "name": name, "variant": variant, "meta": VARIANTS[variant],
            "series": series, "decomposition": decomp, "cumulative": cum,
            "headline": {
                "start": first, "end": last,
                "pct_change": (last / first - 1) * 100 if first else None,
                "start_date": series[0]["date"], "end_date": series[-1]["date"],
            },
        }
        print(f"{variant}: {(last/first-1)*100:+.1f}%  "
              f"emissions {cum['emissions']:+.0f} / valuation {cum['valuation']:+.0f} "
              f"/ allocation {cum['allocation']:+.0f}", flush=True)

    cache["portfolios_meta"] = [{"name": name, "periods": len(periods),
                                 "holdings": len(all_isins),
                                 "start": series[0]["date"], "end": series[-1]["date"]}]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(cache, indent=1))
    print(f"wrote {OUT} in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
