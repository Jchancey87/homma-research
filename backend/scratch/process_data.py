import json
import datetime
import pandas as pd
import numpy as np

snapshot_path = '/home/jackc/projects/homma-research/backend/scratch/recap_data_snapshot.json'
output_path = '/home/jackc/projects/homma-research/backend/scratch/processed_metrics.json'

with open(snapshot_path, 'r') as f:
    data = json.load(f)

processed = {}

# Time helpers
# The timestamp in minute_candles is milliseconds since epoch.
# We need to parse and categorize into:
# Premarket: 4:00 AM - 9:30 AM EST (04:00 - 09:30 EST)
# Regular: 9:30 AM - 4:00 PM EST (09:30 - 16:00 EST)
# Postmarket: 4:00 PM - 8:00 PM EST (16:00 - 20:00 EST)

def parse_time(ts_ms):
    # Convert to EST/EDT (America/New_York)
    dt = datetime.datetime.fromtimestamp(ts_ms / 1000.0, tz=datetime.timezone.utc)
    est = dt.astimezone(datetime.timezone(datetime.timedelta(hours=-4))) # EDT is UTC-4 in May
    return est

for ticker, content in data.items():
    processed[ticker] = {}
    
    # 1. Basics
    fundamentals = content.get('schwab_fundamental', {})
    quote = content.get('schwab_quote', {})
    description = content.get('description', '')
    exchange = content.get('exchange', '')
    
    processed[ticker]['description'] = description
    processed[ticker]['exchange'] = exchange
    processed[ticker]['float'] = fundamentals.get('marketCapFloat')
    processed[ticker]['shares_outstanding'] = fundamentals.get('sharesOutstanding')
    processed[ticker]['market_cap'] = fundamentals.get('marketCap')
    processed[ticker]['short_int_float'] = fundamentals.get('shortIntToFloat')
    processed[ticker]['short_days_cover'] = fundamentals.get('shortIntDayToCover')
    processed[ticker]['avg_10d_vol'] = fundamentals.get('avg10DaysVolume')
    processed[ticker]['avg_3m_vol'] = fundamentals.get('avg3MonthVolume')
    
    # 2. Intraday Analysis (Minute Candles)
    min_candles = content.get('minute_candles', [])
    if isinstance(min_candles, str): # Error message
        min_candles = []
        
    df_min = pd.DataFrame(min_candles)
    if not df_min.empty:
        df_min['dt'] = df_min['datetime'].apply(parse_time)
        df_min['hour_min'] = df_min['dt'].dt.strftime('%H:%M')
        
        # Categorize sessions
        # Premarket: time < 09:30
        # Regular: 09:30 <= time <= 16:00
        # Postmarket: time > 16:00
        pre_df = df_min[df_min['dt'].dt.time < datetime.time(9, 30)]
        reg_df = df_min[(df_min['dt'].dt.time >= datetime.time(9, 30)) & (df_min['dt'].dt.time <= datetime.time(16, 0))]
        post_df = df_min[df_min['dt'].dt.time > datetime.time(16, 0)]
        
        # Premarket Stats
        if not pre_df.empty:
            processed[ticker]['premarket_high'] = float(pre_df['high'].max())
            processed[ticker]['premarket_low'] = float(pre_df['low'].min())
            processed[ticker]['premarket_volume'] = int(pre_df['volume'].sum())
        else:
            processed[ticker]['premarket_high'] = None
            processed[ticker]['premarket_low'] = None
            processed[ticker]['premarket_volume'] = 0
            
        # Regular Session Stats
        if not reg_df.empty:
            processed[ticker]['open'] = float(reg_df.iloc[0]['open'])
            processed[ticker]['high'] = float(reg_df['high'].max())
            processed[ticker]['low'] = float(reg_df['low'].min())
            processed[ticker]['close'] = float(reg_df.iloc[-1]['close'])
            processed[ticker]['volume'] = int(reg_df['volume'].sum())
            
            # Dollar volume: sum(close * volume) for each 1-min bar
            processed[ticker]['dollar_volume'] = float((reg_df['close'] * reg_df['volume']).sum())
            
            # VWAP = sum(typical_price * volume) / sum(volume)
            reg_df['typical_price'] = (reg_df['high'] + reg_df['low'] + reg_df['close']) / 3
            total_vp = (reg_df['typical_price'] * reg_df['volume']).sum()
            total_v = reg_df['volume'].sum()
            vwap_val = total_vp / total_v if total_v > 0 else None
            processed[ticker]['vwap'] = float(vwap_val) if vwap_val else None
            
            # VWAP relationship: percentage of time price closed above VWAP
            if vwap_val:
                above_vwap_count = (reg_df['close'] > vwap_val).sum()
                processed[ticker]['pct_above_vwap'] = float(above_vwap_count / len(reg_df))
            else:
                processed[ticker]['pct_above_vwap'] = None
                
            # Close position in range
            high_val = reg_df['high'].max()
            low_val = reg_df['low'].min()
            close_val = reg_df.iloc[-1]['close']
            if high_val > low_val:
                processed[ticker]['range_location'] = float((close_val - low_val) / (high_val - low_val))
            else:
                processed[ticker]['range_location'] = 1.0
        else:
            processed[ticker]['open'] = None
            processed[ticker]['high'] = None
            processed[ticker]['low'] = None
            processed[ticker]['close'] = None
            processed[ticker]['volume'] = 0
            processed[ticker]['dollar_volume'] = 0.0
            processed[ticker]['vwap'] = None
            processed[ticker]['pct_above_vwap'] = None
            processed[ticker]['range_location'] = None
            
        # Total daily volume (including extended hours)
        processed[ticker]['total_volume'] = int(df_min['volume'].sum())
        processed[ticker]['total_dollar_volume'] = float((df_min['close'] * df_min['volume']).sum())
        
    else:
        processed[ticker]['total_volume'] = 0
        processed[ticker]['total_dollar_volume'] = 0.0
        
    # 3. Daily technicals and ATR
    daily_candles = content.get('daily_candles', [])
    if isinstance(daily_candles, str):
        daily_candles = []
        
    df_daily = pd.DataFrame(daily_candles)
    if not df_daily.empty:
        # Calculate ATR(14)
        # TR = max(high - low, abs(high - prev_close), abs(low - prev_close))
        df_daily['prev_close'] = df_daily['close'].shift(1)
        df_daily['h_l'] = df_daily['high'] - df_daily['low']
        df_daily['h_pc'] = (df_daily['high'] - df_daily['prev_close']).abs()
        df_daily['l_pc'] = (df_daily['low'] - df_daily['prev_close']).abs()
        df_daily['tr'] = df_daily[['h_l', 'h_pc', 'l_pc']].max(axis=1)
        
        # 14-day SMA of TR
        df_daily['atr_14'] = df_daily['tr'].rolling(window=14).mean()
        
        # 20 and 50 SMAs of Close
        df_daily['sma_20'] = df_daily['close'].rolling(window=20).mean()
        df_daily['sma_50'] = df_daily['close'].rolling(window=50).mean()
        
        latest = df_daily.iloc[-1]
        processed[ticker]['atr_14'] = float(latest['atr_14']) if not pd.isna(latest['atr_14']) else None
        processed[ticker]['sma_20'] = float(latest['sma_20']) if not pd.isna(latest['sma_20']) else None
        processed[ticker]['sma_50'] = float(latest['sma_50']) if not pd.isna(latest['sma_50']) else None
        
        # Position relative to SMA
        processed[ticker]['prev_close'] = float(df_daily.iloc[-2]['close']) if len(df_daily) >= 2 else None
    else:
        processed[ticker]['atr_14'] = None
        processed[ticker]['sma_20'] = None
        processed[ticker]['sma_50'] = None
        processed[ticker]['prev_close'] = None
        
    # 4. YFinance Metrics
    yf_data = content.get('yfinance', {})
    processed[ticker]['cash'] = yf_data.get('cash')
    processed[ticker]['net_income'] = yf_data.get('net_income')
    processed[ticker]['operating_cash_flow'] = yf_data.get('operating_cash_flow')
    processed[ticker]['shares_history'] = yf_data.get('shares_history', {})
    processed[ticker]['calendar'] = yf_data.get('calendar')
    
    # News
    processed[ticker]['news'] = yf_data.get('news', [])

# Write processed results
with open(output_path, 'w') as f:
    json.dump(processed, f, indent=2)

print("Metrics processed successfully!")
