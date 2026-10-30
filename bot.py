from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

router = Router()

# Mini App havolasi (Render yoki Vercel manzilingiz)
WEB_APP_URL = "https://pharmaxotira-bot.onrender.com"  # O'zingizning domeningizni qo'ying

START_TEXT = (
    "👋 **PharmaXotira** botiga xush kelibsiz!\n\n"
    "💊 Bu bot farmakologiya fanidan **\"Periferik asam sistemasiga ta'sir etuvchi dorilar\"** "
    "bo'limidagi 63 ta dori vositasini interaktiv flashcardlar va mnemonikalar orqali oson yodlashingizga yordam beradi.\n\n"
    "📚 **Ma'lumotlar manbasi:**\n"
    "Barcha dori dozalari va chiqarilish shakllari **\"Retseptura 2017\"** o'quv qo'llanmasi hamda "
    "xalqaro tibbiy manbalar asosida shakllantirilgan.\n\n"
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
    ]
    
    await message.answer(
        text=START_TEXT,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
