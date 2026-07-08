import pytest
from datetime import datetime
from validation import EASTERN_TZ
from momentum_screener.schwab.stream_client import SchwabStreamer

def test_calculate_confluence_score_watchlist_bonus():
    """Test watchlist presence bonus (+20) and no bonus (+0)."""
    streamer = SchwabStreamer()
    streamer.watchlist_symbols = {"AAPL"}
    streamer.catalyst_tags = {}
    streamer.fundamentals_cache = {}
    
    # Base: watchlist=20, regular session=15, HOD_BREAKOUT=15, rvol=0 -> 50 (Tier 2)
    now_et = datetime.now(EASTERN_TZ).replace(hour=10, minute=0, second=0, microsecond=0)
    score_wl, tier_wl = streamer.calculate_confluence_score("AAPL", "HOD_BREAKOUT", rvol=0.0, now_et=now_et)
    assert score_wl == 50
    assert tier_wl == "Tier 2"
    
    # Base without watchlist: watchlist=0, regular session=15, HOD_BREAKOUT=15, rvol=0 -> 30 (Tier 3)
    score_no, tier_no = streamer.calculate_confluence_score("MSFT", "HOD_BREAKOUT", rvol=0.0, now_et=now_et)
    assert score_no == 30
    assert tier_no == "Tier 3"


def test_calculate_confluence_score_catalyst_tags():
    """Test different catalyst tag scores: Confirmed (+25), Speculative (+15), Technical (+10), none (+0)."""
    streamer = SchwabStreamer()
    streamer.watchlist_symbols = set()
    streamer.fundamentals_cache = {}
    now_et = datetime.now(EASTERN_TZ).replace(hour=10, minute=0, second=0, microsecond=0)
    
    # Confirmed Catalyst: catalyst=25, regular session=15, HOD_BREAKOUT=15 -> 55
    streamer.catalyst_tags = {"AAPL": "Confirmed Catalyst"}
    score, _ = streamer.calculate_confluence_score("AAPL", "HOD_BREAKOUT", rvol=0.0, now_et=now_et)
    assert score == 55
    
    # Speculative: catalyst=15, regular session=15, HOD_BREAKOUT=15 -> 45
    streamer.catalyst_tags = {"AAPL": "Speculative"}
    score, _ = streamer.calculate_confluence_score("AAPL", "HOD_BREAKOUT", rvol=0.0, now_et=now_et)
    assert score == 45
    
    # Technical / No News: catalyst=10, regular session=15, HOD_BREAKOUT=15 -> 40
    streamer.catalyst_tags = {"AAPL": "Technical / No News"}
    score, _ = streamer.calculate_confluence_score("AAPL", "HOD_BREAKOUT", rvol=0.0, now_et=now_et)
    assert score == 40
    
    # None: catalyst=0, regular session=15, HOD_BREAKOUT=15 -> 30
    streamer.catalyst_tags = {}
    score, _ = streamer.calculate_confluence_score("AAPL", "HOD_BREAKOUT", rvol=0.0, now_et=now_et)
    assert score == 30


def test_calculate_confluence_score_float_categories():
    """Test float category scores: Micro (+20), Low (+15), Mid (+10), unknown (+0)."""
    streamer = SchwabStreamer()
    streamer.watchlist_symbols = set()
    streamer.catalyst_tags = {}
    now_et = datetime.now(EASTERN_TZ).replace(hour=10, minute=0, second=0, microsecond=0)
    
    # Micro-Float: float=20, session=15, HOD_BREAKOUT=15 -> 50
    streamer.fundamentals_cache = {"AAPL": {"float_category": "Micro-Float"}}
    score, _ = streamer.calculate_confluence_score("AAPL", "HOD_BREAKOUT", rvol=0.0, now_et=now_et)
    assert score == 50
    
    # Low-Float: float=15, session=15, HOD_BREAKOUT=15 -> 45
    streamer.fundamentals_cache = {"AAPL": {"float_category": "Low-Float"}}
    score, _ = streamer.calculate_confluence_score("AAPL", "HOD_BREAKOUT", rvol=0.0, now_et=now_et)
    assert score == 45
    
    # Mid-Float: float=10, session=15, HOD_BREAKOUT=15 -> 40
    streamer.fundamentals_cache = {"AAPL": {"float_category": "Mid-Float"}}
    score, _ = streamer.calculate_confluence_score("AAPL", "HOD_BREAKOUT", rvol=0.0, now_et=now_et)
    assert score == 40
    
    # Unknown: float=0, session=15, HOD_BREAKOUT=15 -> 30
    streamer.fundamentals_cache = {"AAPL": {"float_category": "Unknown"}}
    score, _ = streamer.calculate_confluence_score("AAPL", "HOD_BREAKOUT", rvol=0.0, now_et=now_et)
    assert score == 30


def test_calculate_confluence_score_market_sessions():
    """Test market session scores: Regular (+15), Pre (+10), Post (+5)."""
    streamer = SchwabStreamer()
    streamer.watchlist_symbols = set()
    streamer.catalyst_tags = {}
    streamer.fundamentals_cache = {}
    
    # Regular Session: 10:00 AM -> session=15, HOD_BREAKOUT=15 -> 30
    now_et = datetime.now(EASTERN_TZ).replace(hour=10, minute=0, second=0, microsecond=0)
    score, _ = streamer.calculate_confluence_score("AAPL", "HOD_BREAKOUT", rvol=0.0, now_et=now_et)
    assert score == 30
    
    # Pre-market: 8:00 AM -> session=10, HOD_BREAKOUT=15 -> 25
    now_et = datetime.now(EASTERN_TZ).replace(hour=8, minute=0, second=0, microsecond=0)
    score, _ = streamer.calculate_confluence_score("AAPL", "HOD_BREAKOUT", rvol=0.0, now_et=now_et)
    assert score == 25
    
    # Post-market: 5:00 PM -> session=5, HOD_BREAKOUT=15 -> 20
    now_et = datetime.now(EASTERN_TZ).replace(hour=17, minute=0, second=0, microsecond=0)
    score, _ = streamer.calculate_confluence_score("AAPL", "HOD_BREAKOUT", rvol=0.0, now_et=now_et)
    assert score == 20


