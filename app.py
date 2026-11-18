import os
import asyncio
import logging
from typing import Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv, set_key

import notion_client
import telegram_notifier

load_dotenv()

# Configure logging to show up clearly in Render logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tracker")

# In-memory timestamp of last alert sent
LAST_REMINDER_SENT_AT: Optional[datetime] = None

async def reminder_scheduler_loop():
    """
    Independent background task running inside FastAPI.
    Checks time every 60 seconds.
    During study windows (5:30-11:30 AM & 9:00 PM-12:00 AM IST),
    sends a reminder every 2 hours if active task is not marked Done.
    """
    global LAST_REMINDER_SENT_AT
    logger.info("⏰ Background reminder scheduler initialized.")
    await asyncio.sleep(5)  # Let server startup finish

    while True:
        try:
            now_ist = telegram_notifier.get_current_ist_time()
            in_window, window_desc = telegram_notifier.is_in_alert_window(now_ist)

            if in_window:
                should_send = False
                if LAST_REMINDER_SENT_AT is None:
                    should_send = True
                    reason = "First alert since server boot"
                else:
                    elapsed_seconds = (now_ist - LAST_REMINDER_SENT_AT).total_seconds()
                    # 115 minutes buffer for 2-hour interval
                    if elapsed_seconds >= (115 * 60):
                        should_send = True
                        reason = f"2 hours elapsed ({int(elapsed_seconds // 60)} mins since last alert)"

                if should_send:
                    logger.info(f"Checking Notion for scheduled alert ({reason})...")
                    summary = notion_client.get_plan_summary()
                    active = summary.get("active_day")
                    stats = summary.get("stats", {})

                    if active and active.get("status") != "Done":
                        logger.info(f"Firing Telegram alert for Day {active.get('day')} (Status: {active.get('status')})...")
                        msg = telegram_notifier.format_reminder_message(active, stats)
                        telegram_notifier.send_telegram_message(msg)
                        LAST_REMINDER_SENT_AT = now_ist
                        logger.info(f"✅ Telegram alert delivered at {now_ist.strftime('%I:%M %p IST')}!")
                    else:
                        logger.info("Active topic is already marked Done. Alert skipped.")
            else:
                logger.debug(f"Quiet hours ({window_desc}). Alert suppressed.")

        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}", exc_info=True)

        # Check every 60 seconds
        await asyncio.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: spawn background scheduler
    task = asyncio.create_task(reminder_scheduler_loop())
    yield
    # Shutdown
    task.cancel()

app = FastAPI(title="ETL Automation Study Tracker", version="1.2.0", lifespan=lifespan)

# Serve static directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

class UpdateDayRequest(BaseModel):
    page_id: str
    status: Optional[str] = None
    resume_note: Optional[str] = None

class TelegramSettingsRequest(BaseModel):
    bot_token: str
    chat_id: str

@app.get("/api/plan")
def get_plan():
    """Returns all 31 days, current active focus day, and statistics."""
    try:
        return notion_client.get_plan_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/update")
def update_day(req: UpdateDayRequest):
    """Updates status and/or resume note in Notion."""
    try:
        updated = notion_client.update_notion_page(
            page_id=req.page_id,
            status=req.status,
            resume_note=req.resume_note
        )
        return {
            "success": True,
            "updated": updated,
            "message": f"Day {updated['day']} updated successfully in Notion!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ping")
