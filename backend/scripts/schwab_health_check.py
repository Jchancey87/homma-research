import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Add paths
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, os.path.join(_REPO_ROOT, 'backend'))

# Load environment
load_dotenv(os.path.join(_REPO_ROOT, 'backend', '.env'))

from config import Config
from momentum_screener.schwab.auth import get_client

def send_alert_email(subject: str, message: str):
    if not Config.SMTP_SERVER or not Config.SMTP_USER or not Config.NOTIFY_EMAIL:
        print("SMTP configuration is missing. Cannot send alert email.")
        return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = Config.SMTP_USER
    msg['To'] = Config.NOTIFY_EMAIL

    part = MIMEText(message, 'plain')
    msg.attach(part)

    try:
        print(f"Connecting to SMTP server {Config.SMTP_SERVER}:{Config.SMTP_PORT}...")
        server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT)
        server.starttls()
        if Config.SMTP_PASSWORD:
            server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
        
        server.sendmail(Config.SMTP_USER, Config.NOTIFY_EMAIL, msg.as_string())
        server.quit()
        print("Alert email sent successfully!")
    except Exception as e:
        print(f"Failed to send alert email: {e}")

def main():
    errors = []
    
    # 1. Initialize client / check token existence and expiration
    print("Checking token load...")
    try:
        client = get_client()
    except Exception as e:
        errors.append(f"Failed to load/refresh Schwab Client Token: {e}")
        client = None

    if client:
        # 2. Check Market Data API
        print("Testing Market Data API...")
        try:
            r = client.get_quote('AAPL')
            if r.status_code != 200:
                errors.append(f"Market Data API returned status {r.status_code}: {r.text}")
        except Exception as e:
            errors.append(f"Market Data API failed with error: {e}")

        # 3. Check Trader API (Preferences)
        print("Testing Trader API...")
        try:
            r = client.get_user_preferences()
            if r.status_code != 200:
                errors.append(f"Trader API (Preferences) returned status {r.status_code}: {r.text}")
        except Exception as e:
            errors.append(f"Trader API (Preferences) failed with error: {e}")

    if errors:
        error_msg = "\n".join(errors)
        print(f"Health check failed:\n{error_msg}")
        subject = "⚠️ Schwab API Health Check FAILED"
        body = (
            f"Schwab API Health Check has detected failures on your system.\n\n"
            f"Errors found:\n"
            f"--------------------------------------------------\n"
            f"{error_msg}\n"
            f"--------------------------------------------------\n\n"
            f"Please run 'python schwab_auth_setup.py' interactively on the server to re-authorize."
        )
        send_alert_email(subject, body)
        sys.exit(1)
    else:
        print("Schwab API health check passed successfully.")
        sys.exit(0)

if __name__ == '__main__':
    main()
