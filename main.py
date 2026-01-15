import os
import sqlite3
import time
import random
import asyncio
import logging
import aiohttp
from urllib.parse import quote
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- SECURE CONFIGURATION ---
# Use Environment Variables for privacy. Set these in your hosting panel (Render/Koyeb).
API_TOKEN = os.getenv("API_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
GPLINKS_API = os.getenv("GPLINKS_API")
SHORTENER_URL = f"https://api.gplinks.com/api?api={GPLINKS_API}&url="
DELETE_TIME = 3600  # 1 Hour

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# --- DATABASE LOGIC ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    # Table for multiple video support (Privacy update: slug-based storage)
    conn.execute('''CREATE TABLE IF NOT EXISTS videos 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT, file_id TEXT)''')
    # Table for users (Added join_date for privacy-safe analytics)
    conn.execute('''CREATE TABLE IF NOT EXISTS users 
                    (id TEXT PRIMARY KEY, vids INTEGER DEFAULT 0, verified_until REAL DEFAULT 0, join_date TEXT)''')
    conn.commit()
    conn.close()

# --- STARTUP ANIMATION ---
async def startup_animation():
    me = await bot.get_me()
    print("\n" + "═"*45)
    print(f" 🚀 DesiKhatta System: PRIVACY MODE ENABLED")
    print(f" ✅ Bot is LIVE: @{me.username}")
    print("═"*45 + "\n")

# --- CORE LOGIC ---

@dp.message(Command("start"))
async def start_handler(message: types.Message, command: CommandObject):
    user_id = str(message.from_user.id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    conn = sqlite3.connect('bot_data.db')
    user = conn.execute("SELECT vids, verified_until FROM users WHERE id=?", (user_id,)).fetchone()
    
    if not user:
        conn.execute("INSERT INTO users (id, vids, verified_until, join_date) VALUES (?, 0, 0, ?)", (user_id, today))
        conn.commit()
        user = (0, 0, 0, today)
    
    # 1. Welcome Message
    if not command.args:
        welcome_pics = [f for f in os.listdir('welcome_pics') if f.endswith(('.png', '.jpg', '.jpeg'))] if os.path.exists('welcome_pics') else []
        caption = (
            "<b>🔥 Welcome to DesiKhatta Premium! 🔥</b>\n\n"
            "📥 <i>The ultimate bot for high-speed video streaming.</i>\n\n"
            "✅ <b>Anti-Save Protection Enabled</b>\n"
            "✅ <b>Self-destructing links</b>"
        )
        if welcome_pics:
            photo = FSInputFile(os.path.join('welcome_pics', random.choice(welcome_pics)))
            await message.answer_photo(photo, caption=caption, parse_mode="HTML")
        else:
            await message.answer(caption, parse_mode="HTML")
        conn.close()
        return

    # 2. Verification Logic
    if command.args == "verify":
        conn.execute("UPDATE users SET verified_until=? WHERE id=?", (time.time() + 86400, user_id))
        conn.commit()
        conn.close()
        return await message.answer("✅ <b>Verification Success!</b>\n24 Hours VIP Access Unlocked!", parse_mode="HTML")

    # 3. Ad System (Privacy: Secure API Call)
    vids_count, verified_until = user[0], user[1]
    if vids_count >= 1 and time.time() > verified_until:
        fetching_ad = await message.answer("🔐 <b>Generating secure link...</b>", parse_mode="HTML")
        me = await bot.get_me()
        bot_link = f"https://t.me/{me.username}?start=verify"
        api_call = f"{SHORTENER_URL}{quote(bot_link)}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(api_call, timeout=10) as response:
                    res_data = await response.json()
                    await fetching_ad.delete()
                    if res_data.get("status") == "success":
                        shortlink = res_data.get("shortenedUrl")
                        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔓 Verify to Watch", url=shortlink)]])
                        conn.close()
                        return await message.answer("⚠️ <b>Trial Expired!</b>\nPlease verify to unlock more content.", reply_markup=kb, parse_mode="HTML")
            except Exception:
                await fetching_ad.edit_text("❌ Connection Secure Error. Try again.")
                conn.close()
                return

    # 4. Content Fetching (Privacy: protect_content=True)
    res = conn.execute("SELECT file_id FROM videos WHERE slug=?", (command.args,)).fetchall()
    if res:
        conn.execute("UPDATE users SET vids=vids+1 WHERE id=?", (user_id,))
        conn.commit()
        
        warn = await message.answer(f"🚀 <b>Success!</b> Video will auto-delete in {DELETE_TIME//60} mins.", parse_mode="HTML")
        
        for row in res:
            f_id = row[0]
            # PRIVACY: protect_content prevents forwarding and saving
            vid = await bot.send_video(message.chat.id, f_id, protect_content=True, caption="🔞 Join @DesiKhatta for more")
            
            run_at = datetime.now() + timedelta(seconds=DELETE_TIME)
            scheduler.add_job(bot.delete_message, 'date', run_date=run_at, args=[message.chat.id, vid.message_id])
            scheduler.add_job(bot.delete_message, 'date', run_date=run_at, args=[message.chat.id, warn.message_id])
    else:
        await message.answer("❌ <b>Error: Content not found or expired.</b>", parse_mode="HTML")
    conn.close()

# --- ADMIN COMMANDS ---

@dp.message(Command("adminak"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: types.Message):
    conn = sqlite3.connect('bot_data.db')
    u = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    v = conn.execute("SELECT COUNT(DISTINCT slug) FROM videos").fetchone()[0]
    conn.close()
    
    text = (f"🛠 <b>SECURE ADMIN PANEL</b>\n\n"
            f"👤 Users: {u}\n"
            f"🎥 Unique Slugs: {v}\n\n"
            "• <code>/add name id1 id2...</code>\n"
            "• <code>/del name</code>\n"
            "• <code>/broadcast text</code>")
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("add"), F.from_user.id == ADMIN_ID)
async def admin_add(message: types.Message, command: CommandObject):
    if not command.args: return
    try:
        parts = command.args.split()
        slug = parts[0]
        f_ids = parts[1:]
        conn = sqlite3.connect('bot_data.db')
        for fid in f_ids:
            conn.execute("INSERT INTO videos (slug, file_id) VALUES (?, ?)", (slug, fid))
        conn.commit()
        conn.close()
        me = await bot.get_me()
        await message.answer(f"✅ <b>Added {len(f_ids)} files to:</b> <code>{slug}</code>\n🔗 <code>https://t.me/{me.username}?start={slug}</code>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Error: {e}")

@dp.message(Command("broadcast"), F.from_user.id == ADMIN_ID)
async def admin_broadcast(message: types.Message, command: CommandObject):
    if not command.args: return
    
    conn = sqlite3.connect('bot_data.db')
    users = conn.execute("SELECT id FROM users").fetchall()
    conn.close()
    
    sent, blocked = 0, 0
    msg = await message.answer(f"⏳ Broadcasting to {len(users)} users...")
    
    for (uid,) in users:
        try:
            await bot.send_message(uid, command.args, parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.05)
        except (TelegramForbiddenError, TelegramBadRequest):
            blocked += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            await bot.send_message(uid, command.args, parse_mode="HTML")
            sent += 1
    
    await msg.edit_text(f"📢 <b>Broadcast Complete</b>\n✅ Sent: {sent}\n🚫 Blocked: {blocked}")

@dp.message(F.video, F.from_user.id == ADMIN_ID)
async def capture(message: types.Message):
    await message.answer(f"📥 <b>File ID:</b>\n<code>{message.video.file_id}</code>", parse_mode="HTML")

# --- STARTUP ---
async def main():
    init_db()
    await startup_animation()
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    asyncio.run(main())