def ping_keepalive():
    """
    Keepalive endpoint for UptimeRobot.
    Keeps Render free tier awake.
    Returns current IST time, alert window status, and last alert timestamp.
    """
    now_ist = telegram_notifier.get_current_ist_time()
    in_window, window_desc = telegram_notifier.is_in_alert_window(now_ist)
    
    elapsed_str = None
    if LAST_REMINDER_SENT_AT:
        mins = int((now_ist - LAST_REMINDER_SENT_AT).total_seconds() // 60)
        elapsed_str = f"{mins} minutes ago ({LAST_REMINDER_SENT_AT.strftime('%I:%M %p IST')})"

    return {
        "status": "alive",
        "service": "ETL Automation Study Tracker",
        "ist_time": now_ist.strftime("%Y-%m-%d %I:%M:%S %p IST"),
        "in_alert_window": in_window,
        "window_description": window_desc,
        "last_alert_sent": elapsed_str or "No alert sent since boot"
    }

@app.get("/api/cron/reminder")
@app.post("/api/cron/reminder")
def trigger_scheduled_reminder(force: bool = False):
    """
    Explicit reminder trigger.
    Enforces shift-based quiet hours unless force=True.
    """
    global LAST_REMINDER_SENT_AT
    now_ist = telegram_notifier.get_current_ist_time()
    in_window, window_desc = telegram_notifier.is_in_alert_window(now_ist)
    
    if not in_window and not force:
        return {
            "status": "suppressed",
            "reason": f"Quiet hours active ({window_desc}). Alerts stop during work shift and sleep.",
            "ist_time": now_ist.strftime("%I:%M %p IST")
        }

    try:
        summary = notion_client.get_plan_summary()
        active = summary.get("active_day")
        stats = summary.get("stats", {})
        
        if not active:
            return {"status": "skipped", "message": "No active day found"}
            
        status = active.get("status", "Not started")
        if status == "Done" and not force:
            return {
                "status": "skipped",
                "day": active.get("day"),
                "message": "Today's active topic is already marked as Done. Rest time!"
            }
            
        # Format and send reminder
        message = telegram_notifier.format_reminder_message(active, stats)
        result = telegram_notifier.send_telegram_message(message)
        LAST_REMINDER_SENT_AT = now_ist
        
        return {
            "status": "sent",
            "day": active.get("day"),
            "topic": active.get("topic"),
            "task_status": status,
            "window": window_desc,
            "ist_time": now_ist.strftime("%I:%M %p IST"),
            "telegram_response": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reminder/test")
def test_reminder(payload: Optional[dict] = None):
    """Send an immediate test alert to Telegram (bypasses quiet hours)."""
    try:
        token = (payload or {}).get("bot_token") or os.getenv("TELEGRAM_BOT_TOKEN")
        chat = (payload or {}).get("chat_id") or os.getenv("TELEGRAM_CHAT_ID")
        
        if not token or not chat:
            raise HTTPException(
                status_code=400,
                detail="Missing Telegram Bot Token or Chat ID. Please configure them in Settings or .env"
            )
            
        summary = notion_client.get_plan_summary()
        active = summary.get("active_day") or summary["days"][0]
        stats = summary.get("stats", {})
        
        message = telegram_notifier.format_reminder_message(active, stats)
        result = telegram_notifier.send_telegram_message(message, bot_token=token, chat_id=chat)
        
        return {
            "success": True,
            "message": "Telegram test alert delivered successfully! Check your Telegram app.",
            "telegram_result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/settings/telegram")
def save_telegram_settings(req: TelegramSettingsRequest):
    """Save Telegram bot token and chat id into local .env and runtime."""
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    try:
        set_key(env_file, "TELEGRAM_BOT_TOKEN", req.bot_token)
        set_key(env_file, "TELEGRAM_CHAT_ID", req.chat_id)
        os.environ["TELEGRAM_BOT_TOKEN"] = req.bot_token
        os.environ["TELEGRAM_CHAT_ID"] = req.chat_id
        return {"success": True, "message": "Telegram settings saved to .env"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/settings/telegram")
def get_telegram_status():
    """Check whether Telegram credentials are configured."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    now_ist = telegram_notifier.get_current_ist_time()
    in_window, window_desc = telegram_notifier.is_in_alert_window(now_ist)
    return {
        "configured": bool(token and chat),
        "bot_token_masked": f"{token[:6]}...{token[-4:]}" if token and len(token) > 10 else None,
        "chat_id": chat if chat else None,
        "ist_time": now_ist.strftime("%I:%M %p IST"),
        "in_alert_window": in_window,
        "window_desc": window_desc
    }

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "ETL Automation Tracker"}

@app.get("/", response_class=HTMLResponse)
def index():
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return "<h1>Frontend index.html not found in static/</h1>"

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
