import asyncio
import logging
import requests
import json
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

# آدرس API متنی و تحلیل تصویر
TEXT_API_URL = 'https://text.pollinations.ai/openai'

# شناسه کانال
CHANNEL_ID = '@bbbyyyrt'
CHANNEL_LINK = 'https://t.me/bbbyyyrt'

# پیام سیستمی برای هوش مصنوعی
SYSTEM_MESSAGE = """
شما یک دستیار پزشکی هوشمند و حرفه‌ای هستید که به کاربران در حوزه سلامت و پزشکی کمک می‌کنید. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده، اما همیشه اطلاعات دقیق و علمی ارائه کن. وظایف شما:

1. **پاسخ به سؤالات پزشکی عمومی**:
   - اگر کاربر درباره بیماری‌ها و داروهای مناسب پرسید، داروهای عمومی (مثل استامینوفن، ایبوپروفن، آموکسی‌سیلین) و کاربردهاشون رو توضیح بده.
   - برای بیماری‌های ساده (مثل سرماخوردگی، سردرد)، راهکارهای عمومی و داروهای بدون نسخه پیشنهاد بده.
   - اگر موضوع تخصصی یا پیچیده بود (مثل بیماری‌های مزمن یا داروهای خاص)، بنویس: «این مورد تخصصیه! 🚨 بهتره با یه پزشک متخصص در اون حوزه مشورت کنی.»

2. **پاسخ به سؤالات درباره داروها**:
   - اگر کاربر درباره داروها (مثل کاربرد، عوارض، یا دوز) پرسید، اطلاعات دقیق و عمومی ارائه بده.
   - همیشه یادآوری کن که مصرف دارو باید تحت نظر پزشک باشه.

3. **تحلیل تصاویر پزشکی**:
   - **برگه آزمایش**: اگر تصویر برگه آزمایش دریافت کردی، شاخص‌های کلیدی (مثل گلبول‌های سفید، هموگلوبین، قند خون) رو استخراج کن و به‌صورت خلاصه توضیح بده که این اعداد چی نشون می‌دن. اگر مقادیر غیرعادی باشه، بنویس: «این مقدار خارج از محدوده نرماله، اما برای تشخیص دقیق باید با پزشک مشورت کنی. 🩺»
   - **نوار قلب (ECG)**: اگر تصویر نوار قلب دریافت کردی، الگوهای اصلی (مثل ریتم، فاصله‌ها، یا ناهنجاری‌های واضح) رو تحلیل کن. توضیح بده که این الگوها ممکنه چی نشون بدن، اما تأکید کن: «تحلیل نوار قلب نیاز به بررسی تخصصی داره. حتماً با یه متخصص قلب مشورت کن. ❤️»
   - اگر تصویر واضح نبود یا اطلاعات کافی نداشت، بنویس: «تصویر واضح نیست یا اطلاعات کافی نداره. لطفاً با پزشک مشورت کن. 🙏»

4. **نکات مهم**:
   - همیشه یادآوری کن که اطلاعات شما جایگزین نظر پزشک نیست و برای تشخیص یا درمان باید به پزشک مراجعه کنند.
   - پاسخ‌ها رو خلاصه، دقیق و حداکثر در 300 توکن نگه دار، مگر اینکه کاربر جزئیات بیشتری بخواد.
   - از ایموجی‌های مرتبط (مثل 🩺، ❤️، 💊) برای جذاب‌تر کردن پاسخ‌ها استفاده کن.
   - اگر سؤال یا تصویر غیرمرتبط با پزشکی بود، با ادب بگو: «این موضوع به حوزه پزشکی ربطی نداره، اما اگه سؤال پزشکی داری، خوشحال می‌شم کمک کنم! 😊»

با این اصول، به کاربر کمک کن که حس کنه یه دستیار قابل اعتماد کنارشه! 🚀
"""

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
    # حذف متن بعد از ---
    if '---' in text:
        text = text.split('---')[0].strip()
    # حذف کاراکترهای غیرضروری
    text = text.replace("*", "").replace("`", "").replace("[", "").replace("]", "").replace("!", "!")
    # حذف تبلیغات خاص
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
            f"سلام {user_name}!\nبرای استفاده از دستیار پزشکی، باید تو کانال @{CHANNEL_ID} عضو بشی! 😊\n"
            "لطفاً تو کانال عضو شو و بعد دکمه 'عضو شدم' رو بزن! 🚑"
        )
        keyboard = [
            [InlineKeyboardButton("عضو کانال شو 📢", url=CHANNEL_LINK)],
            [InlineKeyboardButton("عضو شدم! ✅", callback_data="check_membership")]
        ]
        await update.message.reply_text(welcome_message, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    welcome_message = clean_text(
        f"سلام {user_name}!\nبه دستیار پزشکی هوشمند خوش اومدی! 🩺\n"
        "می‌تونی درباره بیماری‌ها، داروها، برگه آزمایش یا نوار قلب سؤال کنی. چی تو سرته؟ 😎"
    )
    keyboard = [
        [InlineKeyboardButton("شروع مشاوره پزشکی 🤖", callback_data="chat_with_ai")]
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
                "لطفاً تو کانال عضو شو و دوباره دکمه 'عضو شدم' رو بزن! 🚑"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("عضو کانال شو 📢", url=CHANNEL_LINK)],
                [InlineKeyboardButton("عضو شدم! ✅", callback_data="check_membership")]
            ])
        )
        return

    welcome_message = clean_text(
        f"آفرین {user_name}! حالا که تو کانال عضوی، دستیار پزشکی برات فعال شد! 🩺\n"
        "می‌تونی درباره بیماری‌ها، داروها، برگه آزمایش یا نوار قلب سؤال کنی. چی تو سرته؟ 😎"
    )
    keyboard = [
        [InlineKeyboardButton("شروع مشاوره پزشکی 🤖", callback_data="chat_with_ai")]
    ]
    await query.edit_message_text(welcome_message, reply_markup=InlineKeyboardMarkup(keyboard))

