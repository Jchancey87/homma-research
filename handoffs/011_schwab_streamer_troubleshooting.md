# Handoff: Schwab Streamer Troubleshooting & Current Status

## Overview
This handoff documents the troubleshooting process, code corrections, and authentication status for the `schwab-streamer` daemon, which was failing to run under PM2.

---

## 1. Accomplishments & Code Modifications

### A. Streamer Code Fixes (`stream_client.py`)
In `/opt/trading-journal/momentum_screener/schwab/stream_client.py` and the corresponding local file, we made several critical fixes:
1. **Method Renaming**: Changed outdated methods `level1_equity_subs` and `level1_equity_unsubs` to the correct `schwab-py` API names: `level_one_equity_subs` and `level_one_equity_unsubs`.
2. **Websocket Login Initialization**: Added `await self.stream_client.login()` to authenticate and establish the socket session before attempting to subscribe to symbols.
3. **Execution Loop Corrected**: Replaced the non-existent `run()` loop on `stream_client` with a continuous `while True: await self.stream_client.handle_message()` loop to process incoming web socket packets.

*Note: The production and local versions of `stream_client.py` are now fully in-sync.*

### B. Schwab API Scope Investigation
We wrote a test script (`scratch/test_schwab_client.py`) to isolate the `401 Unauthorized` token failures:
* **Market Data API (get_quote)**: Returns `200 OK` (fully functional).
* **Trader API (get_user_preferences)**: Returned `401 Client not authorized`.
* **Finding**: Even for non-trading use cases (streaming only), Schwab's API requires the **"Trader API - Accounts and Trading"** product to be linked to your Developer App. Without this, the library cannot fetch the credentials needed to open the Level 1 stream socket.

### C. Health Check & Notifications Deployed
Created and verified a health check script: [schwab_health_check.py](file:///home/jackc/projects/homma-research/backend/scripts/schwab_health_check.py) (copied to production at `/opt/trading-journal/backend/scripts/`).
* Tests both Market Data and Trader APIs.
* Automatically sends email notifications via Gmail SMTP to `jchancey87@gmail.com` if auth or access fails.
* **Cron Job Configured**: Scheduled a daily check for `jackc` running at 8:00 AM:
  ```text
  0 8 * * * /opt/trading-journal/backend/venv/bin/python /opt/trading-journal/backend/scripts/schwab_health_check.py > /dev/null 2>&1
  ```

---

## 2. Current State & Next Steps

### Status
1. **Developer Portal app modified**: The "Trader API - Accounts and Trading" product was successfully checked/added by the user. The app status displays as **"Ready for Use"**.
2. **Gateway Propagation Delay**: The authorization URL generated immediately after adding the product returned an `invalid_client` error. This is a known Schwab API behavior where credential syncing to their OAuth server takes 5–10 minutes.
3. **PM2 Service State**: The `schwab-streamer` daemon is currently halted/offline because it requires the refreshed token.

### Next Steps (For Tomorrow)
1. **Generate a New Authorization Link**:
   Run the manual auth script again to fetch a fresh token:
   ```bash
   /opt/trading-journal/backend/venv/bin/python schwab_auth_setup.py
   ```
2. **Authorize via Browser**:
   * Open the printed URL, log in to Schwab, approve app access, and copy the redirected URL (starts with `https://127.0.0.1/?code=...`).
   * Paste it back into the command line prompt to write the refreshed credentials to `/home/jackc/.config/schwab/token.json`.
3. **Verify the Streamer**:
   * Restart the PM2 daemon:
     ```bash
     echo "Lexus-Intent-7383" | sudo -S pm2 restart schwab-streamer
     ```
   * Tail the logs to confirm the websocket successfully connects and starts streaming without any 401s:
     ```bash
     echo "Lexus-Intent-7383" | sudo -S pm2 logs schwab-streamer --lines 30 --nostream
     ```
