"""
Early-warning notifier. Refreshes data, re-forecasts, and sends a message when the
alert level rises (no spam: the same warning is not repeated within 12 h).

    python alert.py                      # uses the 'Sensitive' profile threshold (60)
    python alert.py --threshold 90 --no-refresh
    python alert.py --demo
    python alert.py --city Delhi            # any city set up with pipeline.py

Channels (set in .env, all optional - without them the alert is just printed):
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ALERT_EMAIL_TO

Schedule it every 3 hours, e.g. Linux/macOS cron:
    0 */3 * * *  cd /path/to/aqews && python alert.py >> reports/alert.log 2>&1
Windows: Task Scheduler -> "python alert.py" with "Start in" = project folder.
"""
from __future__ import annotations

import argparse
import json
import os
import smtplib
from email.message import EmailMessage

import pandas as pd
import requests

import config
import pipeline
from aq import insights as I

RANK = {"CLEAR": 0, "WATCH": 1, "WARNING": 2, "EMERGENCY": 3, "Unknown": -1}


def send_telegram(text: str) -> bool:
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return False
    r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                      data={"chat_id": chat, "text": text}, timeout=30)
    return r.ok


def send_email(subject: str, text: str) -> bool:
    host, to = os.environ.get("SMTP_HOST"), os.environ.get("ALERT_EMAIL_TO")
    if not (host and to):
        return False
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, os.environ.get("SMTP_USER", to), to
    msg.set_content(text)
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", 587))) as s:
        s.starttls()
        if os.environ.get("SMTP_USER"):
            s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
        s.send_message(msg)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=config.PROFILES["Sensitive (asthma / heart / lung)"])
    ap.add_argument("--no-refresh", action="store_true")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--city", help="city to check (must be set up with pipeline.py)")
    a = ap.parse_args()
    if a.city:
        config.set_city(a.city)
    STATE = config.REPORT_DIR / "alert_state.json"

    if not a.no_refresh:
        pipeline.fetch(demo=a.demo, history=False)
        pipeline.run_forecast()
    fc = I.localize(pd.read_csv(config.REPORT_DIR / "forecast.csv"))
    al = I.alert_summary(fc, a.threshold)
    now = pd.Timestamp.now(tz="UTC")

    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    last_level, last_time = state.get("level", "CLEAR"), pd.Timestamp(state.get("time", "2000-01-01T00:00Z"))
    escalated = RANK[al["level"]] > RANK.get(last_level, 0)
    repeat_due = RANK[al["level"]] >= 2 and (now - last_time) > pd.Timedelta(hours=12)

    text = f"[{config.CITY} PM2.5] {al['level']}: {al['message']}"
    if "peak_value" in al:
        text += f"\nAdvice: {I.HEALTH_ADVICE[I.category(al['peak_value'])[0]]}"
    print(text)
    if escalated or repeat_due:
        sent = [n for n, ok in (("telegram", send_telegram(text)),
                                ("email", send_email(f"Air quality {al['level']} - {config.CITY}", text))) if ok]
        print(f"notified via: {sent or 'console only (no channel configured)'}")
        state = {"level": al["level"], "time": str(now)}
    elif RANK[al["level"]] < RANK.get(last_level, 0):
        state = {"level": al["level"], "time": str(now)}          # de-escalate silently
    STATE.write_text(json.dumps(state))


if __name__ == "__main__":
    main()
