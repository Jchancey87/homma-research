import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.fmp_service import (
    get_company_profile,
    get_earnings_calendar,
    get_income_statement,
    get_key_metrics,
    get_cash_position,
    get_insider_transactions,
    get_institutional_holders,
    get_stock_news
)

def test_ticker(ticker):
    print(f"\n================ TEST {ticker} ================")
    
    print("\n--- Company Profile ---")
    try:
        profile = get_company_profile(ticker)
        print("Profile Keys:", list(profile.keys()))
        print(f"Sector: {profile.get('sector')}, Float Shares: {profile.get('float_shares')}, Shares Out: {profile.get('shares_outstanding')}")
    except Exception as e:
        print("Profile Error:", e)
        
    print("\n--- Earnings Calendar ---")
    try:
        earnings = get_earnings_calendar(ticker)
        print("Earnings Keys:", list(earnings.keys()))
        print(f"Next Date: {earnings.get('next_earnings_date')}, Status: {earnings.get('next_earnings_status')}")
    except Exception as e:
        print("Earnings Error:", e)

    print("\n--- Income Statement ---")
    try:
        income = get_income_statement(ticker, quarters=1)
        if income:
            print("Income Keys:", list(income[0].keys()))
            print(f"Revenue: {income[0].get('revenue')}, Net Income: {income[0].get('net_income')}, Diluted EPS: {income[0].get('eps_diluted')}")
        else:
            print("No Income Statement returned.")
    except Exception as e:
        print("Income Error:", e)

    print("\n--- Key Metrics ---")
    try:
        metrics = get_key_metrics(ticker)
        print("Metrics Keys:", list(metrics.keys()))
        print(f"P/E Ratio: {metrics.get('pe_ratio_ttm')}, P/B Ratio: {metrics.get('pb_ratio_ttm')}, Debt to Equity: {metrics.get('debt_to_equity_ttm')}")
    except Exception as e:
        print("Metrics Error:", e)

    print("\n--- Cash Position ---")
    try:
        cash = get_cash_position(ticker)
        print("Cash Keys:", list(cash.keys()))
        print(f"Cash: {cash.get('cash')}, Period: {cash.get('period')}")
    except Exception as e:
        print("Cash Error:", e)

    print("\n--- Insider Transactions ---")
    try:
        insider = get_insider_transactions(ticker)
        print("Insider Keys:", list(insider.keys()))
        print(f"Net Shares: {insider.get('net_shares')}, Transactions Count: {len(insider.get('transactions', []))}")
    except Exception as e:
        print("Insider Error:", e)

    print("\n--- Institutional Holders ---")
    try:
        holders = get_institutional_holders(ticker)
        print(f"Holders Count: {len(holders)}")
        if holders:
            print("First Holder Keys:", list(holders[0].keys()))
    except Exception as e:
        print("Holders Error:", e)

    print("\n--- Stock News ---")
    try:
        news = get_stock_news(ticker, limit=2)
        print(f"News Count: {len(news)}")
        if news:
            print("First News Keys:", list(news[0].keys()))
    except Exception as e:
        print("News Error:", e)

if __name__ == '__main__':
    test_ticker('AAPL')
