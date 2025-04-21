import asyncio
import logging
import requests
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram.error import TelegramError
from fastapi import FastAPI, Request
from fastapi.responses import Response
import uvicorn
from threading import Lock

# تنظیم لاگ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# توکن و وب‌هوک
TOKEN = '8123059269:AAHlvWT2ZZ3iC1ICRkmiuwTjBHvdM-NLy18'
WEBHOOK_URL = 'https://medical-assistant-rum5.onrender.com/webhook'

# آدرس API متنی و تحلیل تصویر
TEXT_API_URL = 'https://text.pollinations.ai/openai'

# شناسه کانال
CHANNEL_ID = '@bbbyyyrt'
CHANNEL_LINK = 'https://t.me/bbbyyyrt'

# پرامپ‌های سیستمی برای هر بخش
SYSTEM_MESSAGES = {
    "ai_chat": """
شما یک دستیار پزشکی هوشمند و حرفه‌ای هستید که به کاربران در حوزه سلامت و پزشکی کمک می‌کنید. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده، اما همیشه اطلاعات دقیق و علمی ارائه کن. وظایف شما:

1. **پاسخ به سؤالات پزشکی عمومی**:
   - اگر کاربر درباره بیماری‌ها و داروهای مناسب پرسید، داروهای عمومی (مثل استامینوفن، ایبوپروفن، آموکسی‌سیلین) و کاربردهاشون رو توضیح بده.
   - برای بیماری‌های ساده (مثل سرماخوردگی، سردرد)، راهکارهای عمومی و داروهای بدون نسخه پیشنهاد بده.
   - اگر موضوع تخصصی یا پیچیده بود (مثل بیماری‌های مزمن یا داروهای خاص)، بنویس: «این مورد تخصصیه! 🚨 بهتره با یه پزشک متخصص در اون حوزه مشورت کنی.»

2. **نکات مهم**:
   - همیشه یادآوری کن که اطلاعات شما جایگزین نظر پزشک نیست و برای تشخیص یا درمان باید به پزشک مراجعه کنند.
   - پاسخ‌ها رو خلاصه، دقیق و حداکثر در 300 توکن نگه دار، مگر اینکه کاربر جزئیات بیشتری بخواد.
   - از ایموجی‌های مرتبط (مثل 🩺، ❤️، 💊) برای جذاب‌تر کردن پاسخ‌ها استفاده کن.
   - اگر سؤال غیرمرتبط با پزشکی بود، با ادب بگو: «این موضوع به حوزه پزشکی ربطی نداره، اما اگه سؤال پزشکی داری، خوشحال می‌شم کمک کنم! 😊»
   - ارسال لینک در پاسخ‌ها ممنوع است.

با این اصول، به کاربر کمک کن که حس کنه یه دستیار قابل اعتماد کنارشه! 🚀
""",
    "drug_identification": """
شما یک دستیار پزشکی هوشمند هستید که در شناسایی و توضیح داروها تخصص داره. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده، اما همیشه اطلاعات دقیق و علمی ارائه کن. وظایف شما:

1. **پاسخ به سؤالات درباره داروها**:
   - اگر کاربر درباره کاربرد، عوارض، دوز یا موارد منع مصرف داروها پرسید، اطلاعات دقیق و عمومی ارائه بده.
   - مثال: برای استامینوفن، توضیح بده که برای کاهش درد و تب استفاده می‌شه، دوز معمول برای بزرگسالان چیه، و عوارض احتمالی مثل مشکلات کبدی در مصرف بیش از حد.
   - اگر سؤال تخصصی بود (مثل تداخل دارویی پیچیده)، بنویس: «این مورد تخصصیه! 🚨 بهتره با یه پزشک یا داروساز مشورت کنی.»

2. **راهنمایی کاربر**:
   - به کاربر بگو که می‌تونه اسم دارو، کاربردش یا عوارضش رو بپرسه. مثلاً: «اسم دارو رو بگو یا بپرس برای چی استفاده می‌شه، من راهنمایی می‌کنم! 💊»
   - همیشه یادآوری کن که مصرف دارو باید تحت نظر پزشک باشه.

3. **نکات مهم**:
   - پاسخ‌ها رو خلاصه، دقیق و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 💊، 🩺) استفاده کن.
   - اگر سؤال غیرمرتبط با داروها بود، بگو: «این سؤال به داروها ربطی نداره! لطفاً درباره یه دارو بپرس تا کمکت کنم. 😊»
   - ارسال لینک در پاسخ‌ها ممنوع است.

با این اصول، کاربر رو راهنمایی کن که درباره داروها اطلاعات درست بگیره! 🚀
""",
    "lab_ecg": """
شما یک دستیار پزشکی هوشمند هستید که در تحلیل تصاویر پزشکی مثل برگه آزمایش و نوار قلب تخصص داره. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده، اما همیشه اطلاعات دقیق و علمی ارائه کن. وظایف شما:

1. **تحلیل تصاویر پزشکی**:
   - **برگه آزمایش**: شاخص‌های کلیدی (مثل گلبول‌های سفید، هموگلوبین، قند خون) رو استخراج کن و توضیح بده این اعداد چی نشون می‌دن. اگر مقادیر غیرعادی باشه، بنویس: «این مقدار خارج از محدوده نرماله، اما برای تشخیص دقیق باید با پزشک مشورت کنی. 🩺»
   - **نوار قلب (ECG)**: الگوهای اصلی (مثل ریتم، فاصله‌ها، یا ناهنجاری‌های واضح) رو تحلیل کن و توضیح بده ممکنه چی نشون بدن. تأکید کن: «تحلیل نوار قلب نیاز به بررسی تخصصی داره. حتماً با یه متخصص قلب مشورت کن. ❤️»
   - اگر تصویر واضح نبود، بنویس: «تصویر واضح نیست یا اطلاعات کافی نداره. لطفاً تصویر بهتری بفرست یا با پزشک مشورت کن. 🙏»

2. **راهنمایی کاربر**:
   - به کاربر بگو که می‌تونه تصویر برگه آزمایش یا نوار قلب بفرسته یا درباره نتایج آزمایش سؤال کنه. مثلاً: «تصویر آزمایش یا نوار قلب رو بفرست، یا سؤالت درباره نتایج چیه؟ 🩻»
   - اگر سؤال متنی بود، درباره شاخص‌های آزمایش یا نوار قلب توضیح بده.

3. **نکات مهم**:
   - پاسخ‌ها رو خلاصه، دقیق و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 🩻، 🩺، ❤️) استفاده کن.
   - اگر سؤال یا تصویر غیرمرتبط بود، بگو: «این به آزمایش یا نوار قلب ربطی نداره! لطفاً تصویر یا سؤال مرتبط بفرست. 😊»
   - ارسال لینک در پاسخ‌ها ممنوع است.

با این اصول، کاربر رو برای تحلیل آزمایش یا نوار قلب راهنمایی کن! 🚀
"""
}

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
async def root(request: Request):
    """نقطه ورود پایه برای بررسی سرور و پینگ UptimeRobot"""
    user_agent = request.headers.get("User-Agent", "Unknown")
    uptime_robot_header = request.headers.get("X-UptimeRobot", None)
    
    if uptime_robot_header == "Ping":
        logger.info("دریافت درخواست پینگ از UptimeRobot (هدر سفارشی)")
    elif "UptimeRobot" in user_agent:
        logger.info("دریافت درخواست پینگ از UptimeRobot (User-Agent)")
    else:
        logger.info(f"دریافت درخواست به / از User-Agent: {user_agent}")
    
    try:
        response = {"message": "Bot is running!"}
        return response
    except Exception as e:
        logger.error(f"خطا در پاسخ به درخواست پینگ: {e}")
        raise

