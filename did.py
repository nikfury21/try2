import os
import threading
import subprocess
import requests
import isodate
from flask import Flask
from pyrogram import Client, filters, idle
from pytubefix import YouTube

BOT_TOKEN = "8498045631:AAGy7G45gS4TX69pI1KE8NKrKJ2ToeGi2dg"
API_ID = 23679210
API_HASH = "de1030f3e6fa64f9d41540b1f6f53b7a"
YOUTUBE_API_KEY = "AIzaSyAgu3cgcmbTTnbovQsBmYKefcZ_rgcmLPM"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
TOKENS_PATH = os.path.join(BASE_DIR, "tokens.json")


def search_youtube(query: str) -> str:
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": 1,
        "key": YOUTUBE_API_KEY,
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    items = r.json().get("items")
    if not items:
        raise Exception("No results")
    return items[0]["id"]["videoId"]


def get_video_duration_seconds(video_id: str) -> int:
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "contentDetails",
        "id": video_id,
        "key": YOUTUBE_API_KEY,
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    items = r.json().get("items")
    if not items:
        return 0
    iso_duration = items[0]["contentDetails"]["duration"]
    return int(isodate.parse_duration(iso_duration).total_seconds())


def download_audio_to_webm(video_id: str) -> str:
    url = f"https://www.youtube.com/watch?v={video_id}"
    kwargs = {}
    if os.path.exists(TOKENS_PATH):
        kwargs.update(dict(use_oauth=True, allow_oauth_cache=True))
    yt = YouTube(url, **kwargs)
    audio_stream = yt.streams.filter(only_audio=True).order_by("abr").desc().first()
    if not audio_stream:
        raise Exception("No audio stream found")
    out_path = os.path.join(DOWNLOAD_DIR, f"{video_id}_audio.webm")
    if os.path.exists(out_path):
        os.remove(out_path)
    audio_stream.download(output_path=out_path)
    return out_path


def convert_webm_to_mp3(input_path: str, video_id: str) -> str:
    output = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp3")
    print("Converting:", input_path, "->", output)
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-vn",
        "-acodec",
        "libmp3lame",
        "-b:a",
        "128k",
        "-ar",
        "44100",
        "-loglevel",
        "error",
        output,
    ]
    subprocess.run(cmd, check=True)
    return output


app_bot = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


@app_bot.on_message(filters.command("start"))
async def start_cmd(_, msg):
    await msg.reply(
        "🎵 Music Bot\n\nUse:\n/song <song name>",
        parse_mode=None,
    )


@app_bot.on_message(filters.command("song"))
async def song_cmd(_, msg):
    if len(msg.command) < 2:
        return await msg.reply(
            "❌ Usage: /song <song name>",
            parse_mode=None,
        )

    query = " ".join(msg.command[1:])
    status = await msg.reply("🔍 Searching...", parse_mode=None)

    try:
        video_id = search_youtube(query)
    except Exception:
        return await status.edit("❌ No results found", parse_mode=None)

    try:
        dur = get_video_duration_seconds(video_id)
        if dur > 600:
            return await status.edit(
                "❌ Video is too long (max 10 minutes).",
                parse_mode=None,
            )
    except Exception:
        pass

    await status.edit("⬇️ Downloading audio...", parse_mode=None)

    webm_path = None
    mp3_file = None

    try:
        webm_path = download_audio_to_webm(video_id)
    except Exception:
        return await status.edit("❌ Failed to download audio", parse_mode=None)

    await status.edit("🎧 Converting to MP3...", parse_mode=None)

    try:
        mp3_file = convert_webm_to_mp3(webm_path, video_id)
    except Exception:
        return await status.edit("❌ Conversion failed", parse_mode=None)

    await status.edit("📤 Uploading...", parse_mode=None)

    try:
        await msg.reply_audio(
            mp3_file,
            title=query,
        )
    finally:
        for path in (webm_path, mp3_file):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except PermissionError:
                    pass


# --- Flask app ---

flask_app = Flask(__name__)


@flask_app.route("/")
def index():
    return "Bot + Flask running"


def run_flask():
    port = int(os.environ.get("PORT", "10000"))
    flask_app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    print("🎵 Bot starting...")

    # Start bot (sync style)
    app_bot.start()  # connects and begins receiving updates [web:344][web:346]

    # Start Flask in background thread
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()

    # Keep the bot running and processing updates
    idle()  # blocks until you stop the app or container stops [web:341][web:346]

    # On shutdown
    app_bot.stop()
