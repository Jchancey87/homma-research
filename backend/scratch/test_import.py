import sys
import os

# Ensure backend/ and repo root are in sys.path
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, _BACKEND_DIR)

def test_imports():
    try:
        print("\nAttempting to import services.fmp_service...")
        from services.fmp_service import (
            get_company_profile, get_analyst_estimates, get_income_statement,
            get_key_metrics, get_earnings_calendar,
            get_cash_position, get_insider_transactions, get_institutional_holders,
            get_stock_news,
        )
        print("Import of services.fmp_service succeeded!")
    except Exception as e:
        import traceback
        print(f"IMPORT FAILED: {e}")
        print(traceback.format_exc())
    
    try:
        print("\nAttempting to import from llm_tasks...")
        from fastapi_app.tasks.llm_tasks import run_deep_research
        print("Import of run_deep_research succeeded!")
    except Exception as e:
        import traceback
        print(f"IMPORT FAILED: {e}")
        print(traceback.format_exc())
        
    assert True