def test_calculate_confluence_score_alert_weights():
    """Test alert type weight: High (+15), Med (+10), Low (+5)."""
    streamer = SchwabStreamer()
    streamer.watchlist_symbols = set()
    streamer.catalyst_tags = {}
    streamer.fundamentals_cache = {}
    now_et = datetime.now(EASTERN_TZ).replace(hour=10, minute=0, second=0, microsecond=0)
    
    # High: HOD_BREAKOUT, VWAP_CROSSOVER, PREV_DAY_BREAKOUT, RUNNING_UP, BULL_FLAG, VWAP_RECLAIM -> +15
    for at in ('HOD_BREAKOUT', 'VWAP_CROSSOVER', 'PREV_DAY_BREAKOUT', 'RUNNING_UP', 'BULL_FLAG', 'VWAP_RECLAIM'):
        score, _ = streamer.calculate_confluence_score("AAPL", at, rvol=0.0, now_et=now_et)
        assert score == 30, f"Failed for {at}"
        
    # Med: VOLUME_SPIKE, MULTI_TF_CONFLUENCE -> +10
    for at in ('VOLUME_SPIKE', 'MULTI_TF_CONFLUENCE'):
        score, _ = streamer.calculate_confluence_score("AAPL", at, rvol=0.0, now_et=now_et)
        assert score == 25, f"Failed for {at}"
        
    # Low: VOLATILITY_HALT, VOLATILITY_RESUME, HALT_RESUME_MOMENTUM -> +5
    for at in ('VOLATILITY_HALT', 'VOLATILITY_RESUME', 'HALT_RESUME_MOMENTUM'):
        score, _ = streamer.calculate_confluence_score("AAPL", at, rvol=0.0, now_et=now_et)
        assert score == 20, f"Failed for {at}"


def test_calculate_confluence_score_rvol_levels():
    """Test RVOL scores: >=5 (+15), >=3 (+10), >=1.5 (+5), <1.5 (+0)."""
    streamer = SchwabStreamer()
    streamer.watchlist_symbols = set()
    streamer.catalyst_tags = {}
    streamer.fundamentals_cache = {}
    now_et = datetime.now(EASTERN_TZ).replace(hour=10, minute=0, second=0, microsecond=0)
    
    # rvol >= 5.0 -> +15 -> 45
    score, _ = streamer.calculate_confluence_score("AAPL", "HOD_BREAKOUT", rvol=5.0, now_et=now_et)
    assert score == 45
    
    # rvol >= 3.0 -> +10 -> 40
    score, _ = streamer.calculate_confluence_score("AAPL", "HOD_BREAKOUT", rvol=3.0, now_et=now_et)
    assert score == 40
    
    # rvol >= 1.5 -> +5 -> 35
    score, _ = streamer.calculate_confluence_score("AAPL", "HOD_BREAKOUT", rvol=1.5, now_et=now_et)
    assert score == 35
    
    # rvol < 1.5 -> +0 -> 30
    score, _ = streamer.calculate_confluence_score("AAPL", "HOD_BREAKOUT", rvol=1.0, now_et=now_et)
    assert score == 30


def test_calculate_confluence_score_tier_assignments():
    """Test Tier assignments: Tier 1 (>=75), Tier 2 (>=45), Tier 3 (<45)."""
    streamer = SchwabStreamer()
    streamer.watchlist_symbols = {"AAPL"}  # +20
    streamer.catalyst_tags = {"AAPL": "Confirmed Catalyst"}  # +25
    streamer.fundamentals_cache = {"AAPL": {"float_category": "Micro-Float"}}  # +20
    # Current accumulated: 65
    
    now_et = datetime.now(EASTERN_TZ).replace(hour=10, minute=0, second=0, microsecond=0) # Regular session (+15) -> 80
    
    # Tier 1 (score = 80 + 15 + 15 = 110)
    score1, tier1 = streamer.calculate_confluence_score("AAPL", "HOD_BREAKOUT", rvol=5.0, now_et=now_et)
    assert score1 >= 75
    assert tier1 == "Tier 1"
    
    # Tier 2 (score = 20 + 0 + 15 [low-float] + 15 [session] + 10 [spike] + 5 [rvol=1.5] = 65)
    streamer.watchlist_symbols = {"AAPL"}
    streamer.catalyst_tags = {}
    streamer.fundamentals_cache = {"AAPL": {"float_category": "Low-Float"}}
    score2, tier2 = streamer.calculate_confluence_score("AAPL", "VOLUME_SPIKE", rvol=1.5, now_et=now_et)
    assert 45 <= score2 < 75
    assert tier2 == "Tier 2"
    
    # Tier 3 (score = 0 + 0 + 0 + 15 [session] + 15 [hod] + 0 = 30)
    streamer.watchlist_symbols = set()
    streamer.catalyst_tags = {}
    streamer.fundamentals_cache = {}
    score3, tier3 = streamer.calculate_confluence_score("AAPL", "HOD_BREAKOUT", rvol=1.0, now_et=now_et)
    assert score3 < 45
    assert tier3 == "Tier 3"
