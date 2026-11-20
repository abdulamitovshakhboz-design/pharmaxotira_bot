
"""Private-chat audience tracking and admin broadcasts; PostgreSQL persistence."""
import asyncio
import logging
import os
import secrets
import time
from datetime import datetime, timezone

import psycopg
from aiogram import BaseMiddleware, F, Router, types
from aiogram.filters import Command
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramAPIError

log = logging.getLogger(__name__)
router = Router()
DATABASE_URL = os.getenv('DATABASE_URL', '')
ADMIN_IDS = {int(x.strip()) for x in os.getenv('ADMIN_IDS', '8908985083').split(',') if x.strip().isdigit()}
pending = {}
running = set()
tasks = set()

async def connect():
    return await psycopg.AsyncConnection.connect(DATABASE_URL, connect_timeout=10)

async def init_storage():
    if not DATABASE_URL:
        log.warning('DATABASE_URL not set: audience statistics disabled')
        return
    async with await connect() as conn:
        await conn.execute('''CREATE TABLE IF NOT EXISTS bot_users (
            user_id BIGINT PRIMARY KEY,
            first_seen TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_app_seen TIMESTAMPTZ,
            can_message BOOLEAN NOT NULL DEFAULT FALSE
        )''')

async def remember(user_id, *, private=False, app=False):
    if not DATABASE_URL:
        return
    async with await connect() as conn:
        await conn.execute('''INSERT INTO bot_users (user_id, can_message, last_app_seen)
            VALUES (%s, %s, CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END)
            ON CONFLICT (user_id) DO UPDATE SET last_seen=CURRENT_TIMESTAMP,
            can_message=bot_users.can_message OR EXCLUDED.can_message,
            last_app_seen=COALESCE(EXCLUDED.last_app_seen, bot_users.last_app_seen)''',
            (user_id, private, app))

class TrackPrivateMessages(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if event.chat.type == 'private' and event.from_user and not event.from_user.is_bot:
            try:
                await remember(event.from_user.id, private=True)
            except Exception:
                log.exception('Audience tracking failed')
        return await handler(event, data)

async def require_admin(message):
    if message.chat.type != 'private' or not message.from_user or message.from_user.id not in ADMIN_IDS:
        await message.answer('Bu buyruq faqat bot administratoriga ruxsat etilgan.')
        return False
    if not DATABASE_URL:
        await message.answer('Statistika uchun Render Environment bo‘limida DATABASE_URL ni sozlang.')
        return False
    return True

@router.message(Command('myid'))
async def myid(message: types.Message):
    if message.chat.type == 'private' and message.from_user:
        await message.answer(f'Sizning Telegram ID: {message.from_user.id}')

@router.message(Command('stats'))
async def stats(message: types.Message):
    if not await require_admin(message):
        return
    try:
        async with await connect() as conn:
            cur = await conn.execute('''SELECT COUNT(*),
                COUNT(*) FILTER (WHERE can_message),
                COUNT(*) FILTER (WHERE (first_seen AT TIME ZONE 'Asia/Tashkent')::date = (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Tashkent')::date),
                COUNT(*) FILTER (WHERE (last_seen AT TIME ZONE 'Asia/Tashkent')::date = (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Tashkent')::date),
                COUNT(*) FILTER (WHERE last_seen >= CURRENT_TIMESTAMP - INTERVAL '7 days'),
                COUNT(*) FILTER (WHERE (last_app_seen AT TIME ZONE 'Asia/Tashkent')::date = (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Tashkent')::date)
                FROM bot_users''')
            total, reachable, new, today, week, app = await cur.fetchone()
        await message.answer(f'📊 Bot statistikasi\n\nJami qayd etilgan: {total}\nXabar yuborish mumkin: {reachable}\nBugun yangi: {new}\nBugun faol: {today}\nOxirgi 7 kunda faol: {week}\nBugun Mini App ochgan: {app}\n\nKunlar Toshkent vaqti bo‘yicha. Hisob ushbu funksiya o‘rnatilgandan boshlanadi.')
    except Exception:
        log.exception('Stats failed')
        await message.answer('Bazaga ulanishda xatolik. DATABASE_URL va baza holatini tekshiring.')

@router.message(Command('broadcast'))
async def broadcast(message: types.Message):
    if not await require_admin(message):
        return
    if running:
        await message.answer('Hozir boshqa xabar yuborilmoqda. Tugashini kuting.')
        return
    source = message.reply_to_message
    if not source or source.chat.id != message.chat.id:
        await message.answer('Avval tarqatiladigan matn, rasm yoki videoni shu botga yuboring. So‘ng o‘sha xabarga Reply qilib /broadcast yozing. Albom uchun har bir xabar alohida yuboriladi.')
        return
    if source.has_protected_content or source.media_group_id:
        await message.answer('Himoyalangan xabar yoki albom o‘rniga bitta oddiy xabar yuboring.')
        return
    try:
        async with await connect() as conn:
            cur = await conn.execute('SELECT COUNT(*) FROM bot_users WHERE can_message')
            count = (await cur.fetchone())[0]
        if not count:
            await message.answer('Hozircha xabar yuboriladigan foydalanuvchi yo‘q.')
            return
        # copy_message verifies that this message type can actually be copied.
        await message.bot.copy_message(message.chat.id, source.chat.id, source.message_id)
        token = secrets.token_hex(8)
        pending[token] = (message.from_user.id, source.chat.id, source.message_id, time.monotonic())
        for key, value in list(pending.items()):
            if time.monotonic() - value[3] > 600:
                pending.pop(key, None)
        await message.answer(f'Yuqoridagi xabar {count} ta foydalanuvchiga yuboriladi. Tasdiqlaysizmi? (10 daqiqa amal qiladi.)', reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[
            types.InlineKeyboardButton(text='✅ Yuborish', callback_data=f'send:{token}'),
            types.InlineKeyboardButton(text='❌ Bekor qilish', callback_data=f'cancel:{token}')]]))
    except Exception:
        log.exception('Broadcast preview failed')
        await message.answer('Xabarni tayyorlab bo‘lmadi. Oddiy matn, rasm yoki video bilan qayta urinib ko‘ring; baza sozlamasini ham tekshiring.')

