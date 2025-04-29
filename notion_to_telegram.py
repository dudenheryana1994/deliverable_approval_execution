import requests
import json
import os
from dotenv import load_dotenv
from datetime import datetime
import logging
import sys

# Konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(name)s:%(message)s",
    handlers=[
        logging.FileHandler("log_notion_to_telegram.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Muat variabel lingkungan dari file .env
load_dotenv()

NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SENT_IDS_FILE = "id_sent.json"

def get_notion_data():
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Notion data: {e}")
        return None

def send_to_telegram(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logger.info(f"Message sent to Telegram ID {chat_id}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending message to {chat_id}: {e}")

def read_sent_ids():
    if os.path.exists(SENT_IDS_FILE):
        with open(SENT_IDS_FILE, "r") as f:
            return json.load(f)
    return []

def save_sent_ids(sent_ids):
    with open(SENT_IDS_FILE, "w") as f:
        json.dump(sent_ids, f, indent=4)

def extract_text(rich_text_list, default="Tidak ada data"):
    if not rich_text_list:
        return default
    return " ".join([text.get("plain_text", "") for text in rich_text_list if "plain_text" in text])

def extract_select(prop):
    if prop and isinstance(prop, dict):
        select_data = prop.get("select")
        if select_data and isinstance(select_data, dict):
            return select_data.get("name", "Tidak ada data")
    return "Tidak ada data"

def extract_date(prop):
    if isinstance(prop, dict):
        date_data = prop.get("date")
        if date_data and isinstance(date_data, dict):
            return date_data.get("start", "Tidak ada data")
    return "Tidak ada data"

def format_datetime(iso_str):
    if not iso_str or iso_str == "Tidak ada data":
        return "-"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception as e:
        logger.error(f"Date format error: {e}")
        return "-"

def main():
    notion_data = get_notion_data()
    if not notion_data:
        sys.exit(0)

    results = notion_data.get("results", [])
    if not results:
        logger.info("No data found.")
        sys.exit(0)

    sent_ids = read_sent_ids()

    for item in results:
        item_id = item.get("id")
        properties = item.get("properties", {})

        accept_reject = extract_select(properties.get("Accept / Reject", {}))
        project_name = extract_text(properties.get("Project Name", {}).get("rich_text", []))
        work_package = extract_text(properties.get("Work Package Name", {}).get("rich_text", []))
        id_activities = extract_text(properties.get("ID Activities", {}).get("rich_text", []))
        activities_name = extract_text(properties.get("Activities Name", {}).get("title", []))
        assignee_name = extract_text(properties.get("Assignee Name", {}).get("rich_text", []))
        user_name = extract_text(properties.get("User Name", {}).get("rich_text", []))
        accepted_date_raw = extract_date(properties.get("Accepted Date", {}))
        accepted_date = format_datetime(accepted_date_raw)

        id_kirim_fb = extract_text(properties.get("ID Kirim FB Tugas", {}).get("rich_text", []))
        id_telegram_us = extract_text(properties.get("ID Telegram (Us)", {}).get("rich_text", []))

        if item_id not in sent_ids and id_kirim_fb != "Tidak ada data" and id_telegram_us != "Tidak ada data":
            message = (
                f"*HASIL TUGAS*\n\n"
                f"🆔 *ID Activity:* {id_activities}\n"
                f"📄 *Nama Activity:* {activities_name}\n"
                f"👤 *Assignee:* {assignee_name}\n"
                f"👥 *User:* {user_name}\n"
                f"🏗 *Project:* {project_name}\n"
                f"📦 *Work Package:* {work_package}\n"
                f"📅 *Tanggal Diterima:* {accepted_date}\n"
                f"✅ *Status:* {accept_reject}"
            )
            send_to_telegram(id_telegram_us, message)
            sent_ids.append(item_id)
            save_sent_ids(sent_ids)

    logger.info("Processing completed.")
    sys.exit(0)

if __name__ == "__main__":
    main()
