"""FastAPI backend for the Carbon Attribution dashboard.

Wraps the existing Python model unchanged. The estimator itself lives in
methodology.py and carbon_calculator.py; this layer only selects a variant,
caches results and shapes them for the front end.
"""
from __future__ import annotations

import io
import json
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from carbon_calculator import CarbonCalculator  # noqa: E402
from data_persistence import DataPersistence  # noqa: E402
from api.variants import VARIANTS, DEFAULT_VARIANT, params_for  # noqa: E402

app = FastAPI(title="Carbon Attribution API", version="2.0")

PRECOMPUTED = ROOT / "precomputed"
WEB = ROOT / "web"

_state: Dict[str, object] = {}


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------
def get_data():
    if "data" not in _state:
        dp = DataPersistence()
        data = dp.load_carbon_data()
        if data is None:
            raise HTTPException(503, "No carbon dataset available on the server")
        _state["data"] = data
        _state["calc"] = CarbonCalculator(data)
    return _state["data"]


def get_calc() -> CarbonCalculator:
    get_data()
    return _state["calc"]  # type: ignore


@lru_cache(maxsize=4096)
def _attribution(company: str, variant: str, investment: float) -> Optional[str]:
    """Cached attribution. Returns the frame as JSON so lru_cache stays hashable."""
    calc = get_calc()
    df = calc.calculate_attribution(company, investment, **params_for(variant))
    if df is None or len(df) == 0:
        return None
    return df.to_json(orient="records", date_format="iso")


def attribution_df(company: str, variant: str, investment: float = 1_000_000.0):
    raw = _attribution(company, variant, investment)
    if raw is None:
        return None
    return pd.read_json(io.StringIO(raw), orient="records")


# --------------------------------------------------------------------------
# Meta
# --------------------------------------------------------------------------
@app.get("/api/meta")
def meta():
    data = get_data()
    carbon_years = sorted(int(c) for c in data["carbon"].columns if str(c).isdigit())
    sales_years = sorted(int(c) for c in data["sales"].columns if str(c).isdigit())
    return {
        "variants": list(VARIANTS.values()),
        "default_variant": DEFAULT_VARIANT,
        "companies": int(len(data["reference"])),
        "carbon_years": {"first": carbon_years[0], "last": carbon_years[-1]},
        "sales_years": {"first": sales_years[0], "last": sales_years[-1]},
        "nowcast_from": carbon_years[-1] + 1,
        "disclosure": (
            f"Carbon data ends {carbon_years[-1]}. Revenue and enterprise value "
            f"run to {sales_years[-1]}. Every year after {carbon_years[-1]} is "
            "modelled, not reported."
        ),
    }


@app.get("/api/companies")
def companies(q: str = "", limit: int = 50):
    data = get_data()
    ref = data["reference"]
    df = ref
    if q:
        mask = ref["Company"].astype(str).str.contains(q, case=False, na=False)
        mask |= ref["ISIN"].astype(str).str.contains(q, case=False, na=False)
        df = ref[mask]
    df = df.head(limit)
    return [
        {"isin": r.ISIN, "name": r.Company, "sector": r.Sector, "country": r.Country}
        for r in df.itertuples()
    ]


# --------------------------------------------------------------------------
# Company detail, one row per variant
# --------------------------------------------------------------------------
@app.get("/api/company/{company}")
def company_detail(company: str,
                   variants: str = Query(DEFAULT_VARIANT),
                   investment: float = 1_000_000.0):
    wanted = [v.strip() for v in variants.split(",") if v.strip() in VARIANTS]
    if not wanted:
        wanted = [DEFAULT_VARIANT]

    out: Dict[str, object] = {"company": company, "investment": investment, "series": {}}
    for v in wanted:
        df = attribution_df(company, v, investment)
        if df is None:
            continue
        df = df.sort_values(["year", "month"])
        monthly = [
            {
                "date": str(r["date"])[:10],
                "year": int(r["year"]),
                "value": float(r["monthly_emissions_attributed"]),
                "lower": float(r.get("monthly_emissions_lower", np.nan))
                if pd.notna(r.get("monthly_emissions_lower")) else None,
                "upper": float(r.get("monthly_emissions_upper", np.nan))
                if pd.notna(r.get("monthly_emissions_upper")) else None,
                "quality": r.get("data_quality", "unknown"),
            }
            for _, r in df.iterrows()
        ]
        annual = (df.groupby("year")
                    .agg(value=("monthly_emissions_attributed", "sum"),
                         quality=("data_quality", "first"),
                         ev=("enterprise_value", "first"))
                    .reset_index())
        out["series"][v] = {
            "monthly": monthly,
            "annual": [
                {"year": int(r.year), "value": float(r.value),
                 "quality": str(r.quality), "ev": float(r.ev) if pd.notna(r.ev) else None}
                for r in annual.itertuples()
            ],
            "meta": VARIANTS[v],
        }

    if not out["series"]:
        raise HTTPException(404, f"No attribution available for {company}")

    # Headline reduction, reported-only vs including nowcast, per variant.
    out["headline"] = {}
    for v, s in out["series"].items():
        ann = s["annual"]
        rep = [a for a in ann if a["quality"] == "reported"]
        out["headline"][v] = {
            "full": _pct_change(ann),
            "reported_only": _pct_change(rep),
            "reported_last_year": rep[-1]["year"] if rep else None,
            "final_year": ann[-1]["year"] if ann else None,
        }
    return out


def _pct_change(rows: List[dict]) -> Optional[float]:
    if len(rows) < 2 or not rows[0]["value"]:
        return None
    return (rows[-1]["value"] / rows[0]["value"] - 1) * 100


# --------------------------------------------------------------------------
# Portfolio, with an exact three-way decomposition
# --------------------------------------------------------------------------
@app.get("/api/portfolios")
def portfolios():
    lib = PRECOMPUTED / "portfolio_cache.json"
    if lib.exists():
        return json.loads(lib.read_text()).get("portfolios_meta", [])
    return []


@app.get("/api/portfolio/{name}")
def portfolio(name: str, variant: str = DEFAULT_VARIANT):
    cache_file = PRECOMPUTED / "portfolio_cache.json"
    if not cache_file.exists():
        raise HTTPException(503, "Portfolio cache not built. Run precompute_portfolio.py")
    cache = json.loads(cache_file.read_text())
    key = f"{name}::{variant}"
    if key not in cache.get("portfolios", {}):
        raise HTTPException(404, f"No cached portfolio {name} for variant {variant}")
    return cache["portfolios"][key]


# --------------------------------------------------------------------------
# Backtest evidence
# --------------------------------------------------------------------------
@app.get("/api/backtest")
def backtest():
    f = PRECOMPUTED / "backtest.json"
    if not f.exists():
        raise HTTPException(503, "Backtest artefact not built. Run precompute_backtest.py")
    return json.loads(f.read_text())


@app.get("/api/health")
def health():
    return {"ok": True}


# --------------------------------------------------------------------------
# Static front end
# --------------------------------------------------------------------------
if WEB.exists():
    app.mount("/assets", StaticFiles(directory=str(WEB / "assets")), name="assets")

    @app.get("/")
    def index():
        return FileResponse(str(WEB / "index.html"))

    @app.get("/{path:path}")
    def spa(path: str):
        candidate = WEB / path
        if candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(WEB / "index.html"))
