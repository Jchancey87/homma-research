import pytest
from unittest.mock import AsyncMock
from services.sector_strength_service import (
    build_sector_strength,
    market_tone_label,
    SECTOR_ETFS,
)
from services.live_quotes_service import NormalizedQuote

def test_market_tone_label():
    assert market_tone_label(7, 2, 11) == "bullish"
    assert market_tone_label(1, 7, 11) == "bearish"
    assert market_tone_label(4, 4, 11) == "rotation"
    assert market_tone_label(3, 3, 11) == "mixed"

@pytest.mark.asyncio
async def test_build_sector_strength():
    mock_quotes_fn = AsyncMock(return_value={
        "SPY": NormalizedQuote(ticker="SPY", last_price=500.0, change_pct=1.0, source="schwab"),
        "XLK": NormalizedQuote(ticker="XLK", last_price=200.0, change_pct=2.0, source="schwab"),  # RS +1.0 (leading)
        "XLV": NormalizedQuote(ticker="XLV", last_price=150.0, change_pct=0.5, source="schwab"),  # RS -0.5 (lagging)
        "XLF": NormalizedQuote(ticker="XLF", last_price=40.0, change_pct=1.1, source="schwab"),   # RS +0.1 (inline)
    })

    res = await build_sector_strength(mock_quotes_fn)
    assert res["spy"]["price"] == 500.0
    assert res["spy"]["chg_pct"] == 1.0
    assert len(res["sectors"]) == 3  # XLK, XLV, XLF provided
    
    xlk = next(s for s in res["sectors"] if s["etf"] == "XLK")
    assert xlk["rs_vs_spy"] == 1.0
    assert xlk["status"] == "leading"

    xlv = next(s for s in res["sectors"] if s["etf"] == "XLV")
    assert xlv["rs_vs_spy"] == -0.5
    assert xlv["status"] == "lagging"

    xlf = next(s for s in res["sectors"] if s["etf"] == "XLF")
    assert xlf["rs_vs_spy"] == 0.1
    assert xlf["status"] == "inline"
