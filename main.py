from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    CallbackQueryHandler, MessageHandler, filters, ConversationHandler
)
import logging
import requests
from fastapi import FastAPI, Request
import asyncio
import tempfile
import os
import base64
import uvicorn

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants
TOKEN = "7158305425:AAHvpcyKIpucMqRxkxbK0o9INLJEetJ0A5o"
TEXT_API_URL = 'https://text.pollinations.ai/'
WEBHOOK_URL = "https://medical-assistant-rum5.onrender.com/webhook"
SYSTEM_MESSAGE = (
    "شما دستیار هوشمند PlatoDex هستید و درمورد پلاتو به کاربران کمک میکنید. "
    "به صورت خودمونی، نسل Z، باحال و با طنز جواب بده."
)

# State
AI_CHAT_USERS = set()

# FastAPI + Telegram
app = FastAPI()
application = Application.builder().token(TOKEN).build()

@app.post("/webhook")
async def webhook(request: Request):
    update = await request.json()
    update_obj = Update.de_json(update, application.bot)
    await application.initialize()
    asyncio.create_task(application.process_update(update_obj))
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "AI Chat Bot is running!"}

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    keyboard = [[InlineKeyboardButton("🤖 شروع چت با هوش مصنوعی", callback_data="chat_with_ai")]]
    await update.message.reply_text(
        f"سلام {user_name}! به ربات چت هوش مصنوعی خوش اومدی!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# AI Chat button callback
async def chat_with_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    AI_CHAT_USERS.add(user_id)
    context.user_data.clear()
    context.user_data["mode"] = "ai_chat"
    context.user_data["chat_history"] = []
    keyboard = [[InlineKeyboardButton("🏠 بازگشت به خانه", callback_data="back_to_home")]]
    await query.edit_message_text(
        "🤖 چت با هوش مصنوعی فعال شد! هر چی می‌خوای بپرس، من هستم!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Button navigation
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    if data == "chat_with_ai":
        return await chat_with_ai(update, context)
    elif data == "back_to_home":
        return await start(update.callback_query, context)

# Text message handler (private or group)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message
    text = message.text.lower()

    trigger_words = ["سلام", "ربات", "پلاتو"]
    should_reply = (
        user_id in AI_CHAT_USERS or
        message.chat.type != "private" and (
            any(w in text for w in trigger_words) or message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id
        )
    )

    if not should_reply:
        return

    chat_history = context.user_data.get("chat_history", [])
    chat_history.append({"role": "user", "content": message.text})
    context.user_data["chat_history"] = chat_history

    payload = {
        "messages": [{"role": "system", "content": SYSTEM_MESSAGE}] + chat_history,
        "model": "openai-large",
        "seed": 42,
        "jsonMode": False
    }

    try:
        response = requests.post(TEXT_API_URL, json=payload, timeout=20)
        if response.status_code == 200:
            ai_response = response.text.strip()
            chat_history.append({"role": "assistant", "content": ai_response})
            context.user_data["chat_history"] = chat_history
            await message.reply_text(ai_response, reply_to_message_id=message.message_id)
        else:
            await message.reply_text("خطایی رخ داد! بعداً امتحان کن.", reply_to_message_id=message.message_id)
    except Exception as e:
        logger.error(f"AI error: {e}")
        await message.reply_text("یه مشکلی پیش اومد. بعداً دوباره امتحان کن!", reply_to_message_id=message.message_id)

# Photo handler
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AI_CHAT_USERS:
        return

    photo = update.message.photo[-1]
    file = await photo.get_file()
    file_path = tempfile.mktemp(suffix=".jpg")
    await file.download_to_drive(file_path)

    with open(file_path, "rb") as f:
        encoded_image = base64.b64encode(f.read()).decode("utf-8")
    os.remove(file_path)

    prompt = "What is in this image?"
    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": prompt}
        ],
        "image": encoded_image,
        "model": "openai-large",
        "jsonMode": False
    }

    try:
        response = requests.post(TEXT_API_URL, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.text.strip()
            await update.message.reply_text(f"تجزیه و تحلیل تصویر:\n{result}", reply_to_message_id=update.message.message_id)
        else:
            await update.message.reply_text("نتونستم عکسو بررسی کنم.", reply_to_message_id=update.message.message_id)
    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        await update.message.reply_text("یه مشکلی پیش اومد موقع بررسی عکس.", reply_to_message_id=update.message.message_id)

# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(callback_router, pattern=".*"))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(MessageHandler(filters.PHOTO, handle_image))

# Webhook setup + FastAPI startup
if __name__ == "__main__":
    async def main():
        bot = Bot(token=TOKEN)
        await bot.set_webhook(url=WEBHOOK_URL)
        print("Webhook set successfully.")

    asyncio.run(main())
    uvicorn.run("main:app", host="0.0.0.0")
            
