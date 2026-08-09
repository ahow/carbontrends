"""Streamlit-compatible message shim.

The model modules only ever used Streamlit for user-facing messages
(`st.error`, `st.warning`, `st.info`, `st.success`). Importing Streamlit for
that alone forced the FastAPI service to ship an entire UI framework, and the
container crashed on start when it was absent.

This module exposes the same four functions. Under Streamlit it delegates to
the real thing, so the dashboard behaves exactly as before. Anywhere else --
the API, the backtest harness, a notebook, a cron job -- it falls back to the
logging module. Import it as `st` to keep call sites unchanged:

    import ui_messages as st
"""
from __future__ import annotations

import logging

logger = logging.getLogger("carbontrends")

try:  # pragma: no cover - depends on the runtime, not on logic
    import streamlit as _st

    # Streamlit is importable even outside a script run, so check for a live
    # script context before delegating. Without this, calls made from the API
    # would emit "missing ScriptRunContext" warnings on every request.
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        def _active() -> bool:
            return get_script_run_ctx() is not None
    except Exception:
        def _active() -> bool:
            return True
except Exception:  # Streamlit not installed at all
    _st = None

    def _active() -> bool:
        return False


def _emit(level: int, kind: str, msg: str) -> None:
    if _st is not None and _active():
        getattr(_st, kind)(msg)
    else:
        logger.log(level, msg)


def error(msg: str) -> None:
    _emit(logging.ERROR, "error", msg)


def warning(msg: str) -> None:
    _emit(logging.WARNING, "warning", msg)


def info(msg: str) -> None:
    _emit(logging.INFO, "info", msg)


def success(msg: str) -> None:
    _emit(logging.INFO, "success", msg)
