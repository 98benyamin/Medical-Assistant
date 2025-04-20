import asyncio
import logging
import requests
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram.error import TelegramError
from bs4 import BeautifulSoup
from fastapi import FastAPI, Request
from fastapi.responses import Response
import uvicorn
from threading import Lock

# تنظیم لاگ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# توکن و وب‌هوک جدید
TOKEN = '8123059269:AAHlvWT2ZZ3iC1ICRkmiuwTjBHvdM-NLy18'
WEBHOOK_URL = 'https://medical-assistant-rum5.onrender.com/webhook'

# آدرس API متنی و تحلیل تصویر
TEXT_API_URL = 'https://text.pollinations.ai/openai'

# شناسه کانال
CHANNEL_ID = '@bbbyyyrt'
CHANNEL_LINK = 'https://t.me/bbbyyyrt'

# مسیر فایل دیتابیس
DATABASE_FILE = 'database.json'

# تابع‌های مدیریت دیتابیس
def load_database():
    """بارگذاری اطلاعات از فایل دیتابیس"""
    if os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "users": {},
        "statistics": {
            "total_messages": 0,
            "total_users": 0,
            "total_photos": 0
        },
        "admins": [6753257929]
    }

def save_database(data):
    """ذخیره اطلاعات در فایل دیتابیس"""
    with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def update_user_stats(user_id, username=None, first_name=None):
    """بروزرسانی آمار کاربر"""
    db = load_database()
    if str(user_id) not in db["users"]:
        db["users"][str(user_id)] = {
            "username": username,
            "first_name": first_name,
            "join_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message_count": 0,
            "photo_count": 0,
            "last_activity": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        db["statistics"]["total_users"] += 1
    
    db["users"][str(user_id)]["last_activity"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_database(db)
    return db

def increment_message_count(user_id, is_photo=False):
    """افزایش تعداد پیام‌های کاربر"""
    db = load_database()
    if str(user_id) in db["users"]:
        if is_photo:
            db["users"][str(user_id)]["photo_count"] += 1
            db["statistics"]["total_photos"] += 1
        else:
            db["users"][str(user_id)]["message_count"] += 1
        db["statistics"]["total_messages"] += 1
        save_database(db)

def is_admin(user_id):
    """بررسی ادمین بودن کاربر"""
    db = load_database()
    return user_id in db["admins"]

# دستورات ادمین
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش پنل ادمین"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔️ شما دسترسی به این بخش را ندارید!")
        return

    db = load_database()
    stats = db["statistics"]
    active_users = sum(1 for user in db["users"].values() 
                      if (datetime.now() - datetime.strptime(user["last_activity"], "%Y-%m-%d %H:%M:%S")).days < 7)

    stats_message = (
        "📊 آمار ربات:\n\n"
        f"👥 تعداد کل کاربران: {stats['total_users']}\n"
        f"👤 کاربران فعال (7 روز اخیر): {active_users}\n"
        f"💬 تعداد کل پیام‌ها: {stats['total_messages']}\n"
        f"🖼 تعداد کل تصاویر: {stats['total_photos']}\n"
    )

    keyboard = [
        [InlineKeyboardButton("📊 آمار تفصیلی", callback_data="detailed_stats")],
        [InlineKeyboardButton("👥 لیست کاربران", callback_data="users_list")]
    ]
    await update.message.reply_text(stats_message, reply_markup=InlineKeyboardMarkup(keyboard))

async def detailed_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش آمار تفصیلی"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.edit_message_text("⛔️ شما دسترسی به این بخش را ندارید!")
        return

    db = load_database()
    users = db["users"]
    
    # محاسبه آمار
    today_active = sum(1 for user in users.values() 
                      if (datetime.now() - datetime.strptime(user["last_activity"], "%Y-%m-%d %H:%M:%S")).days < 1)
    week_active = sum(1 for user in users.values() 
                     if (datetime.now() - datetime.strptime(user["last_activity"], "%Y-%m-%d %H:%M:%S")).days < 7)
    month_active = sum(1 for user in users.values() 
                      if (datetime.now() - datetime.strptime(user["last_activity"], "%Y-%m-%d %H:%M:%S")).days < 30)

    stats_message = (
        "📊 آمار تفصیلی:\n\n"
        f"📅 کاربران فعال امروز: {today_active}\n"
        f"📆 کاربران فعال هفته: {week_active}\n"
        f"📅 کاربران فعال ماه: {month_active}\n"
        f"💬 میانگین پیام هر کاربر: {db['statistics']['total_messages'] / len(users) if users else 0:.1f}\n"
        f"🖼 میانگین تصویر هر کاربر: {db['statistics']['total_photos'] / len(users) if users else 0:.1f}\n"
    )

    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_admin")]]
    await query.edit_message_text(stats_message, reply_markup=InlineKeyboardMarkup(keyboard))

async def users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش لیست کاربران"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.edit_message_text("⛔️ شما دسترسی به این بخش را ندارید!")
        return

    db = load_database()
    users = db["users"]
    
    # مرتب‌سازی کاربران بر اساس آخرین فعالیت
    sorted_users = sorted(users.items(), 
                         key=lambda x: datetime.strptime(x[1]["last_activity"], "%Y-%m-%d %H:%M:%S"),
                         reverse=True)[:10]  # نمایش 10 کاربر آخر

    users_message = "👥 آخرین کاربران فعال:\n\n"
    for user_id, user_data in sorted_users:
        users_message += (
            f"👤 نام: {user_data['first_name']}\n"
            f"🆔 یوزرنیم: @{user_data['username'] if user_data['username'] else 'ندارد'}\n"
            f"💬 تعداد پیام: {user_data['message_count']}\n"
            f"🖼 تعداد تصویر: {user_data['photo_count']}\n"
            f"⏱ آخرین فعالیت: {user_data['last_activity']}\n"
            "➖➖➖➖➖➖➖➖\n"
        )

    keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_admin")]]
    await query.edit_message_text(users_message, reply_markup=InlineKeyboardMarkup(keyboard))

async def back_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بازگشت به پنل ادمین"""
    query = update.callback_query
    await query.answer()
    await admin_panel(update, context)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ارسال پیام خوش‌آمدگویی با بررسی عضویت در کانال"""
    user = update.effective_user
    user_id = user.id
    
    # بروزرسانی آمار کاربر
    update_user_stats(user_id, user.username, user.first_name)

    if user_id in AI_CHAT_USERS:
        AI_CHAT_USERS.remove(user_id)
    context.user_data.clear()

    is_member = await check_channel_membership(context.bot, user_id)
    if not is_member:
        welcome_message = clean_text(
            f"سلام {user.first_name}!\nبرای استفاده از دستیار پزشکی، باید تو کانال عضو بشی! 🏥\n"
            "لطفاً تو کانال عضو شو و بعد دکمه 'عضو شدم' رو بزن! 🚑"
        )
        keyboard = [
            [InlineKeyboardButton("عضو کانال شو 📢", url=CHANNEL_LINK)],
            [InlineKeyboardButton("عضو شدم! ✅", callback_data="check_membership")]
        ]
        await update.message.reply_text(welcome_message, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    welcome_message = clean_text(
        f"سلام {user.first_name}!\nبه دستیار پزشکی هوشمند خوش اومدی! 🩺\n"
        "می‌تونی درباره بیماری‌ها، داروها، برگه آزمایش یا نوار قلب سؤال کنی. چی تو سرته؟ 🧑🏻‍⚕"
    )
    keyboard = [
        [InlineKeyboardButton("شروع مشاوره پزشکی 🤖", callback_data="chat_with_ai")]
    ]
    await update.message.reply_text(welcome_message, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت پیام‌های متنی کاربر در حالت چت با هوش مصنوعی"""
    user = update.effective_user
    user_id = user.id
    
    # بروزرسانی آمار کاربر
    update_user_stats(user_id, user.username, user.first_name)
    increment_message_count(user_id)
    
    if user_id not in AI_CHAT_USERS or context.user_data.get("mode") != "ai_chat":
        return

    message_id = update.message.message_id
    with PROCESSING_LOCK:
        if message_id in PROCESSED_MESSAGES:
            logger.warning(f"پیام تکراری با message_id: {message_id} - نادیده گرفته شد")
            return
        PROCESSED_MESSAGES.add(message_id)

    chat_id = update.message.chat_id
    user_message = update.message.text
    chat_history = context.user_data.get("chat_history", [])
    chat_history.append({"role": "user", "content": user_message})
    context.user_data["chat_history"] = chat_history

    # ارسال پیام موقت
    temp_message = await update.message.reply_text(clean_text("🩺"))

    payload = {
        "model": "openai-large",
        "messages": [
            {"role": "system", "content": SYSTEM_MESSAGE}
        ] + chat_history,
        "max_tokens": 300,
        "seed": 42,
        "json_mode": False
    }

    keyboard = [[InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="back_to_home")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        response = requests.post(TEXT_API_URL, json=payload, timeout=20)
        # حذف پیام موقت
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=temp_message.message_id)
        except TelegramError as e:
            logger.error(f"خطا در حذف پیام موقت: {e}")

        if response.status_code == 200:
            response_data = response.json()
            ai_response = response_data.get("choices", [{}])[0].get("message", {}).get("content", "پاسخی دریافت نشد!")
            ai_response = clean_text(ai_response.strip())
            chat_history.append({"role": "assistant", "content": ai_response})
            context.user_data["chat_history"] = chat_history
            await update.message.reply_text(ai_response, reply_markup=reply_markup)
        else:
            await update.message.reply_text(
                clean_text("اوپس، سیستم پزشکی‌مون یه لحظه قفل کرد! 🩺 لطفاً دوباره سؤالت رو بفرست. 😊"),
                reply_markup=reply_markup
            )
    except Exception as e:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=temp_message.message_id)
        except TelegramError as e:
            logger.error(f"خطا در حذف پیام موقت: {e}")
        logger.error(f"خطا در اتصال به API چت: {e}")
        await update.message.reply_text(
            clean_text("اوه، انگار ابزار تشخیص‌مون نیاز به بررسی داره! 💉 لطفاً دوباره سؤالت رو بفرست. 😊"),
            reply_markup=reply_markup
        )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت عکس‌های ارسالی و تحلیل با API Pollinations"""
    user = update.effective_user
    user_id = user.id
    
    # بروزرسانی آمار کاربر
    update_user_stats(user_id, user.username, user.first_name)
    increment_message_count(user_id, is_photo=True)
    
    if user_id not in AI_CHAT_USERS or context.user_data.get("mode") != "ai_chat":
        return

    message_id = update.message.message_id
    with PROCESSING_LOCK:
        if message_id in PROCESSED_MESSAGES:
            logger.warning(f"پیام تکراری با message_id: {message_id} - نادیده گرفته شد")
            return
        PROCESSED_MESSAGES.add(message_id)

    chat_id = update.message.chat_id
    keyboard = [[InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="back_to_home")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # ارسال پیام موقت
    temp_message = await update.message.reply_text(clean_text("🔬"))

    # دریافت عکس با بالاترین کیفیت
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_url = file.file_path

    # بررسی کپشن (اگر وجود دارد)
    caption = update.message.caption if update.message.caption else "این تصویر پزشکی (مثل برگه آزمایش یا نوار قلب) چیه؟ به‌صورت خلاصه و دقیق تحلیل کن! 🩺"

    # آماده‌سازی پیام برای تحلیل تصویر
    chat_history = context.user_data.get("chat_history", [])
    image_message = {
        "role": "user",
        "content": [
            {"type": "text", "text": caption},
            {"type": "image_url", "image_url": {"url": file_url}}
        ]
    }
    chat_history.append(image_message)
    context.user_data["chat_history"] = chat_history

    payload = {
        "model": "openai-large",
        "messages": [
            {"role": "system", "content": SYSTEM_MESSAGE}
        ] + chat_history,
        "max_tokens": 300,
        "seed": 42,
        "json_mode": False
    }

    try:
        response = requests.post(TEXT_API_URL, json=payload, timeout=20)
        # حذف پیام موقت
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=temp_message.message_id)
        except TelegramError as e:
            logger.error(f"خطا در حذف پیام موقت: {e}")

        if response.status_code == 200:
            response_data = response.json()
            ai_response = response_data.get("choices", [{}])[0].get("message", {}).get("content", "پاسخی دریافت نشد!")
            ai_response = clean_text(ai_response.strip())
            chat_history.append({"role": "assistant", "content": ai_response})
            context.user_data["chat_history"] = chat_history
            await update.message.reply_text(ai_response, reply_markup=reply_markup)
        else:
            await update.message.reply_text(
                clean_text("اوه، دستگاه تحلیل‌مون نیاز به تنظیم داره! 💉 لطفاً دوباره عکس رو بفرست. 🩻"),
                reply_markup=reply_markup
            )
    except Exception as e:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=temp_message.message_id)
        except TelegramError as e:
            logger.error(f"خطا در حذف پیام موقت: {e}")
        logger.error(f"خطا در تحلیل تصویر: {e}")
        await update.message.reply_text(
            clean_text("اوپس، اسکنر پزشکی‌مون یه لحظه خاموش شد! 🩺 لطفاً دوباره عکس رو بفرست. 😊"),
            reply_markup=reply_markup
        )

async def main():
    """راه‌اندازی ربات با وب‌هوک و سرور FastAPI"""
    global application
    try:
        # ساخت اپلیکیشن با توکن
        application = Application.builder().token(TOKEN).read_timeout(60).write_timeout(60).connect_timeout(60).build()

        # تنظیم وب‌هوک
        await application.bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Webhook روی {WEBHOOK_URL} تنظیم شد.")

        # اضافه کردن هندلرها
        application.add_handler(CommandHandler("start", start, filters=filters.ChatType.PRIVATE))
        application.add_handler(CommandHandler("admin", admin_panel, filters=filters.ChatType.PRIVATE))
        application.add_handler(CallbackQueryHandler(check_membership, pattern="^check_membership$"))
        application.add_handler(CallbackQueryHandler(chat_with_ai, pattern="^chat_with_ai$"))
        application.add_handler(CallbackQueryHandler(back_to_home, pattern="^back_to_home$"))
        application.add_handler(CallbackQueryHandler(detailed_stats, pattern="^detailed_stats$"))
        application.add_handler(CallbackQueryHandler(users_list, pattern="^users_list$"))
        application.add_handler(CallbackQueryHandler(back_to_admin, pattern="^back_to_admin$"))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_ai_message))
        application.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, handle_photo))

        # شروع ربات
        logger.info("در حال آماده‌سازی ربات...")
        await application.initialize()
        logger.info("در حال شروع ربات...")
        await application.start()

        # راه‌اندازی سرور FastAPI
        config = uvicorn.Config(app, host="0.0.0.0", port=8000)
        server = uvicorn.Server(config)
        await server.serve()

    except Exception as e:
        logger.error(f"خطا در راه‌اندازی ربات: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 
