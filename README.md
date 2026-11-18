# ETL Automation — 25-Day Study Tracker & Smart Reminder Engine

A full-stack, Notion-backed web application and automated Telegram reminder system to help you master **ETL Automation & QA Engineering** in 25 days (starting **November 18, 2026**).

---

## ⏰ Work Shift & Alert Schedule (IST)

Your shift is **2:00 PM to 10:00 PM IST**. Alerts are customized around your routine:

| Window | Time (IST) | Status | What Happens |
|---|---|---|---|
| 🌅 **Morning Study** | **5:30 AM – 11:30 AM** | **ALERTS ACTIVE** | Pings every 2 hours with today's topic & resume note |
| 💼 **Work Shift Buffer** | **11:30 AM – 9:00 PM** | 🔕 **SILENCED** | Zero alerts during work/shift hours |
| 🌙 **Night Study** | **9:00 PM – 12:00 AM** | **ALERTS ACTIVE** | Pings every 2 hours until topic is marked Done |
| 🛌 **Sleep Window** | **12:00 AM – 5:30 AM** | 🔕 **SILENCED** | Zero alerts during sleep hours |

*Once marked **"Done"**, alerts automatically stop for the day!*

---

## 🌐 UptimeRobot Setup (Keep Render Free Tier Awake 24/7)

Render Free Tier sleeps after 15 minutes of inactivity. To prevent this without paying:

1. Sign up for free at [uptimerobot.com](https://uptimerobot.com).
2. Click **+ Add New Monitor**:
   * **Monitor Type**: `HTTP(s)`
   * **Friendly Name**: `ETL Study Tracker`
   * **URL (or IP)**: `https://<your-app-name>.onrender.com/api/ping`
   * **Monitoring Interval**: `Every 10 minutes` (or 5 minutes)
3. Click **Create Monitor**.

### ⚡ What `/api/ping` does:
* **Keeps Render Awake**: Responds in <5ms, keeping your free Render instance running 24/7.
* **Auto-Scheduler**: Checks if you are in your study window (5:30–11:30 AM or 9:00 PM–12:00 AM IST) and triggers the 2-hour reminder if your task is not Done.

---

## ⚡ Quick Start (Local Run)

1. Check your `.env`:
   ```env
   NOTION_TOKEN=ntn_...
   DATABASE_ID=41945e70-eb68-81fa-9fce-fe8c3ae18eb5
   TELEGRAM_BOT_TOKEN=...
   TELEGRAM_CHAT_ID=...
   PLAN_START_DATE=2026-11-18
   ```

2. Run the server:
   ```bash
   python -m uvicorn app:app --host 0.0.0.0 --port 8000
   ```

3. Open your browser:
   👉 **http://localhost:8000**

---

## 📱 Telegram Setup (60 Seconds)

1. Open Telegram → Search **`@BotFather`** → Send `/newbot` → Copy the **Bot Token**.
2. Search **`@userinfobot`** → Send `/start` → Copy your numeric **Chat ID**.
3. Open a chat with your new bot and press **Start**.
4. In the app ([http://localhost:8000](http://localhost:8000)), click **Telegram Bot** → enter token & chat ID → click **Save & Connect** → click **Send Test Alert**.

---

## ☁️ Deploy to Render Free Tier

1. **Push to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "ETL Study Tracker with shift schedule"
   git remote add origin https://github.com/<username>/<repo>.git
   git push -u origin main
   ```
2. **Deploy on Render**:
   - Go to [dashboard.render.com](https://dashboard.render.com) → **New +** → **Blueprint** → Select your repo.
   - Render reads `render.yaml` automatically.
   - Add your environment variables (`NOTION_TOKEN`, `DATABASE_ID`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`).
3. Add the monitor in **UptimeRobot** pointing to `https://<your-render-url>/api/ping`.
