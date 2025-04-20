import asyncio
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram.error import TelegramError
from bs4 import BeautifulSoup  # اضافه شده اما استفاده نشده
from fastapi import FastAPI, Request
import uvicorn
from threading import Lock

# تنظیم لاگ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# توکن و وب‌هوک جدید
TOKEN = '8123059269:AAHlvWT2ZZ3iC1ICRkmiuwTjBHvdM-NLy18'
WEBHOOK_URL = 'https://medical-assistant-rum5.onrender.com/webhook'

# آدرس API چت و آنالیز تصویر
TEXT_API_URL = 'https://text.pollinations.ai/'
IMAGE_API_URL = 'https://image.pollinations.ai/analyze'

# شناسه کانال
CHANNEL_ID = '@bbbyyyrt'

# پیام سیستمی برای هوش مصنوعی
SYSTEM_MESSAGE = (
    "شما دستیار هوشمند هستید و به صورت خودمونی، جذاب و با ایموجی حرف می‌زنید! 😎 "
    "به سبک نسل Z و با کمی طنز پاسخ بده و کاربر رو سرگرم کن. 🚀 "
    "به سوالات کاربر خلاصه و دقیق جواب بده، مگر اینکه بخواد توضیح بیشتر بشنوه."
)

# مجموعه کاربران در حالت چت با هوش مصنوعی و قفل برای پردازش پیام‌ها
AI_CHAT_USERS = set()
PROCESSING_LOCK = Lock()
PROCESSED_MESSAGES = set()

application = None

app = FastAPI()

@app.post("/webhook")
async def webhook(request: Request):
    """مدیریت درخواست‌های وب‌هوک"""
    global application
    update = await request.json()
    update_obj = Update.de_json(update, application.bot)
    update_id = update_obj.update_id
    logger.info(f"دریافت درخواست با update_id: {update_id}")
    with PROCESSING_LOCK:
        if update_id in PROCESSED_MESSAGES:
            logger.warning(f"درخواست تکراری با update_id: {update_id} - نادیده گرفته شد")
            return {"status": "ok"}
        PROCESSED_MESSAGES.add(update_id)
    asyncio.create_task(application.process_update(update_obj))
    return {"status": "ok"}

@app.get("/")
async def root():
    """نقطه ورود پایه برای بررسی سرور"""
    return {"message": "Bot is running!"}

def clean_text(text):
    """پاک‌سازی متن از تبلیغات و کاراکترهای غیرضروری"""
    if not text:
        return ""
    text = text.replace("*", "").replace("`", "").replace("[", "").replace("]", "").replace("!", "!")
    ad_texts = [
        "Powered by Pollinations.AI free text APIs. Support our mission(https://pollinations.ai/redirect/kofi) to keep AI accessible for everyone.",
        "توسط Pollinations.AI به صورت رایگان ارائه شده است. از مأموریت ما حمایت کنید(https://pollinations.ai/redirect/kofi) تا AI برای همه قابل دسترسی باشد."
    ]
    for ad_text in ad_texts:
        if ad_text in text:
            text = text.replace(ad_text, "").strip()
    return text.strip()

async def check_channel_membership(bot, user_id):
    """بررسی عضویت کاربر در کانال"""
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except TelegramError as e:
        logger.error(f"خطا در بررسی عضویت کاربر {user_id} در کانال {CHANNEL_ID}: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ارسال پیام خوش‌آمدگویی با بررسی عضویت در کانال"""
    user_id = update.effective_user.id
    user_name = update.message.from_user.first_name

    if user_id in AI_CHAT_USERS:
        AI_CHAT_USERS.remove(user_id)
    context.user_data.clear()

    is_member = await check_channel_membership(context.bot, user_id)
    if not is_member:
        welcome_message = clean_text(
            f"سلام {user_name}!\nبرای استفاده از ربات، باید تو کانال @{CHANNEL_ID} عضو بشی! 😎\n"
            "بعد از عضویت، دکمه زیر رو بزن تا ربات فعال بشه! 🚀"
        )
        keyboard = [
            [InlineKeyboardButton("عضو شدم! ✅", callback_data="check_membership")]
        ]
        await update.message.reply_text(welcome_message, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    welcome_message = clean_text(
        f"سلام {user_name}!\nبه ربات خوش اومدی! 😊\n"
        "می‌خوای با هوش مصنوعی گپ بزنی یا عکس بفرستی تا آنالیز کنم؟ دکمه زیر رو بزن! 🤖"
    )
    keyboard = [
        [InlineKeyboardButton("Chat with AI 🤖", callback_data="chat_with_ai")]
    ]
    await update.message.reply_text(welcome_message, reply_markup=InlineKeyboardMarkup(keyboard))

async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بررسی عضویت کاربر پس از کلیک روی دکمه 'عضو شدم'"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_name = query.from_user.first_name

    is_member = await check_channel_membership(context.bot, user_id)
    if not is_member:
        await query.edit_message_text(
            clean_text(
                f"اوپس! 😅 هنوز تو کانال @{CHANNEL_ID} عضو نشدی!\n"
                "لطفاً عضو شو و دوباره دکمه رو بزن! 🚀"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("عضو شدم! ✅", callback_data="check_membership")]
            ])
        )
        return

    welcome_message = clean_text(
        f"آفرین {user_name}! حالا که تو کانال عضوی، ربات برات فعال شد! 😎\n"
        "می‌خوای با هوش مصنوعی گپ بزنی یا عکس بفرستی تا آنالیز کنم؟ 🤖"
    )
    keyboard = [
        [InlineKeyboardButton("Chat with AI 🤖", callback_data="chat_with_ai")]
    ]
    await query.edit_message_text(welcome_message, reply_markup=InlineKeyboardMarkup(keyboard))

