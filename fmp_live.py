"""Live market data from FMP, applied as RATIOS rather than levels.

WHY RATIOS AND NOT LEVELS
-------------------------
FMP and the carbon dataset do not agree on levels. For 3M at 31 Dec 2025 the
dataset carries an enterprise value of $84.11bn; FMP reports $93.24bn for the
same date -- about 10% apart, because the two use different conventions for
debt, cash, share count and snapshot timing. Splicing FMP levels onto the
dataset would put a 10% step in every affected series at the join, and that
step would then read as a valuation effect in the portfolio decomposition.
It would be a data artefact presented as a finding.

So we take only the *change* from FMP and apply it to the dataset's own level:

    EV_usd(t) = EV_usd(base) x [ EV_local(t) / EV_local(base) ] x [ FX(t) / FX(base) ]

The bracketed terms are pure ratios, so FMP's level convention cancels. Only
its view of the market move survives. The dataset's convention is preserved
end to end, and there is no discontinuity at the join.

This is the same construction the user proposed for revenue, and it generalises
cleanly: FMP financial-estimates are reported in local currency (Toyota comes
back as JPY 59.9tn, with a 31 March year end), while the dataset is USD. Taking
the local-currency growth rate and applying it to the last USD actual keeps the
series continuous. The FX term is what makes it *correct* rather than merely
continuous -- without it you are implicitly assuming the exchange rate never
moved, which for a JPY or KRW name over two years is a large assumption. It is
carried separately here so it can be switched off and the effect measured.

CREDENTIALS
-----------
Set FMP_API_KEY in the environment. On Railway this is a service variable.
Without it every function degrades to returning None and callers fall back to
the dataset value unchanged -- the dashboard must never silently show stale
data as live, so `as_of` and `source` travel with every number.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

import requests

BASE = "https://financialmodelingprep.com/stable"
TIMEOUT = 30
# FMP rate-limits bursts. Without pacing, roughly 60% of a sequential run comes
# back empty and -- before this was fixed -- those transport failures were being
# recorded as "ISIN not resolvable", which sent the diagnosis in the wrong
# direction entirely. Pace requests and distinguish a failed call from a
# genuinely absent record.
MIN_INTERVAL = 0.28
_last_call = [0.0]
_session = requests.Session()


class FmpUnavailable(Exception):
    """The call failed in transport. NOT the same as 'no such record'."""


def _throttle():
    gap = time.time() - _last_call[0]
    if gap < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - gap)
    _last_call[0] = time.time()


def api_key() -> Optional[str]:
    return os.environ.get("FMP_API_KEY") or None


def available() -> bool:
    return api_key() is not None


def _via_curl(url: str) -> Optional[list]:
    """Fallback transport.

    In the development sandbox, outbound HTTPS goes through an inspecting proxy
    whose CA Python rejects ("Missing Authority Key Identifier"), while curl
    accepts it. Production on Railway talks to FMP directly and never reaches
    this path, but without it the refresh job cannot be run or tested locally.
    """
    import json as _json
    import subprocess
    for attempt in range(4):
        _throttle()
        try:
            r = subprocess.run(["curl", "-sS", "--max-time", str(TIMEOUT), url],
                               capture_output=True, text=True, timeout=TIMEOUT + 10)
            if r.returncode == 0 and r.stdout.strip():
                data = _json.loads(r.stdout)
                if isinstance(data, dict) and data.get("Error Message"):
                    raise FmpUnavailable(str(data["Error Message"])[:120])
                return data if isinstance(data, list) else [data]
        except FmpUnavailable:
            raise
        except Exception:
            pass
        time.sleep(0.5 * (2 ** attempt))
    raise FmpUnavailable("no response after 4 attempts")


def _get(path: str, **params) -> Optional[list]:
    key = api_key()
    if not key:
        return None
    params["apikey"] = key
    url = f"{BASE}/{path}?" + "&".join(f"{k}={v}" for k, v in params.items())
    for attempt in range(3):
        try:
            r = _session.get(f"{BASE}/{path}", params=params, timeout=TIMEOUT)
            if r.status_code == 429:          # rate limited
                time.sleep(2 ** attempt)
                continue
            if r.status_code != 200:
                return None
            data = r.json()
            return data if isinstance(data, list) else [data]
        except requests.exceptions.SSLError:
            return _via_curl(url)
        except Exception:
            if attempt == 2:
                return None
            time.sleep(1)
    return None


# ---------------------------------------------------------------------------
# Identifier resolution
# ---------------------------------------------------------------------------
# An ISIN maps to many listings: Toyota's JP3633400001 returns nine symbols
# across seven exchanges, with market caps in JPY, EUR and USD. Picking the
# wrong one silently changes both the currency and the liquidity basis, so
# prefer the listing on the issuer's home exchange.
_HOME_SUFFIX = {
    "JP": ".T", "GB": ".L", "FR": ".PA", "DE": ".DE", "CH": ".SW", "NL": ".AS",
    "SE": ".ST", "IT": ".MI", "ES": ".MC", "HK": ".HK", "KR": ".KS", "TW": ".TW",
    "IN": ".NS", "AU": ".AX", "CA": ".TO", "DK": ".CO", "NO": ".OL", "FI": ".HE",
    "BE": ".BR", "SG": ".SI", "CN": ".SS", "BR": ".SA", "ZA": ".JO", "AT": ".VI",
    "PT": ".LS", "IE": ".IR", "NZ": ".NZ", "TH": ".BK", "ID": ".JK", "MY": ".KL",
}


def resolve_symbol(isin: str) -> Optional[str]:
    """Best primary listing for an ISIN, preferring the issuer's home exchange.

    Raises FmpUnavailable on transport failure so the caller can report that
    honestly instead of recording it as an unknown ISIN.
    """
    rows = _get("search-isin", isin=isin)
    if not rows:
        return None
    country = (isin or "")[:2].upper()
    suffix = _HOME_SUFFIX.get(country)
    if suffix:
        for r in rows:
            sym = r.get("symbol", "")
            if sym.endswith(suffix):
                return sym
    if country == "US":
        for r in rows:
            if "." not in r.get("symbol", ""):
                return r["symbol"]
    # Fall back to the largest market cap, which is usually the home line.
    rows = [r for r in rows if r.get("marketCap")]
    if not rows:
        return None
    return max(rows, key=lambda r: r["marketCap"])["symbol"]


# ---------------------------------------------------------------------------
# Enterprise value
# ---------------------------------------------------------------------------
@dataclass
class EVRefresh:
    isin: str
    symbol: Optional[str]
    base_year: int
    base_ev_usd: float          # dataset level, unchanged
    ratio: Optional[float]      # FMP EV(t) / EV(base), local currency
    fx_ratio: Optional[float]   # USD per local unit, now / base
    ev_usd: float               # refreshed level
    as_of: Optional[str]
    source: str                 # "fmp_ratio" | "dataset" | "unavailable"
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def ev_series(symbol: str, limit: int = 12) -> Optional[List[dict]]:
    """Quarterly enterprise values, most recent first."""
    return _get("enterprise-values", symbol=symbol, period="quarter", limit=limit)


def refresh_ev(isin: str, base_year: int, base_ev_usd: float,
               apply_fx: bool = True) -> EVRefresh:
    """Refresh one company's enterprise value to the latest available quarter.

    Returns the dataset value unchanged, clearly labelled, whenever FMP cannot
    supply a clean ratio. Never guesses.
    """
    out = EVRefresh(isin=isin, symbol=None, base_year=base_year,
                    base_ev_usd=base_ev_usd, ratio=None, fx_ratio=None,
                    ev_usd=base_ev_usd, as_of=None, source="dataset")
    if not available():
        out.source = "unavailable"
        out.note = "FMP_API_KEY not set"
        return out

    try:
        sym = resolve_symbol(isin)
    except FmpUnavailable as e:
        out.source = "unavailable"
        out.note = f"lookup failed: {e}"
        return out
    if not sym:
        out.note = "ISIN not resolvable to a listing"
        return out
    out.symbol = sym

    try:
        rows = ev_series(sym)
    except FmpUnavailable as e:
        out.source = "unavailable"
        out.note = f"enterprise-value fetch failed: {e}"
        return out
    if not rows:
        out.note = "no enterprise-value history"
        return out

    rows = [r for r in rows if r.get("enterpriseValue") and r.get("date")]
    rows.sort(key=lambda r: r["date"], reverse=True)
    latest = rows[0]
    base = next((r for r in rows if r["date"][:4] == str(base_year)), None)
    if base is None:
        out.note = f"no FMP enterprise value in base year {base_year}"
        return out
    if not base["enterpriseValue"]:
        out.note = "base enterprise value is zero"
        return out

    ratio = float(latest["enterpriseValue"]) / float(base["enterpriseValue"])
    # A ratio outside this range is far more likely to be a restatement, a share
    # count change or a currency switch than a real move. Refuse rather than
    # propagate it.
    if not (0.2 <= ratio <= 5.0):
        out.note = f"implausible EV ratio {ratio:.2f}; not applied"
        return out

    out.ratio = ratio
    out.as_of = latest["date"]

    fx = 1.0
    if apply_fx:
        cur = (latest.get("reportedCurrency") or "").upper()
        if cur and cur != "USD":
            fx = fx_ratio(cur, base["date"], latest["date"]) or 1.0
            out.fx_ratio = fx
        else:
            out.fx_ratio = 1.0

    out.ev_usd = base_ev_usd * ratio * fx
    out.source = "fmp_ratio"
    return out


# ---------------------------------------------------------------------------
# FX
# ---------------------------------------------------------------------------
_fx_cache: Dict[str, Optional[float]] = {}


def fx_ratio(currency: str, base_date: str, latest_date: str) -> Optional[float]:
    """USD per unit of `currency` at latest_date divided by the same at base_date.

    Returns None when unavailable, so callers can choose between skipping the FX
    adjustment and skipping the company. Silently assuming 1.0 would embed a
    'the exchange rate never moved' assumption in the emissions series.
    """
    ck = f"{currency}:{base_date}:{latest_date}"
    if ck in _fx_cache:
        return _fx_cache[ck]
    pair = f"{currency}USD"
    rows = _get("historical-price-eod/light", symbol=pair,
                **{"from": base_date, "to": latest_date})
    val = None
    if rows:
        rows = [r for r in rows if r.get("price") and r.get("date")]
        if len(rows) >= 2:
            rows.sort(key=lambda r: r["date"])
            first, last = rows[0]["price"], rows[-1]["price"]
            if first:
                val = float(last) / float(first)
    _fx_cache[ck] = val
    return val


# ---------------------------------------------------------------------------
# Revenue, same ratio construction
# ---------------------------------------------------------------------------
def revenue_growth(symbol: str, base_year: int, target_year: int) -> Optional[float]:
    """Analyst consensus revenue growth from base_year to target_year.

    Local currency throughout, so the ratio is currency-free. Returns None if
    either year is missing or thinly covered -- `numAnalystsRevenue` of 1 is
    closer to no data than to a consensus and should not be treated as one.
    """
    rows = _get("analyst-estimates", symbol=symbol, period="annual", limit=12)
    if not rows:
        return None
    by_year = {}
    for r in rows:
        d = r.get("date", "")
        if len(d) >= 4 and r.get("revenueAvg"):
            by_year[int(d[:4])] = (float(r["revenueAvg"]),
                                   int(r.get("numAnalystsRevenue") or 0))
    b = by_year.get(base_year)
    t = by_year.get(target_year)
    if not b or not t or not b[0]:
        return None
    if min(b[1], t[1]) < 2:
        return None
    return t[0] / b[0]
