# Webpage Troubleshooting: CORS, Path Imports, and Schwab Auth Handoff 🚀

This document outlines the troubleshooting actions taken, the status of the fixes, and the remaining action required to get the Schwab data ingestion fully working on the frontend.

---

## 📋 Status Summary

We identified and resolved three main issues that were blocking the FastAPI backend and Celery workers, and we prepared the final interactive Schwab authentication step.

1. **CORS Wildcard with Credentials Block (Fixed)**:
   - **Problem**: Browser console showed CORS errors blocking requests to `http://192.168.0.202:5000/api/gainers/live` from origin `http://192.168.0.202:3000`.
   - **Cause**: Starlette/FastAPI's `CORSMiddleware` cannot use `allow_origins=["*"]` when `allow_credentials=True`.
   - **Fix**: Modified `backend/fastapi_app/main.py` to dynamically filter out `*` and use `allow_origin_regex="https?://.*"`. This matches any HTTP/HTTPS origin and echoes it back in the CORS header, resolving the browser block.

2. **Missing `momentum_screener` Import (Fixed)**:
   - **Problem**: Backend API requests failed with `ModuleNotFoundError: No module named 'momentum_screener'`.
   - **Cause**: The application was run with `cwd` set to `/opt/trading-journal/backend`, but the `momentum_screener` package resides outside it at `/opt/trading-journal/momentum_screener`.
   - **Fix**: Updated `backend/fastapi_app/main.py` and `backend/fastapi_app/celery_app.py` to dynamically add the parent repository root to Python's `sys.path` on boot.

3. **Celery Worker Redis Disconnection (Fixed)**:
   - **Problem**: Celery was spamming connection refused errors trying to connect to local Redis (`127.0.0.1:6379`).
   - **Cause**: The production `.env` was missing `CELERY_BROKER_URL`, defaulting to localhost.
   - **Fix**: Appended the correct remote Redis instance configuration (`redis://192.168.0.151:6379`) to `/opt/trading-journal/backend/.env`. Celery is now successfully connected and ready.

4. **Shared Schwab Token Configuration**:
   - Both the development and production `.env` files are now configured to share the absolute path for the token: `SCHWAB_TOKEN_PATH=/home/jackc/.config/schwab/token.json`.
   - This ensures that once you authenticate via your user account, the background PM2 daemon (running as `root`) can immediately read and use the same token.

---

## 🔑 Remaining Action Required

The Schwab API client needs a one-time interactive OAuth login to generate the initial `token.json` file. 

To complete this, please run the following command in a terminal when you return:

```bash
/opt/trading-journal/backend/venv/bin/python /home/jackc/projects/homma-research/schwab_auth_setup.py
```

### 🚶‍♂️ Auth Walkthrough:
1. The script will output an authorization URL. Open this URL in your web browser.
2. Log in with your Schwab developer credentials and authorize the application.
3. The page will redirect to your callback URL (e.g. `https://127.0.0.1:8182/?code=...`). It might show a connection error in the browser, which is expected.
4. **Copy the entire redirected URL** from the browser's address bar.
5. Paste it back into your terminal prompt where the script is waiting, and press Enter.

Once the `token.json` file is successfully written to `/home/jackc/.config/schwab/token.json`, the background FastAPI service and Celery tasks will immediately pick it up and begin fetching live data.

---

## 🔍 Verification Commands
Once authenticated, you can check the status of the services and logs:

```bash
# Check service logs for any errors
sudo pm2 logs fastapi-backend

# Check Celery worker logs
sudo pm2 logs celery-worker

# Test hitting the live endpoint
curl -i -H "Origin: http://192.168.0.202:3000" http://localhost:5000/api/gainers/live
```
