import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import get_connection
from config import Config
from jobs.daily_analysis_report import send_email

def check_db():
    print("Checking database connection...")
    try:
        with get_connection() as conn:
            # Query recent daily gainers
            rows = conn.execute("SELECT date, COUNT(*) as count FROM daily_gainers GROUP BY date ORDER BY date DESC LIMIT 5").fetchall()
            print("Recent Gainer Ingestions:")
            for r in rows:
                print(f"  Date: {r['date']}, Count: {r['count']}")
            
            # Query continuation picks
            picks = conn.execute("SELECT date, count(*) as count FROM continuation_picks GROUP BY date ORDER BY date DESC LIMIT 5").fetchall()
            print("\nRecent Continuation Picks:")
            for p in picks:
                print(f"  Date: {p['date']}, Count: {p['count']}")
                
            # Query llm_jobs
            jobs = conn.execute("SELECT type, status, created_at FROM llm_jobs ORDER BY created_at DESC LIMIT 5").fetchall()
            print("\nRecent LLM Jobs:")
            for j in jobs:
                print(f"  Type: {j['type']}, Status: {j['status']}, Created At: {j['created_at']}")
    except Exception as e:
        print(f"DB Error: {e}")

def check_email_config():
    print("\nSMTP Configuration:")
    print(f"  SMTP_SERVER: {Config.SMTP_SERVER}")
    print(f"  SMTP_PORT: {Config.SMTP_PORT}")
    print(f"  SMTP_USER: {Config.SMTP_USER}")
    print(f"  NOTIFY_EMAIL: {Config.NOTIFY_EMAIL}")
    print(f"  Has SMTP_PASSWORD? {'Yes' if Config.SMTP_PASSWORD else 'No'}")

def test_send_email():
    print("\nAttempting to send a test email...")
    try:
        send_email(str(date.today()), "This is a test of the Homma Research daily analysis email configuration.")
        print("Success! Test email sent.")
    except Exception as e:
        print(f"Error sending test email: {e}")

if __name__ == '__main__':
    check_db()
    check_email_config()
    test_send_email()
