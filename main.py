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
from aiogram.exceptions import TelegramBadRequest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- CONFIGURATION ---
API_TOKEN = "8574845770:AAEPnmibU8y0l2K8iaRlP-3Mt9gZfnIxE2c"
ADMIN_ID = 6824306713
SHORTENER_URL = "https://api.gplinks.com/api?api=1d65d18e76422e83ab19c6866fb0399d184593d0&url="
DELETE_TIME = 3600  # 1 Hour

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# --- TERMINAL STARTUP ANIMATION ---
async def startup_animation():
    print("\n" + "═"*45)
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    for i in range(15):
        frame = frames[i % len(frames)]
        print(f"\r {frame}  🚀 Initializing DesiKhatta System...", end="")
        await asyncio.sleep(0.1)
    print(f"\r ✅  Bot is LIVE: @{(await bot.get_me()).username}          ")
    print("═"*45 + "\n")

# --- DATABASE LOGIC ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS videos (id TEXT PRIMARY KEY, file_id TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, vids INTEGER, verified_until REAL)''')
    conn.commit()
    conn.close()

# --- CORE LOGIC ---

@dp.message(Command("myid"))
async def cmd_myid(message: types.Message):
    await message.answer(f"🆔 Your Admin ID: <code>{message.from_user.id}</code>", parse_mode="HTML")

@dp.message(Command("start"))
async def start_handler(message: types.Message, command: CommandObject):
    user_id = str(message.from_user.id)
    
    conn = sqlite3.connect('bot_data.db')
    user = conn.execute("SELECT vids, verified_until FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        conn.execute("INSERT INTO users VALUES (?, 0, 0)", (user_id,))
        conn.commit()
        user = (0, 0)
    conn.close()

    if not command.args:
        welcome_pics = [f for f in os.listdir('welcome_pics') if f.endswith(('.png', '.jpg', '.jpeg'))]
        caption = (
            "<b>🔥 Welcome to DesiKhatta Premium! 🔥</b>\n\n"
            "📥 <i>The ultimate bot for high-speed video streaming.</i>\n\n"
            "✅ Safe & Secure\n"
            "✅ Self-destructing links\n\n"
            "👉 <b>Just click a link shared by our admin to watch!</b>"
        )
        if welcome_pics:
            photo = FSInputFile(os.path.join('welcome_pics', random.choice(welcome_pics)))
            await message.answer_photo(photo, caption=caption, parse_mode="HTML")
        else:
            await message.answer(caption, parse_mode="HTML")
        return

    if command.args == "verify":
        conn = sqlite3.connect('bot_data.db')
        conn.execute("UPDATE users SET verified_until=? WHERE id=?", (time.time() + 86400, user_id))
        conn.commit()
        conn.close()
        return await message.answer("✅ <b>Verification Success!</b>\n24 Hours VIP Access Unlocked!", parse_mode="HTML")

    vids_count, verified_until = user
    if vids_count > 0 and time.time() > verified_until:
        # ASYNC SHORTLINK GENERATION
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
                    return await message.answer("⚠️ <b>Trial Expired!</b>\nPlease verify to unlock the video.", reply_markup=kb, parse_mode="HTML")
                else:
                    return await message.answer("❌ Shortener API Error. Contact Admin.")

    # VIDEO FETCHING ANIMATION
    fetching_msg = await message.answer("🔍 <b>Searching Database...</b>", parse_mode="HTML")
    await asyncio.sleep(0.7)
    await fetching_msg.edit_text("⚡ <b>Bypassing Encryption...</b>", parse_mode="HTML")
    
    conn = sqlite3.connect('bot_data.db')
    res = conn.execute("SELECT file_id FROM videos WHERE id=?", (command.args,)).fetchone()
    
    if res:
        f_id = res[0]
        await fetching_msg.delete()
        
        warn = await message.answer(f"🚀 <b>Success!</b> Video will auto-delete in {DELETE_TIME//60} mins.", parse_mode="HTML")
        vid = await bot.send_video(message.chat.id, f_id, protect_content=True, caption="🔞 For More")
        kbt = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔓 More to Watch", url="https://t.me/+50GaDliHPXE1YjRl")]])
        await message.answer("⚠️ <b>Please join to watch more video.</b>", reply_markup=kbt, parse_mode="HTML")

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
    text = (f"🛠 <b>ADMIN PANEL</b>\n\n👤 Users: {u}\n🎥 Videos: {v}\n\n"
            "<code>/add name id</code>\n<code>/del name</code>\n<code>/broadcast text</code>")
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("add"), F.from_user.id == ADMIN_ID)
async def admin_add(message: types.Message, command: CommandObject):
    try:
        name, f_id = command.args.split()
        conn = sqlite3.connect('bot_data.db')
        conn.execute("INSERT OR REPLACE INTO videos VALUES (?, ?)", (name, f_id))
        conn.commit()
        conn.close()
        me = await bot.get_me()
        await message.answer(f"✅ <b>Link:</b> <code>https://t.me/{me.username}?start={name}</code>", parse_mode="HTML")
    except: await message.answer("Usage: /add name file_id")

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
