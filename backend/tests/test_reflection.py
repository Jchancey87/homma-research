import pytest
import json
from unittest.mock import patch, MagicMock
from database import get_connection
from llm.llm_client import get_reflection
from jobs.reflect_picks import main as reflect_picks_main
from jobs.daily_analysis_report import fetch_last_reflections

# Helper to clean up any test records
def cleanup_test_data(date_str):
    with get_connection() as conn:
        conn.execute("DELETE FROM continuation_reflections WHERE date = %s", (date_str,))
        conn.execute("DELETE FROM continuation_picks WHERE date = %s", (date_str,))

def test_fetch_last_reflections_empty():
    # Make sure we can handle empty reflections log gracefully
    cleanup_test_data("2020-01-01")
    cleanup_test_data("2020-01-02")
    cleanup_test_data("2020-01-03")
    
    reflections = fetch_last_reflections(limit=3)
    assert isinstance(reflections, list)

def test_reflect_picks_no_data():
    test_date = "2050-12-31"
    cleanup_test_data(test_date)
    
    with patch("jobs.reflect_picks.get_reflection") as mock_get_ref:
        with patch("sys.argv", ["reflect_picks.py", "--date", test_date]):
            reflect_picks_main()
        mock_get_ref.assert_not_called()
        
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM continuation_reflections WHERE date = %s", (test_date,)).fetchone()
        assert row is None

def test_db_writes_and_retrieval():
    test_date = "2050-01-01"
    cleanup_test_data(test_date)
    
    # 1. Insert mock continuation picks with outcomes (d1_close is not null)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO continuation_picks (ticker, date, reason, gap_pct, float_shares, rvol_15m, sector, rank, d1_close)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            ("FAKE", test_date, "Some thesis", 35.5, 5000000.0, 6.2, "Technology", 1, 10.5)
        )
        
    # 2. Mock LLM call to get_reflection
    mock_reflection_text = "Today's performance was great. TSTT hit target."
    mock_lessons = {"avoid_sectors": ["Healthcare"], "max_float": 8000000}
    
    with patch("jobs.reflect_picks.get_reflection", return_value=(mock_reflection_text, mock_lessons)) as mock_get_ref:
        # Run reflect_picks job main for target date
        with patch("sys.argv", ["reflect_picks.py", "--date", test_date]):
            reflect_picks_main()
            
        mock_get_ref.assert_called_once()
        
    # 3. Assert DB writes
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM continuation_reflections WHERE date = %s", (test_date,)).fetchone()
        assert row is not None
        assert row["reflection_text"] == mock_reflection_text
        lessons = row["lessons_json"]
        if isinstance(lessons, str):
            lessons = json.loads(lessons)
        assert lessons["avoid_sectors"] == ["Healthcare"]
        assert lessons["max_float"] == 8000000

    # Cleanup
    cleanup_test_data(test_date)

def test_retrieve_last_3_reflections():
    dates = ["2050-01-01", "2050-01-02", "2050-01-03", "2050-01-04"]
    for d in dates:
        cleanup_test_data(d)
        
    try:
        with get_connection() as conn:
            for idx, d in enumerate(dates, start=1):
                conn.execute(
                    """
                    INSERT INTO continuation_reflections (date, reflection_text, lessons_json)
                    VALUES (%s, %s, %s::jsonb)
                    """,
                    (d, f"Reflect {d}", json.dumps({"avoid_sectors": [f"Sector{idx}"], "max_float": idx * 1000000}))
                )
                
        # Retrieve last 3
        reflections = fetch_last_reflections(limit=3)
        
        # Since these are in 2050, they will be the top 3
        assert len(reflections) >= 3
        retrieved_dates = [str(r["date"]) for r in reflections[:3]]
        assert retrieved_dates == ["2050-01-04", "2050-01-03", "2050-01-02"]
    finally:
        for d in dates:
            cleanup_test_data(d)
