import os
import requests
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, time
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

IST_TZ = ZoneInfo("Asia/Kolkata")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
APP_URL = os.getenv("APP_URL", "http://localhost:8000")

MOTIVATION_QUOTES = [
    "“The secret of getting ahead is getting started.” — Mark Twain",
    "“Small daily improvements over time lead to stunning results.” — Robin Sharma",
    "“Consistency compounds. Show up even for 30 focused minutes.”",
    "“Don't break the chain. Future you will thank present you.”",
    "“Focus on the process, not the outcome. One query, one test at a time.”",
    "“Discipline is choosing between what you want now and what you want most.”",
]

def get_current_ist_time() -> datetime:
    """Returns current datetime in IST."""
    return datetime.now(IST_TZ)

def is_in_alert_window(dt: Optional[datetime] = None) -> Tuple[bool, str]:
    """
    Checks if the current time is within allowed alert hours in IST:
    - Morning: 5:30 AM to 11:30 AM IST
    - Night:   9:00 PM to 12:00 AM (midnight) IST
    
    Quiet Hours (NO ALERTS):
    - Sleep: 12:00 AM to 5:30 AM IST
    - Work:  11:30 AM to 9:00 PM IST (Shift: 2 PM - 10 PM)
    """
    if dt is None:
        dt = get_current_ist_time()
        
    t = dt.time()
    
    morning_start = time(5, 30)
    morning_end = time(11, 30)
    night_start = time(21, 0)
    night_end = time(23, 59, 59)
    
    if morning_start <= t <= morning_end:
        return True, "Morning study window (5:30 AM – 11:30 AM IST)"
    elif night_start <= t <= night_end:
        return True, "Night study window (9:00 PM – 12:00 AM IST)"
    elif time(0, 0) <= t < morning_start:
        return False, "Sleep quiet hours (12:00 AM – 5:30 AM IST)"
    else:
        return False, "Work shift quiet hours (11:30 AM – 9:00 PM IST)"

def get_quote_of_the_day() -> str:
    day_of_year = datetime.now().timetuple().tm_yday
    return MOTIVATION_QUOTES[day_of_year % len(MOTIVATION_QUOTES)]

def format_reminder_message(active_day: Dict[str, Any], stats: Dict[str, Any]) -> str:
    """Format rich HTML message based on status and resume notes."""
    day_num = active_day.get("day", 1)
    topic = active_day.get("topic", "")
    task = active_day.get("task", "")
    status = active_day.get("status", "Not started")
    resume_note = (active_day.get("resume_note") or "").strip()
    phase = active_day.get("phase", "SQL")
    
    core_completed = stats.get("core_completed", 0)
    core_total = stats.get("core_total", 25)
    core_pct = stats.get("core_percent", 0.0)

    # Progress bar visualization (10 blocks)
    filled_blocks = int(round(core_pct / 10))
    bar = "▓" * filled_blocks + "░" * (10 - filled_blocks)

    if status == "Done":
        return (
            f"🎉 <b>DAY {day_num} COMPLETED!</b>\n\n"
            f"<b>Topic:</b> {topic}\n"
            f"<b>Progress:</b> [{bar}] {core_pct}% ({core_completed}/{core_total} Days)\n\n"
            f"Great job! Take a well-deserved rest or review your notes for tomorrow.\n\n"
            f"🔗 <a href='{APP_URL}'>Open ETL Study Dashboard</a>"
        )

    # If user left a resume note or is in progress
    if resume_note or status == "In progress":
        header = f"⚠️ <b>CONTINUE WHERE YOU LEFT OFF (Day {day_num})</b>"
        focus_block = (
            f"📝 <b>Where You Stopped:</b>\n"
            f"<i>\"{resume_note if resume_note else 'In progress - pick up where you left!'}\"</i>\n\n"
            f"🎯 <b>Today's Mission:</b>\n{task}"
        )
    else:
        header = f"🚀 <b>TODAY'S MISSION: NEW TOPIC (Day {day_num})</b>"
        focus_block = (
            f"📌 <b>Topic:</b> {topic}\n\n"
            f"🎯 <b>Today's Mission:</b>\n{task}"
        )

    quote = get_quote_of_the_day()
    now_ist = get_current_ist_time().strftime("%I:%M %p IST")

    target_date = active_day.get("target_date_short", "")
    date_str = f" ({target_date})" if target_date else ""

    msg = (
        f"{header}{date_str}\n"
        f"<b>Time:</b> {now_ist} | <b>Phase:</b> {phase}\n"
        f"<b>Status:</b> {status}\n"
        f"<b>Core Progress:</b> [{bar}] {core_pct}% ({core_completed}/{core_total})\n"
        f"────────────────────────\n"
        f"{focus_block}\n"
        f"────────────────────────\n"
        f"💡 <i>{quote}</i>\n\n"
        f"👉 <a href='{APP_URL}'>Open Dashboard to Update Status & Notes</a>"
    )
    return msg

def send_telegram_message(text: str, bot_token: Optional[str] = None, chat_id: Optional[str] = None) -> Dict[str, Any]:
    """Send HTML message via Telegram Bot API."""
    token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
    chat = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat:
        raise ValueError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
        
    token = str(token).strip().strip("'").strip('"')
    chat = str(chat).strip().strip("'").strip('"')
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    
    res = requests.post(url, json=payload, timeout=10)
    if res.status_code >= 400:
        raise RuntimeError(f"Telegram API Error {res.status_code}: {res.text}")
        
    return res.json()
