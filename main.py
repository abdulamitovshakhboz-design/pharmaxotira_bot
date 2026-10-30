import json
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import uvicorn

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-app.up.railway.app")

app = FastAPI()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Static papkani ulaymiz (Mini App HTML uchun)
if not os.path.exists("static"):
    os.makedirs("static")

app.mount("/app", StaticFiles(directory="static", html=True), name="static")

@app.get("/api/drugs")
def get_drugs():
    with open("drugs_database.json", "r", encoding="utf-8") as f:
        return json.load(f)

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 PharmaXotira Mini App", web_app=WebAppInfo(url=f"{WEBAPP_URL}/app"))]
    ])
    await message.answer(
        "<b>PharmaXotira | Farmakologiya</b> botiga xush kelibsiz!\n\n"
        "Interaktiv flashcardlarni ochish uchun pastdagi tugmani bosing:",
        reply_markup=kb,
        parse_mode="HTML"
    )

@app.on_event("startup")
async def on_startup():
    asyncio.createTask(dp.start_polling(bot))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
