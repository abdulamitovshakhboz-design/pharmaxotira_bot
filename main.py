import os
import json
import httpx
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI()

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

DRUGS_FILE = "drugs_database.json"

# Telegram Bot Token (Render Environment Variables'га ёки бевосита уланг)
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
CHANNEL_USERNAME = "@fundamedical_academy"

def load_drugs():
    if os.path.exists(DRUGS_FILE):
        try:
            with open(DRUGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"JSON o'qishda xatolik: {e}")
    return []

@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

@app.get("/app")
async def read_app():
    return FileResponse("static/index.html")

@app.get("/api/drugs")
async def get_drugs():
    return load_drugs()

@app.get("/api/check-sub")
async def check_subscription(user_id: int = Query(...)):
    """
    Telegram Bot API (getChatMember) орқали фойдаланувчининг
    @fundamedical_academy каналига аъзолигини холис текширади.
    """
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        return {"subscribed": True}

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
    params = {
        "chat_id": CHANNEL_USERNAME,
        "user_id": user_id
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, params=params)
            res_data = response.json()
            
            if res_data.get("ok"):
                status = res_data.get("result", {}).get("status", "")
                if status in ["member", "administrator", "creator"]:
                    return {"subscribed": True}
    except Exception as e:
        print(f"Obunani tekshirishda xatolik: {e}")

    return {"subscribed": False}
