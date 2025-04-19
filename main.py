from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters, ConversationHandler import logging import requests from fastapi import FastAPI, Request import asyncio import tempfile import os


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO) logger = logging.getLogger(name)

TOKEN = '7158305425:AAHvpcyKIpucMqRxkxbK0o9INLJEetJ0A5o' TEXT_API_URL = 'https://text.pollinations.ai/' AI_CHAT_USERS = set() SYSTEM_MESSAGE = ( "شما دستیار هوشمند PlatoDex هستید و درمورد پلاتو به کاربران کمک میکنید. به صورت خودمونی، نسل Z، باحال و با طنز جواب بده." )

app = FastAPI() application = None

@app.post("/webhook") async def webhook(request: Request): global application update = await request.json() update_obj = Update.de_json(update, application.bot) update_id = update_obj.update_id asyncio.create_task(application.process_update(update_obj)) return {"status": "ok"}

@app.get("/") async def root(): return {"message": "AI Chat Bot is running!"}

async def chat_with_ai(update: Update, context: ContextTypes.DEFAULT_TYPE): query = update.callback_query await query.answer() user_id = update.effective_user.id AI_CHAT_USERS.add(user_id) context.user_data.clear() context.user_data["mode"] = "ai_chat" context.user_data["chat_history"] = [] keyboard = [[InlineKeyboardButton("🏠 بازگشت به خانه", callback_data="back_to_home")]] reply_markup = InlineKeyboardMarkup(keyboard) await query.edit_message_text( "🤖 چت با هوش مصنوعی فعال شد! هر چی می‌خوای بپرس، من هستم!", reply_markup=reply_markup ) return ConversationHandler.END

async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE): user_id = update.effective_user.id if user_id not in AI_CHAT_USERS or context.user_data.get("mode") != "ai_chat": return ConversationHandler.END

user_message = update.message.text
chat_history = context.user_data.get("chat_history", [])
chat_history.append({"role": "user", "content": user_message})
context.user_data["chat_history"] = chat_history

payload = {
    "messages": [
        {"role": "system", "content": SYSTEM_MESSAGE}
    ] + chat_history,
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
        await update.message.reply_text(ai_response)
    else:
        await update.message.reply_text("خطایی رخ داد! لطفاً بعداً امتحان کن.")
except Exception as e:
    logger.error(f"API error: {e}")
    await update.message.reply_text("خطایی پیش اومد. بعداً امتحان کن!")
return ConversationHandler.END

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE): user_id = update.effective_user.id if user_id not in AI_CHAT_USERS: return

photo = update.message.photo[-1]
file = await photo.get_file()
file_path = tempfile.mktemp(suffix=".jpg")
await file.download_to_drive(file_path)

with open(file_path, "rb") as f:
    image_bytes = f.read()
os.remove(file_path)

base64_image = image_bytes.encode("base64") if hasattr(image_bytes, "encode") else image_bytes
prompt = "What is in this image?"

payload = {
    "messages": [
        {"role": "system", "content": SYSTEM_MESSAGE},
        {"role": "user", "content": prompt}
    ],
    "image": base64_image,
    "model": "openai-large",
    "jsonMode": False
}

try:
    response = requests.post(TEXT_API_URL, json=payload, timeout=30)
    if response.status_code == 200:
        result = response.text.strip()
        await update.message.reply_text(f"تجزیه و تحلیل تصویر:

{result}") else: await update.message.reply_text("نتونستم عکسو بررسی کنم! لطفاً بعداً امتحان کن.") except Exception as e: logger.error(f"Image analysis error: {e}") await update.message.reply_text("یه مشکلی پیش اومد موقع بررسی عکس. 😕")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): user_name = update.message.from_user.first_name welcome_message = f"سلام {user_name}! به ربات چت هوش مصنوعی خوش اومدی!" keyboard = [[InlineKeyboardButton("🤖 شروع چت با هوش مصنوعی", callback_data="chat_with_ai")]] await update.message.reply_text(welcome_message, reply_markup=InlineKeyboardMarkup(keyboard))

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE): data = update.callback_query.data if data == "chat_with_ai": return await chat_with_ai(update, context) elif data == "back_to_home": return await start(update.callback_query, context)


app_handler_list = [ CommandHandler("start", start), CallbackQueryHandler(callback_router), MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai_message), MessageHandler(filters.PHOTO, handle_image) ]