async def send_broadcast(bot, admin_id, chat_id, message_id):
    sent = blocked = failed = 0
    last_id = 0
    try:
        while True:
            async with await connect() as conn:
                cur = await conn.execute('SELECT user_id FROM bot_users WHERE can_message AND user_id > %s ORDER BY user_id LIMIT 200', (last_id,))
                users = await cur.fetchall()
            if not users:
                break
            for (user_id,) in users:
                last_id = user_id
                try:
                    for attempt in range(3):
                        try:
                            await bot.copy_message(user_id, chat_id, message_id)
                            sent += 1
                            break
                        except TelegramRetryAfter as exc:
                            if attempt == 2:
                                failed += 1
                            else:
                                await asyncio.sleep(exc.retry_after + 1)
                except TelegramForbiddenError:
                    blocked += 1
                    async with await connect() as conn:
                        await conn.execute('UPDATE bot_users SET can_message=FALSE WHERE user_id=%s', (user_id,))
                except TelegramAPIError:
                    failed += 1
                await asyncio.sleep(0.06)
        await bot.send_message(admin_id, f'✅ Yuborish yakunlandi.\nYetkazildi: {sent}\nBotni bloklagan: {blocked}\nBoshqa xatolar: {failed}')
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception('Broadcast interrupted')
        await bot.send_message(admin_id, f'Yuborish to‘xtadi. Yetkazilgan: {sent}. Takror yuborish ayrim odamlarga ikki marta xabar yetkazishi mumkin.')
    finally:
        running.discard(admin_id)

@router.callback_query(F.data.startswith('send:') | F.data.startswith('cancel:'))
async def confirm(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer('Ruxsat yo‘q.', show_alert=True)
        return
    action, token = callback.data.split(':', 1)
    item = pending.get(token)
    if not item or item[0] != callback.from_user.id or time.monotonic() - item[3] > 600:
        await callback.answer('Tasdiqlash muddati tugagan yoki allaqachon bajarilgan.', show_alert=True)
        return
    if action == 'send' and running:
        await callback.answer('Boshqa yuborish hali tugamagan.', show_alert=True)
        return
    pending.pop(token, None)
    if action == 'send':
        running.add(item[0])
        task = asyncio.create_task(send_broadcast(callback.bot, item[0], item[1], item[2]))
        tasks.add(task)
        task.add_done_callback(tasks.discard)
    await callback.answer('Yuborish boshlandi.' if action == 'send' else 'Bekor qilindi.')
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)

async def shutdown():
    for task in list(tasks):
        task.cancel()
    if tasks:
        await asyncio.gather(*list(tasks), return_exceptions=True)