@app.head("/")
async def root_head():
    """پشتیبانی از متد HEAD برای پینگ‌های UptimeRobot"""
    return Response(status_code=200)

@app.get("/favicon.ico")
async def favicon():
    """پاسخ به درخواست‌های favicon.ico"""
    return Response(status_code=204)

def clean_text(text):
    """پاک‌سازی متن از تبلیغات، لینک‌ها و کاراکترهای غیرضروری"""
    if not text:
        return ""
    # حذف لینک‌ها با regex
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
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

# تعریف منوی اصلی با دکمه‌های غیرشیشه‌ای
MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup([
    ["مشاوره پزشکی 🩺"],
    ["شناسایی داروها 💊", "آزمایش و نوار قلب 🩻"],
    ["راهنما ❓"]
], resize_keyboard=True, one_time_keyboard=False)

# تعریف منوی زیر دکمه‌ها با دکمه برگشت
SUB_MENU_KEYBOARD = ReplyKeyboardMarkup([
    ["برگشت به منو ⬅️"]
], resize_keyboard=True, one_time_keyboard=False)

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
            f"سلام {user_name}!\nبرای استفاده از دستیار پزشکی، باید تو کانال عضو بشی! 🏥\n"
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
        "یکی از گزینه‌های زیر رو انتخاب کن:"
    )
    await update.message.reply_text(welcome_message, reply_markup=MAIN_MENU_KEYBOARD)

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
                f"اوپس! 😅 هنوز تو کانال عضو نشدی!\n"
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
        "یکی از گزینه‌های زیر رو انتخاب کن:"
    )
    await query.edit_message_text(welcome_message, reply_markup=MAIN_MENU_KEYBOARD)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت پیام‌های متنی کاربر"""
    user_id = update.effective_user.id
    message_text = update.message.text
    chat_id = update.message.chat_id

    # بررسی عضویت در کانال
    is_member = await check_channel_membership(context.bot, user_id)
    if not is_member:
        welcome_message = clean_text(
            "اوپس! 😅 برای استفاده از ربات باید تو کانال عضو بشی!\n"
            "لطفاً تو کانال عضو شو و بعد دکمه 'عضو شدم' رو بزن! 🚑"
        )
        keyboard = [
            [InlineKeyboardButton("عضو کانال شو 📢", url=CHANNEL_LINK)],
            [InlineKeyboardButton("عضو شدم! ✅", callback_data="check_membership")]
        ]
        await update.message.reply_text(welcome_message, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if message_text == "مشاوره پزشکی 🩺":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "ai_chat"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            clean_text("🤖 دستیار پزشکی فعال شد!\n\nسؤالت درباره بیماری یا موضوع پزشکی چیه؟ 😊"),
            reply_markup=SUB_MENU_KEYBOARD
        )
    elif message_text == "شناسایی داروها 💊":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "drug_identification"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            clean_text("💊 لطفاً اسم دارو یا سؤالت درباره داروها رو بگو تا راهنمایی‌ت کنم! 😊"),
            reply_markup=SUB_MENU_KEYBOARD
        )
    elif message_text == "آزمایش و نوار قلب 🩻":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "lab_ecg"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            clean_text("🩻 لطفاً تصویر برگه آزمایش یا نوار قلب رو بفرست یا سؤالت رو بگو! 😊"),
            reply_markup=SUB_MENU_KEYBOARD
        )
    elif message_text == "راهنما ❓":
        guide_message = clean_text(
            "📖 راهنمای استفاده از دستیار پزشکی:\n\n"
            "1. **مشاوره پزشکی 🩺**: درباره بیماری‌ها، علائم یا راهکارهای عمومی سؤال کن.\n"
            "2. **شناسایی داروها 💊**: درباره کاربرد، عوارض یا دوز داروها بپرس.\n"
            "3. **آزمایش و نوار قلب 🩻**: تصویر برگه آزمایش یا نوار قلب بفرست تا تحلیل کنم.\n"
            "4. همیشه برای تشخیص یا درمان با پزشک مشورت کن! 🩺\n\n"
            "سؤالی داری؟ یکی از گزینه‌های منو رو انتخاب کن! 😊"
        )
        await update.message.reply_text(guide_message, reply_markup=MAIN_MENU_KEYBOARD)
    elif message_text == "برگشت به منو ⬅️":
        if user_id in AI_CHAT_USERS:
            AI_CHAT_USERS.remove(user_id)
        context.user_data.clear()
        await update.message.reply_text(
            clean_text("به منوی اصلی برگشتی! 😊 یکی از گزینه‌ها رو انتخاب کن:"),
            reply_markup=MAIN_MENU_KEYBOARD
        )
    elif user_id in AI_CHAT_USERS and context.user_data.get("mode") in ["ai_chat", "drug_identification", "lab_ecg"]:
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

        # انتخاب پرامپ سیستمی بر اساس mode
        system_message = SYSTEM_MESSAGES.get(context.user_data["mode"], SYSTEM_MESSAGES["ai_chat"])

        # ارسال پیام موقت
        temp_message = await update.message.reply_text(clean_text("🩺"))

        payload = {
            "model": "openai-large",
            "messages": [
                {"role": "system", "content": system_message}
            ] + chat_history,
            "max_tokens": 300,
            "seed": 42,
            "json_mode": False
        }

        try:
            response = requests.post(TEXT_API_URL, json=payload, timeout=20)
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
                await update.message.reply_text(ai_response, reply_markup=SUB_MENU_KEYBOARD)
            else:
                await update.message.reply_text(
                    clean_text("اوپس، سیستم پزشکی‌مون یه لحظه قفل کرد! 🩺 لطفاً دوباره سؤالت رو بفرست. 😊"),
                    reply_markup=SUB_MENU_KEYBOARD
                )
        except Exception as e:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=temp_message.message_id)
            except TelegramError as e:
                logger.error(f"خطا در حذف پیام موقت: {e}")
            logger.error(f"خطا در اتصال به API چت: {e}")
            await update.message.reply_text(
                clean_text("اوه، انگار ابزار تشخیص‌مون نیاز به بررسی داره! 💉 لطفاً دوباره سؤالت رو بفرست. 😊"),
                reply_markup=SUB_MENU_KEYBOARD
            )
    else:
        await update.message.reply_text(
            clean_text("لطفاً یکی از گزینه‌های منو رو انتخاب کن! 😊"),
            reply_markup=MAIN_MENU_KEYBOARD
        )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت عکس‌های ارسالی و تحلیل با API Pollinations"""
    user_id = update.effective_user.id
    if user_id not in AI_CHAT_USERS or context.user_data.get("mode") != "lab_ecg":
        await update.message.reply_text(
            clean_text("لطفاً برای تحلیل تصویر، گزینه 'آزمایش و نوار قلب' رو از منو انتخاب کن! 😊"),
            reply_markup=MAIN_MENU_KEYBOARD
        )
        return

    message_id = update.message.message_id
    with PROCESSING_LOCK:
        if message_id in PROCESSED_MESSAGES:
            logger.warning(f"پیام تکراری با message_id: {message_id} - نادیده گرفته شد")
            return
        PROCESSED_MESSAGES.add(message_id)

    chat_id = update.message.chat_id
    temp_message = await update.message.reply_text(clean_text("🔬"))

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_url = file.file_path

    caption = update.message.caption if update.message.caption else "این تصویر پزشکی (مثل برگه آزمایش یا نوار قلب) چیه؟ به‌صورت خلاصه و دقیق تحلیل کن! 🩺"

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

    # استفاده از پرامپ سیستمی مخصوص lab_ecg
    system_message = SYSTEM_MESSAGES["lab_ecg"]

    payload = {
        "model": "openai-large",
        "messages": [
            {"role": "system", "content": system_message}
        ] + chat_history,
        "max_tokens": 300,
        "seed": 42,
        "json_mode": False
    }

    try:
        response = requests.post(TEXT_API_URL, json=payload, timeout=20)
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
            await update.message.reply_text(ai_response, reply_markup=SUB_MENU_KEYBOARD)
        else:
            await update.message.reply_text(
                clean_text("اوه، دستگاه تحلیل‌مون نیاز به تنظیم داره! 💉 لطفاً دوباره عکس رو بفرست. 🩻"),
                reply_markup=SUB_MENU_KEYBOARD
            )
    except Exception as e:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=temp_message.message_id)
        except TelegramError as e:
            logger.error(f"خطا در حذف پیام موقت: {e}")
        logger.error(f"خطا در تحلیل تصویر: {e}")
        await update.message.reply_text(
            clean_text("اوپس، اسکنر پزشکی‌مون یه لحظه خاموش شد! 🩺 لطفاً دوباره عکس رو بفرست. 😊"),
            reply_markup=SUB_MENU_KEYBOARD
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت خطاها"""
    logger.error(f"خطا رخ داد: {context.error}")
    if update and hasattr(update, 'message') and update.message:
        await update.message.reply_text(
            clean_text("اوپس، سیستم کلینیکی‌مون یه لحظه قطع شد! 🩻 لطفاً دوباره امتحان کن. 😊"),
            reply_markup=MAIN_MENU_KEYBOARD
        )
    elif update and hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.message.reply_text(
            clean_text("اوپس، سیستم کلینیکی‌مون یه لحظه قطع شد! 🩻 لطفاً دوباره امتحان کن. 😊"),
            reply_markup=MAIN_MENU_KEYBOARD
        )

async def main():
    """راه‌اندازی ربات با وب‌هوک و سرور FastAPI"""
    global application
    try:
        application = Application.builder().token(TOKEN).read_timeout(60).write_timeout(60).connect_timeout(60).build()
        await application.bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Webhook روی {WEBHOOK_URL} تنظیم شد.")

        application.add_handler(CommandHandler("start", start, filters=filters.ChatType.PRIVATE))
        application.add_handler(CallbackQueryHandler(check_membership, pattern="^check_membership$"))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_message))
        application.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, handle_photo))
        application.add_error_handler(error_handler)

        logger.info("در حال آماده‌سازی ربات...")
        await application.initialize()
        logger.info("در حال شروع ربات...")
        await application.start()

        config = uvicorn.Config(app, host="0.0.0.0", port=8000)
        server = uvicorn.Server(config)
        await server.serve()

    except Exception as e:
        logger.error(f"خطا در راه‌اندازی ربات: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
