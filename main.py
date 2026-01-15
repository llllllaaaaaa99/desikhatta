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
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- SECURE CONFIGURATION (Environment Variables) ---
# Set these in your Koyeb/Hosting Dashboard
API_TOKEN = os.getenv("API_TOKEN", "8574845770:AAEPnmibU8y0l2K8iaRlP-3Mt9gZfnIxE2c")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6824306713"))
GPLINKS_API = os.getenv("GPLINKS_API", "1d65d18e76422e83ab19c6866fb0399d184593d0")
SHORTENER_URL = f"https://api.gplinks.com/api?api={GPLINKS_API}&url="

# Channel Privacy: Users must join this to use the bot
CHANNEL_ID = os.getenv("CHANNEL_ID", "-100xxxxxxxxxx") # Add your channel ID
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/yourchannel")

DELETE_TIME = 3600  # 1 Hour

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# --- PRIVACY HELPER: FORCE SUBSCRIBE ---
async def is_subscribed(user_id: int):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False

# --- TERMINAL STARTUP ---
async def startup_animation():
    print("\n" + "═"*45)
    print(f" 🚀 Initializing Privacy-Enhanced System...")
    print(f" ✅ Bot is LIVE: @{(await bot.get_me()).username}")
    print("═"*45 + "\n")

# --- DATABASE LOGIC ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS videos (id TEXT PRIMARY KEY, file_id TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, vids INTEGER, verified_until REAL)''')
    conn.commit()
    conn.close()

# --- CORE LOGIC ---

@dp.message(Command("start"))
async def start_handler(message: types.Message, command: CommandObject):
    user_id = str(message.from_user.id)
    
    # Check Privacy: Force Sub
    if not await is_subscribed(message.from_user.id):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Join Channel to Unlock", url=CHANNEL_LINK)]
        ])
        return await message.answer("⚠️ <b>Access Denied!</b>\nYou must join our private channel to use this bot.", reply_markup=kb, parse_mode="HTML")

    conn = sqlite3.connect('bot_data.db')
    user = conn.execute("SELECT vids, verified_until FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        conn.execute("INSERT INTO users VALUES (?, 0, 0)", (user_id,))
        conn.commit()
        user = (0, 0)
    conn.close()

    if not command.args:
        # Welcome logic (same as before)
        welcome_pics = [f for f in os.listdir('welcome_pics') if f.endswith(('.png', '.jpg', '.jpeg'))] if os.path.exists('welcome_pics') else []
        caption = "<b>🔥 Welcome to DesiKhatta Premium! 🔥</b>"
        if welcome_pics:
            photo = FSInputFile(os.path.join('welcome_pics', random.choice(welcome_pics)))
            await message.answer_photo(photo, caption=caption, parse_mode="HTML")
        else:
            await message.answer(caption, parse_mode="HTML")
        return

    # Verification Logic
    if command.args == "verify":
        conn = sqlite3.connect('bot_data.db')
        conn.execute("UPDATE users SET verified_until=? WHERE id=?", (time.time() + 86400, user_id))
        conn.commit()
        conn.close()
        return await message.answer("✅ <b>Verification Success!</b>\n24 Hours VIP Access Unlocked!", parse_mode="HTML")

    vids_count, verified_until = user
    if vids_count > 0 and time.time() > verified_until:
        # GPLinks generation (same logic, using secure API key)
        fetching_ad = await message.answer("🔐 <b>Generating secure link...</b>", parse_mode="HTML")
        me = await bot.get_me()
        bot_link = f"https://t.me/{me.username}?start=verify"
        api_call = f"{SHORTENER_URL}{quote(bot_link)}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_call) as response:
                res_data = await response.json()
                await fetching_ad.delete()
                if res_data.get("status") == "success":
                    shortlink = res_data.get("shortenedUrl")
                    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔓 Verify to Watch", url=shortlink)]])
                    return await message.answer("⚠️ <b>Trial Expired!</b>", reply_markup=kb, parse_mode="HTML")

    # Fetching Logic
    fetching_msg = await message.answer("🔍 <b>Searching Database...</b>", parse_mode="HTML")
    conn = sqlite3.connect('bot_data.db')
    res = conn.execute("SELECT file_id FROM videos WHERE id=?", (command.args,)).fetchone()
    
    if res:
        f_id = res[0]
        await fetching_msg.delete()
        warn = await message.answer(f"🚀 <b>Success!</b> Auto-delete in 60 mins.", parse_mode="HTML")
        vid = await bot.send_video(message.chat.id, f_id, protect_content=True) # protect_content=True adds privacy
        
        conn.execute("UPDATE users SET vids=vids+1 WHERE id=?", (user_id,))
        conn.commit()
        
        run_at = datetime.now() + timedelta(seconds=DELETE_TIME)
        scheduler.add_job(bot.delete_message, 'date', run_date=run_at, args=[message.chat.id, vid.message_id])
        scheduler.add_job(bot.delete_message, 'date', run_date=run_at, args=[message.chat.id, warn.message_id])
    else:
        await fetching_msg.edit_text("❌ <b>Error: Video not found.</b>", parse_mode="HTML")
    conn.close()

# --- ADMIN COMMANDS ---

@dp.message(Command("adminak"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: types.Message):
    conn = sqlite3.connect('bot_data.db')
    u = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    v = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    conn.close()
    await message.answer(f"🛠 <b>ADMIN PANEL</b>\n👤 Users: {u}\n🎥 Videos: {v}", parse_mode="HTML")

@dp.message(Command("add"), F.from_user.id == ADMIN_ID)
async def admin_add(message: types.Message, command: CommandObject):
    try:
        # Enhancement: Allow multiple file_ids in one command
        # Usage: /add slug fileid1 fileid2...
        parts = command.args.split()
        name = parts[0]
        f_ids = parts[1:] 
        
        conn = sqlite3.connect('bot_data.db')
        for f_id in f_ids:
            conn.execute("INSERT OR REPLACE INTO videos VALUES (?, ?)", (name, f_id))
        conn.commit()
        conn.close()
        await message.answer(f"✅ <b>Added {len(f_ids)} video(s) to:</b> {name}", parse_mode="HTML")
    except Exception:
        await message.answer("Usage: /add name file_id")

# --- STARTUP ---
async def main():
    init_db()
    await startup_animation()
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    asyncio.run(main())
