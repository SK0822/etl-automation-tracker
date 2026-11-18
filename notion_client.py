import os
import requests
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")
PLAN_START_DATE_STR = os.getenv("PLAN_START_DATE", "2026-11-18")

BASE_URL = "https://api.notion.com/v1"
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def query_notion_db() -> List[Dict[str, Any]]:
    """Fetch all pages from the Notion database sorted by Day."""
    if not NOTION_TOKEN or not DATABASE_ID:
        raise ValueError("Missing NOTION_TOKEN or DATABASE_ID in environment")
    
    url = f"{BASE_URL}/databases/{DATABASE_ID}/query"
    payload = {
        "sorts": [{"property": "Day", "direction": "ascending"}],
        "page_size": 100
    }
    
    response = requests.post(url, headers=HEADERS, json=payload, timeout=15)
    if response.status_code >= 400:
        raise RuntimeError(f"Notion API error {response.status_code}: {response.text}")
    
    data = response.json()
    return data.get("results", [])

def parse_page(page: Dict[str, Any]) -> Dict[str, Any]:
    """Parse a Notion page into a friendly dictionary."""
    props = page.get("properties", {})
    
    # Day
    day = props.get("Day", {}).get("number")
    
    # Phase
    phase_obj = props.get("Phase", {}).get("select") or {}
    phase = phase_obj.get("name", "General")
    phase_color = phase_obj.get("color", "gray")
    
    # Topic (Title)
    title_objs = props.get("Topic", {}).get("title", [])
    topic = "".join([t.get("plain_text", "") for t in title_objs])
    
    # Today's task
    task_objs = props.get("Today's task", {}).get("rich_text", [])
    task = "".join([t.get("plain_text", "") for t in task_objs])
    
    # Status
    status_obj = props.get("Status", {}).get("select") or {}
    status = status_obj.get("name", "Not started")
    status_color = status_obj.get("color", "gray")
    
    # Resume note
    resume_objs = props.get("Resume note", {}).get("rich_text", [])
    resume_note = "".join([t.get("plain_text", "") for t in resume_objs])
    
    # Last done
    last_done_obj = props.get("Last done", {}).get("date") or {}
    last_done = last_done_obj.get("start")
    
    return {
        "page_id": page["id"],
        "day": day,
        "phase": phase,
        "phase_color": phase_color,
        "topic": topic,
        "task": task,
        "status": status,
        "status_color": status_color,
        "resume_note": resume_note,
        "last_done": last_done,
        "url": page.get("url")
    }

def get_plan_summary() -> Dict[str, Any]:
    """Fetch and organize the complete plan with metrics and the active focus day."""
    pages = query_notion_db()
    days = [parse_page(p) for p in pages if p.get("properties", {}).get("Day", {}).get("number") is not None]
    days.sort(key=lambda d: d["day"])
    
    try:
        start_dt = date.fromisoformat(PLAN_START_DATE_STR)
    except Exception:
        start_dt = date(2026, 11, 18)

    for d in days:
        d_num = d.get("day", 1)
        target_d = start_dt + timedelta(days=d_num - 1)
        d["target_date"] = target_d.strftime("%b %d, %Y")
        d["target_date_short"] = target_d.strftime("%b %d")

    total_days = len(days)
    completed_days = sum(1 for d in days if d["status"] == "Done")
    in_progress_days = sum(1 for d in days if d["status"] == "In progress")
    
    # 25 core days count
    core_days = [d for d in days if d["day"] <= 25]
    core_completed = sum(1 for d in core_days if d["status"] == "Done")
    
    percent_complete = round((completed_days / total_days * 100), 1) if total_days > 0 else 0
    core_percent = round((core_completed / 25 * 100), 1) if len(core_days) > 0 else 0
    core_end_date = (start_dt + timedelta(days=24)).strftime("%b %d, %Y")
    total_end_date = (start_dt + timedelta(days=total_days - 1)).strftime("%b %d, %Y") if total_days else ""
    
    # Determine Active Day:
    # 1. Any day marked 'In progress'
    # 2. Or the first day that is 'Not started'
    # 3. Or Day 1 if none found
    active_day = None
    for d in days:
        if d["status"] == "In progress":
            active_day = d
            break
            
    if not active_day:
        for d in days:
            if d["status"] == "Not started":
                active_day = d
                break
                
    if not active_day and days:
        active_day = days[0]

    return {
        "days": days,
        "active_day": active_day,
        "stats": {
            "total_days": total_days,
            "completed_days": completed_days,
            "in_progress_days": in_progress_days,
            "percent_complete": percent_complete,
            "core_completed": core_completed,
            "core_total": 25,
            "core_percent": core_percent,
            "start_date": PLAN_START_DATE_STR,
            "core_end_date": core_end_date,
            "total_end_date": total_end_date
        }
    }

def update_notion_page(page_id: str, status: Optional[str] = None, resume_note: Optional[str] = None) -> Dict[str, Any]:
    """Update status, resume note, and auto-set Last done in Notion."""
    url = f"{BASE_URL}/pages/{page_id}"
    properties: Dict[str, Any] = {}
    
    if status is not None:
        properties["Status"] = {"select": {"name": status}}
        if status == "Done":
            properties["Last done"] = {"date": {"start": date.today().isoformat()}}
        elif status in ("Not started", "In progress"):
            # Clear or leave date as is
            pass
            
    if resume_note is not None:
        properties["Resume note"] = {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": resume_note}
                }
            ] if resume_note.strip() else []
        }
        
    response = requests.patch(url, headers=HEADERS, json={"properties": properties}, timeout=15)
    if response.status_code >= 400:
        raise RuntimeError(f"Notion Update Error {response.status_code}: {response.text}")
        
    return parse_page(response.json())
