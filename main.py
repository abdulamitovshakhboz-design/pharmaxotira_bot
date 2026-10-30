import os
import json
import httpx
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

DRUGS_FILE = "drugs_database.json"

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
CHANNEL_USERNAME = "@fundamedical_academy"
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://pharmaxotira-bot.onrender.com")

# --- AIOGRAM BOT CONFIGURATION ---
bot = Bot(token=BOT_TOKEN) if BOT_TOKEN and BOT_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN_HERE" else None
dp = Dispatcher()
router = Router()

START_TEXT = (
    "👋 **PharmaXotira** botiga xush kelibsiz!\n\n"
    "💊 Bu bot farmakologiya fanidan **\"Periferik asam sistemasiga ta'sir etuvchi dorilar\"** "
    "bo'limidagi 63 ta dori vositasini interaktiv flashcardlar va mnemonikalar orqali oson yodlashingizga yordam beradi.\n\n"
    "📚 **Ma'lumotlar manbasi:**\n"
    "Barcha dori dozalari va chiqarilish shakllari **\"Retseptura 2017\"** o'quv qo'llanmasi hamda "
    "xalqaro tibbiy manbalar (Medscape, Drugs.com) asosida shakllantirilgan.\n\n"
    "📥 **Taklif va murojaatlar uchun:**\n"
    "Bot bo'yicha taklif va mulohazalaringiz bo'lsa, @Shakhbozbek_Abdulamitov ga murojaat qilishingiz mumkin.\n\n"
    "👇 Pastdagi tugma orqali Mini App'ni ochishingiz mumkin:"
)

@router.message(CommandStart())
async def start_handler(message: types.Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Mini App'ni ochish",
                    web_app=WebAppInfo(url=WEB_APP_URL)
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Rasmiy kanal",
                    url="https://t.me/fundamedical_academy"
                )
            ]
        ]
    )
    await message.answer(text=START_TEXT, reply_markup=keyboard, parse_mode="Markdown")

dp.include_router(router)

# --- FASTAPI LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    if bot:
        asyncio.create_task(dp.start_polling(bot))
    yield
    if bot:
        await bot.session.close()

app = FastAPI(lifespan=lifespan)

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

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
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        return {"subscribed": True}

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
    params = {"chat_id": CHANNEL_USERNAME, "user_id": user_id}

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
