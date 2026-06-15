"""
tests/test_alerts_telegram_format.py
------------------------------------
Golden-message snapshot tests for the Telegram alert formatter.

Drives the unified ALERT_TYPE_META template and verifies the Markdown
body for every supported alert_type, plus the fallback path. The
formatter is a pure function of ``alert_data`` so the whole suite runs
in <50ms with no DB or HTTP.
"""
from fastapi_app.tasks.alerts import (
    ALERT_TYPE_META,
    FALLBACK_META,
    _format_alert_message,
)


# ---------------------------------------------------------------------------
# Base payload — every test mutates one field at a time
# ---------------------------------------------------------------------------
BASE_PAYLOAD = {
    "symbol": "AAPL",
    "price": 150.25,
    "alert_type": "HOD_BREAKOUT",
    "rvol": 3.5,
    "time": "2026-06-14T14:30:00.000000",
    "daily_pct": 5.2,
    "candle_vol": 250_000,
    "avg_candle_vol": 100_000,
    "vwap": 148.0,
    "yesterday_high": 149.5,
    "float_category": "Mid",
    "market_cap": 2_500_000_000,
    "float_shares": 15_000_000_000,
}


# ---------------------------------------------------------------------------
# Header + signal-line correctness per alert type
# ---------------------------------------------------------------------------
def test_volatility_halt_header_and_static_signal():
    msg = _format_alert_message({**BASE_PAYLOAD, "alert_type": "VOLATILITY_HALT"})
    assert msg.startswith("⏸️ *VOLATILITY HALT* ⏸️\n\n")
    assert "- *Signal:* Volatility Halt (Status H)\n" in msg
    assert "*RVOL:*" not in msg  # halts/resumes intentionally omit RVOL
    assert "- *Ticker:* [$AAPL](https://www.tradingview.com/chart/?symbol=AAPL)" in msg
    assert "- *Price:* $150.25 (+5.2% day)" in msg
    assert msg.endswith("- *Time:* 2026-06-14 14:30:00")


def test_volatility_resume_header_and_static_signal():
    msg = _format_alert_message({**BASE_PAYLOAD, "alert_type": "VOLATILITY_RESUME"})
    assert msg.startswith("▶️ *VOLATILITY RESUME* ▶️\n\n")
    assert "- *Signal:* Volatility Resume (Status Active)\n" in msg
    assert "*RVOL:*" not in msg


def test_hod_breakout_full_enrichment():
    msg = _format_alert_message(BASE_PAYLOAD)
    assert "🏔️ *HOD BREAKOUT* 🏔️" in msg
    assert "- *RVOL:* 3.5x" in msg
    # _fmt_volume uses 1 decimal for M, no decimal for K (250K not 250.0K)
    assert "- *Candle vol:* 250K (2.5x avg 100K)" in msg
    assert "- *VWAP dist:* +1.5% (VWAP $148.00)" in msg
    assert "- *PDH dist:* +0.5% (PDH $149.50)" in msg
    # _fmt_float only formats in M units — 15B becomes 15000.0M
    assert "- *Float:* 15000.0M [Mid] | Cap: $2.5B" in msg
    # No Signal line for the rich path
    assert "- *Signal:*" not in msg


def test_volume_spike_omits_pdh_self_guarded():
    """yesterday_high=0 collapses the PDH line to empty — must not render."""
    msg = _format_alert_message(
        {**BASE_PAYLOAD, "alert_type": "VOLUME_SPIKE", "yesterday_high": 0.0}
    )
    assert "🔊 *VOLUME SPIKE* 🔊" in msg
    assert "*PDH dist:*" not in msg
    assert "- *VWAP dist:* +1.5% (VWAP $148.00)" in msg
    assert "- *RVOL:* 3.5x" in msg


def test_prev_day_breakout_renders_both_pdh_and_vwap():
    msg = _format_alert_message({**BASE_PAYLOAD, "alert_type": "PREV_DAY_BREAKOUT"})
    assert "🚀 *PREV DAY HIGH BREAKOUT* 🚀" in msg
    assert "*PDH dist:*" in msg
    assert "*VWAP dist:*" in msg
    # Standardized field order: VWAP before PDH (was PDH-first originally)
    vwap_idx = msg.index("*VWAP dist:*")
    pdh_idx = msg.index("*PDH dist:*")
    assert vwap_idx < pdh_idx


def test_vwap_crossover_renders_vwap_distance():
    msg = _format_alert_message({**BASE_PAYLOAD, "alert_type": "VWAP_CROSSOVER"})
    assert "🌊 *VWAP CROSSOVER* 🌊" in msg
    assert "- *VWAP dist:* +1.5% (VWAP $148.00)" in msg
    assert "- *RVOL:* 3.5x" in msg


def test_vwap_bounce_renders_vwap_distance():
    msg = _format_alert_message({**BASE_PAYLOAD, "alert_type": "VWAP_BOUNCE"})
    assert "📈 *VWAP SUPPORT BOUNCE* 📈" in msg
    assert "- *VWAP dist:* +1.5% (VWAP $148.00)" in msg
    assert "- *RVOL:* 3.5x" in msg


# ---------------------------------------------------------------------------
# Fallback path (unknown alert_type) — dynamic signal, markdown-escaped
# ---------------------------------------------------------------------------
def test_fallback_uses_dynamic_escaped_signal():
    msg = _format_alert_message(
        {**BASE_PAYLOAD, "alert_type": "HIGH_VOLUME_UP_BREAKOUT"}
    )
    assert "🚨 *BREAKOUT DETECTED* 🚨" in msg
    # Underscores in dynamic alert_type must be escaped
    assert "- *Signal:* HIGH\\_VOLUME\\_UP\\_BREAKOUT\n" in msg
    assert "- *RVOL:* 3.5x" in msg


