"""Model variant definitions shared by the API and the dashboard.

Each variant is a named, self-describing configuration of the estimator so the
dashboard can show the effect of a modelling change rather than asserting it.
Keep the descriptions honest -- they are rendered directly in the UI.
"""

VARIANTS = {
    "legacy": {
        "id": "legacy",
        "label": "Legacy",
        "short": "Pre-fix baseline",
        "description": (
            "Forward estimates capped around the retained regime median, and the "
            "sales fallback restricted to years with both carbon and sales. This "
            "is the model as it stood before the August 2026 review."
        ),
        "caveat": (
            "For 17.7% of companies the median floor sits above the last reported "
            "intensity, so the fastest decarbonisers are pushed back up."
        ),
        "params": {"cap_mode": "median", "drift_offset": 0.0, "sales_mode": "joint"},
    },
    "current": {
        "id": "current",
        "label": "Current",
        "short": "Anchored cap + latest sales",
        "description": (
            "Forward estimates capped around the last observed value rather than "
            "the regime median, and the sales fallback reads the most recent year "
            "with actual revenue."
        ),
        "caveat": (
            "Removes the mechanical distortion but still has no view that "
            "intensities trend down, so it reads high at long horizons."
        ),
        "params": {"cap_mode": "anchor", "drift_offset": 0.0, "sales_mode": "latest"},
    },
    "drift": {
        "id": "drift",
        "label": "Drift-corrected",
        "short": "Current + calibrated drift",
        "description": (
            "As Current, plus a calibrated downward drift of 4.5% per year of "
            "horizon, which is the median rate at which company intensities "
            "actually fall in this dataset."
        ),
        "caveat": (
            "The drift term is fitted on the backtest and must be recalibrated "
            "whenever the data is refreshed. Treat it as a parameter, not a "
            "constant."
        ),
        "params": {"cap_mode": "anchor", "drift_offset": 0.045, "sales_mode": "latest"},
    },
}

DEFAULT_VARIANT = "current"


def params_for(variant_id: str) -> dict:
    v = VARIANTS.get(variant_id or DEFAULT_VARIANT) or VARIANTS[DEFAULT_VARIANT]
    return dict(v["params"])