async def chat_with_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فعال‌سازی حالت چت با هوش مصنوعی"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    AI_CHAT_USERS.add(user_id)
    context.user_data.clear()
    context.user_data["mode"] = "ai_chat"
    context.user_data["chat_history"] = []
    keyboard = [[InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="back_to_home")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        clean_text("🤖 دستیار پزشکی فعال شد!\n\nسؤالت درباره بیماری، دارو، برگه آزمایش یا نوار قلب چیه؟ 😊"),
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

    chat_id = update.message.chat_id
    user_message = update.message.text
    chat_history = context.user_data.get("chat_history", [])
    chat_history.append({"role": "user", "content": user_message})
    context.user_data["chat_history"] = chat_history

    # ارسال پیام موقت
    temp_message = await update.message.reply_text(
        clean_text("در حال نوشتن... ✍️")
    )

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
            # پردازش پاسخ JSON و استخراج content
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
        # حذف پیام موقت در صورت خطا
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
    user_id = update.effective_user.id
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
    temp_message = await update.message.reply_text(
        clean_text("در حال آنالیز عکس، صبر کنید... ⏳")
    )

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
            # پردازش پاسخ JSON و استخراج content
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
        # حذف پیام موقت در صورت خطا
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=temp_message.message_id)
        except TelegramError as e:
            logger.error(f"خطا در حذف پیام موقت: {e}")
        logger.error(f"خطا در تحلیل تصویر: {e}")
        await update.message.reply_text(
            clean_text("اوپس، اسکنر پزشکی‌مون یه لحظه خاموش شد! 🩺 لطفاً دوباره عکس رو بفرست. 😊"),
            reply_markup=reply_markup
        )

async def back_to_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بازگشت به منوی اصلی"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id in AI_CHAT_USERS:
        AI_CHAT_USERS.remove(user_id)
    context.user_data.clear()
    user_name = query.from_user.first_name
    welcome_message = clean_text(
        f"سلام {user_name}!\nبه دستیار پزشکی هوشمند خوش اومدی! 🩺\n"
        "می‌تونی درباره بیماری‌ها، داروها، برگه آزمایش یا نوار قلب سؤال کنی. چی تو سرته؟ 😎"
    )
    keyboard = [
        [InlineKeyboardButton("شروع مشاوره پزشکی 🤖", callback_data="chat_with_ai")]
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
        await update.message.reply_text(clean_text("اوپس، سیستم کلینیکی‌مون یه لحظه قطع شد! 🩻 لطفاً دوباره امتحان کن. 😊"))
    elif update and hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.message.reply_text(clean_text("اوپس، سیستم کلینیکی‌مون یه لحظه قطع شد! 🩻 لطفاً دوباره امتحان کن. 😊"))

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