def test_fallback_renders_known_payload_in_full():
    msg = _format_alert_message(
        {**BASE_PAYLOAD, "alert_type": "CUSTOM_xyz"}
    )
    # All standard context lines still render under the fallback header
    assert "🚨 *BREAKOUT DETECTED* 🚨" in msg
    assert "- *Ticker:* [$AAPL]" in msg
    assert "- *Candle vol:* 250K (2.5x avg 100K)" in msg
    assert "- *VWAP dist:* +1.5% (VWAP $148.00)" in msg
    assert "- *PDH dist:* +0.5% (PDH $149.50)" in msg
    assert "- *Float:* 15000.0M [Mid] | Cap: $2.5B" in msg
    assert msg.endswith("- *Time:* 2026-06-14 14:30:00")


# ---------------------------------------------------------------------------
# Edge cases — sign handling, missing data, special chars in symbol
# ---------------------------------------------------------------------------
def test_negative_daily_pct_drops_plus_sign():
    msg = _format_alert_message(
        {**BASE_PAYLOAD, "alert_type": "VOLUME_SPIKE", "daily_pct": -3.4}
    )
    assert "- *Price:* $150.25 (-3.4% day)" in msg


def test_zero_daily_pct_gets_plus_sign():
    """Per the formatter contract, daily_pct >= 0 always gets a '+' prefix."""
    msg = _format_alert_message(
        {**BASE_PAYLOAD, "alert_type": "VOLUME_SPIKE", "daily_pct": 0.0}
    )
    assert "- *Price:* $150.25 (+0.0% day)" in msg


def test_all_optional_fields_absent_renders_compact_body():
    """Zero values + empty strings collapse every optional line."""
    payload = {
        "symbol": "X",
        "price": 1.0,
        "alert_type": "HOD_BREAKOUT",
        "rvol": 2.0,
        "time": "2026-06-14T09:30:00",
        "daily_pct": 1.0,
    }
    msg = _format_alert_message(payload)
    assert "- *RVOL:* 2.0x" in msg
    assert "*Candle vol:*" not in msg
    assert "*VWAP dist:*" not in msg
    assert "*PDH dist:*" not in msg
    assert "*Float:*" not in msg
    assert "*Signal:*" not in msg
    assert msg.endswith("- *Time:* 2026-06-14 09:30:00")


def test_invalid_timestamp_falls_back_to_raw_string():
    """Bad ISO strings render as-is (no crash, no exception)."""
    msg = _format_alert_message(
        {**BASE_PAYLOAD, "alert_type": "HOD_BREAKOUT", "time": "not-a-date"}
    )
    assert "- *Time:* not-a-date" in msg


def test_tradingview_url_uses_raw_unscaped_symbol():
    """The TV URL never escapes — only the Markdown label does."""
    msg = _format_alert_message(BASE_PAYLOAD)
    assert "https://www.tradingview.com/chart/?symbol=AAPL" in msg


def test_ticker_with_underscore_escaped_in_label_only():
    """Underscores in symbol get escaped in the visible label, not the URL."""
    msg = _format_alert_message(
        {**BASE_PAYLOAD, "symbol": "BRK_A", "alert_type": "HOD_BREAKOUT"}
    )
    assert "[$BRK\\_A]" in msg
    assert "https://www.tradingview.com/chart/?symbol=BRK_A" in msg


def test_float_only_category_no_shares():
    """float_category alone (no float_shares, no market_cap) still renders."""
    msg = _format_alert_message(
        {
            **BASE_PAYLOAD,
            "alert_type": "HOD_BREAKOUT",
            "float_shares": 0,
            "market_cap": 0,
            "float_category": "Low",
        }
    )
    assert "- *Float:* N/A [Low]\n" in msg


def test_float_only_shares_no_category_no_cap():
    """float_shares alone (no category, no cap) renders just the share count."""
    msg = _format_alert_message(
        {
            **BASE_PAYLOAD,
            "alert_type": "HOD_BREAKOUT",
            "float_shares": 5_000_000,
            "market_cap": 0,
            "float_category": "",
        }
    )
    assert "- *Float:* 5.0M\n" in msg


# ---------------------------------------------------------------------------
# META table contract — guards against silent additions/removals
# ---------------------------------------------------------------------------
def test_meta_dict_covers_all_documented_types():
    expected = {
        "VOLATILITY_HALT", "VOLATILITY_RESUME",
        "HOD_BREAKOUT", "VOLUME_SPIKE", "PREV_DAY_BREAKOUT",
        "VWAP_CROSSOVER", "VWAP_BOUNCE",
    }
    assert set(ALERT_TYPE_META.keys()) == expected
    for name, meta in ALERT_TYPE_META.items():
        assert "emoji" in meta and meta["emoji"], f"{name} missing emoji"
        assert "header" in meta and meta["header"], f"{name} missing header"
        assert "signal" in meta, f"{name} missing signal key"
        assert "show_rvol" in meta, f"{name} missing show_rvol key"
        assert isinstance(meta["show_rvol"], bool)


def test_fallback_meta_uses_auto_signal():
    assert FALLBACK_META["emoji"] == "🚨"
    assert FALLBACK_META["header"] == "BREAKOUT DETECTED"
    assert FALLBACK_META["signal"] == "auto"
    assert FALLBACK_META["show_rvol"] is True