async def chat_with_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فعال‌سازی حالت چت با هوش مصنوعی"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    AI_CHAT_USERS.add(user_id)
    context.user_data.clear()
    context.user_data["mode"] = "ai_chat"
    context.user_data["chat_history"] = []
    keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        clean_text("🤖 چت با هوش مصنوعی فعال شد!\n\nهر چی می‌خوای بگو یا یه عکس بفرست تا آنالیز کنم! 😎"),
        reply_markup=reply_markup
    )

async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت پیام‌های متنی کاربر در حالت چت با هوش مصنوعی"""
    user_id = update.effective_user.id
    if user_id not in AI_CHAT_USERS or context.user_data.get("mode") != "ai_chat":
        return

    message_id = update.message.message_id
    with PROCESSING_LOCK:
        if message_id in PROCESSED_MESSAGES:
            logger.warning(f"پیام تکراری با message_id: {message_id} - نادیده گرفته شد")
            return
        PROCESSED_MESSAGES.add(message_id)

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

    keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        response = requests.post(TEXT_API_URL, json=payload, timeout=20)
        if response.status_code == 200:
            ai_response = clean_text(response.text.strip())
            chat_history.append({"role": "assistant", "content": ai_response})
            context.user_data["chat_history"] = chat_history
            await update.message.reply_text(ai_response, reply_markup=reply_markup)
        else:
            await update.message.reply_text(
                clean_text("اوفف، یه مشکلی پیش اومد! 😅 فکر کنم API یه کم خوابش برده! بعداً امتحان کن 🚀"),
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"خطا در اتصال به API چت: {e}")
        await update.message.reply_text(
            clean_text("اییی، یه خطا خوردم! 😭 بعداً دوباره بیا، قول می‌دم درستش کنم! 🚀"),
            reply_markup=reply_markup
        )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت عکس‌های ارسالی و آنالیز با API Pollinations"""
    user_id = update.effective_user.id
    if user_id not in AI_CHAT_USERS or context.user_data.get("mode") != "ai_chat":
        return

    message_id = update.message.message_id
    with PROCESSING_LOCK:
        if message_id in PROCESSED_MESSAGES:
            logger.warning(f"پیام تکراری با message_id: {message_id} - نادیده گرفته شد")
            return
        PROCESSED_MESSAGES.add(message_id)

    keyboard = [[InlineKeyboardButton("🏠 Back to Home", callback_data="back_to_home")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # دریافت عکس با بالاترین کیفیت
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_url = file.file_path

    try:
        # دانلود عکس
        response = requests.get(file_url, timeout=10)
        if response.status_code != 200:
            await update.message.reply_text(
                clean_text("اوفف، نمی‌تونم عکس رو دانلود کنم! 😅 دوباره امتحان کن! 🚀"),
                reply_markup=reply_markup
            )
            return

        # ارسال به API Pollinations برای آنالیز
        files = {'image': ('photo.jpg', response.content, 'image/jpeg')}
        payload = {"prompt": "Describe this image in a casual, fun way with emojis! 😎"}
        api_response = requests.post(IMAGE_API_URL, files=files, data=payload, timeout=20)

        if api_response.status_code == 200:
            analysis = clean_text(api_response.text.strip())
            chat_history = context.user_data.get("chat_history", [])
            chat_history.append({"role": "user", "content": "[User sent an image]"})
            chat_history.append({"role": "assistant", "content": analysis})
            context.user_data["chat_history"] = chat_history
            await update.message.reply_text(analysis, reply_markup=reply_markup)
        else:
            await update.message.reply_text(
                clean_text("اوفف، API تصویر یه کم قاطی کرد! 😅 دوباره امتحان کن! 🚀"),
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"خطا در آنالیز تصویر: {e}")
        await update.message.reply_text(
            clean_text("اییی، یه خطا تو آنالیز عکس پیش اومد! 😭 دوباره بفرست! 🚀"),
            reply_markup=reply_markup
        )

async def back_to_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بازگشت به منوی اصلی"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_id in AI_CHAT_USERS:
        AI_CHAT_USERS.remove(user_id)
    context.user_data.clear()
    user_name = query.from_user.first_name
    welcome_message = clean_text(
        f"سلام {user_name}!\nبه ربات خوش اومدی! 😊\n"
        "می‌خوای با هوش مصنوعی گپ بزنی یا عکس بفرستی تا آنالیز کنم؟ دکمه زیر رو بزن! 🤖"
    )
    keyboard = [
        [InlineKeyboardButton("Chat with AI 🤖", callback_data="chat_with_ai")]
    ]
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=welcome_message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    try:
        await query.message.delete()
    except Exception as e:
        logger.error(f"خطا در حذف پیام قبلی: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت خطاها"""
    logger.error(f"خطا رخ داد: {context.error}")
    if update and hasattr(update, 'message') and update.message:
        await update.message.reply_text(clean_text("یه مشکلی پیش اومد! 😅 دوباره امتحان کن!"))
    elif update and hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.message.reply_text(clean_text("یه مشکلی پیش اومد! 😅 دوباره امتحان کن!"))

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
        application.add_handler(CallbackQueryHandler(check_membership, pattern="^check_membership$"))
        application.add_handler(CallbackQueryHandler(chat_with_ai, pattern="^chat_with_ai$"))
        application.add_handler(CallbackQueryHandler(back_to_home, pattern="^back_to_home$"))
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
