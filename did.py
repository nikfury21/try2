import os
import subprocess
import requests
import isodate
from pyrogram import Client, filters
import threading
from flask import Flask

# ================= CONFIG =================
BOT_TOKEN = "8498045631:AAGy7G45gS4TX69pI1KE8NKrKJ2ToeGi2dg"
API_ID = 23679210
API_HASH = "de1030f3e6fa64f9d41540b1f6f53b7a"

YOUTUBE_API_KEY = "AIzaSyAgu3cgcmbTTnbovQsBmYKefcZ_rgcmLPM"

# Render API (separate deployment)
API_BASE_URL = "https://try-x2ij.onrender.com/info/"  # UPDATE THIS
INTERNAL_API_KEY = "super_secret_key_12345"  # UPDATE or env

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ================= FLASK =================
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Music bot is running", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
    )

# ================= HELPERS =================
def search_youtube(query: str) -> str:
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet", "q": query, "type": "video",
        "maxResults": 1, "key": YOUTUBE_API_KEY,
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    items = r.json().get("items")
    if not items:
        raise Exception("No results")
    return items[0]["id"]["videoId"]

def get_video_duration_seconds(video_id: str) -> int:
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {"part": "contentDetails", "id": video_id, "key": YOUTUBE_API_KEY}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    items = r.json().get("items")
    if not items:
        return 0
    iso_duration = items[0]["contentDetails"]["duration"]
    return int(isodate.parse_duration(iso_duration).total_seconds())

# ================= BOT =================
app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply("🎵 Music Bot\n\nUse:\n/song <song name>")

@app.on_message(filters.command("song"))
async def song(_, msg):
    if len(msg.command) < 2:
        return await msg.reply("❌ Usage: /song <song name>")

    query = " ".join(msg.command[1:])
    status = await msg.reply("🔍 Searching...")

    try:
        video_id = search_youtube(query)
    except Exception:
        return await status.edit("❌ No results found")

    dur = get_video_duration_seconds(video_id)
    if dur > 600:
        return await status.edit("❌ Video too long (max 10 min)")

    await status.edit("📡 Fetching streams...")

    headers = {"X-API-Key": INTERNAL_API_KEY}
    api_url = f"{API_BASE_URL}{video_id}"
    try:
        api_resp = requests.get(api_url, headers=headers, timeout=30)
        api_resp.raise_for_status()
        data = api_resp.json()
    except Exception as e:
        return await status.edit(f"❌ API error: {str(e)}")

    if data.get("status") != "success" or not data.get("audio_url"):
        return await status.edit("❌ No audio stream available")

    await status.edit("📤 Sending audio...")

    try:
        await msg.reply_audio(
            data["audio_url"],
            title=query,
            performer="YouTube",
            duration=data.get("duration", 0)
        )
    except Exception as e:
        await msg.reply(f"❌ Send failed: {str(e)}")
    finally:
        await status.delete()


print("🌐 Starting Flask...")
threading.Thread(target=run_flask, daemon=True).start()

print("🎵 Bot running...")
app.run()


