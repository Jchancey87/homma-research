import sys
import os
import yfinance as yf

ticker = "AAPL"
t = yf.Ticker(ticker)

print("Balance Sheet:")
try:
    print(t.quarterly_balance_sheet.index.tolist())
except Exception as e:
    print("Error:", e)

print("\nFinancials:")
try:
    print(t.quarterly_financials.index.tolist())
except Exception as e:
    print("Error:", e)

print("\nCash Flow:")
try:
    print(t.quarterly_cashflow.index.tolist())
except Exception as e:
    print("Error:", e)
