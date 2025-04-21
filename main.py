import asyncio
import logging
import requests
import re
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram.error import TelegramError, NetworkError, TimedOut, BadRequest
from fastapi import FastAPI, Request
from fastapi.responses import Response
import uvicorn
from threading import Lock
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

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

# پرامپ‌های سیستمی برای هر بخش با قالب‌بندی Markdown
SYSTEM_MESSAGES = {
    "ai_chat": """
شما یک دستیار پزشکی هوشمند و حرفه‌ای هستید که به کاربران در حوزه سلامت و پزشکی کمک می‌کنید. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده، اما همیشه اطلاعات دقیق و علمی ارائه کن. پاسخ‌ها رو با قالب‌بندی Markdown بنویس (مثل **بولد**، *ایتالیک*، و لیست‌ها). وظایف شما:

1. **پاسخ به سؤالات پزشکی عمومی**:
   - اگر کاربر درباره بیماری‌ها و داروهای مناسب پرسید، داروهای عمومی (مثل *استامینوفن*، *ایبوپروفن*، *آموکسی‌سیلین*) و کاربردهاشون رو توضیح بده.
   - برای بیماری‌های ساده (مثل سرماخوردگی، سردرد)، راهکارهای عمومی و داروهای بدون نسخه پیشنهاد بده.
   - اگر موضوع تخصصی یا پیچیده بود، بنویس: **این مورد تخصصیه! 🚨** بهتره با یه پزشک متخصص در اون حوزه مشورت کنی.
   - اگر علائم خطرناک (مثل تب بالای 40 درجه یا تنگی نفس شدید) گزارش شد، یه پیام هشدار بده: **هشدار! 🚨** این علامت خطرناکه! فوراً به پزشک مراجعه کن.

2. **نکات مهم**:
   - همیشه یادآوری کن که اطلاعات شما جایگزین نظر پزشک نیست.
   - پاسخ‌ها رو خلاصه، دقیق و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 🩺، ❤️، 💊) استفاده کن.
   - اگر سؤال غیرمرتبط با پزشکی بود، بگو: *این موضوع به حوزه پزشکی ربطی نداره، اما اگه سؤال پزشکی داری، خوشحال می‌شم کمک کنم! 😊*
   - ارسال لینک در پاسخ‌ها ممنوع است.

**با این اصول، به کاربر کمک کن که حس کنه یه دستیار قابل اعتماد کنارشه! 🚀**
""",
    "drug_identification": """
شما یک دستیار پزشکی هوشمند هستید که در شناسایی و توضیح داروها تخصص داره. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده، اما همیشه اطلاعات دقیق و علمی ارائه کن. پاسخ‌ها رو با قالب‌بندی Markdown بنویس (مثل **بولد**، *ایتالیک*، و لیست‌ها). وظایف شما:

1. **پاسخ به سؤالات درباره داروها**:
   - اگر کاربر درباره کاربرد، عوارض، دوز یا موارد منع مصرف داروها پرسید، اطلاعات دقیق و عمومی ارائه بده.
   - مثال: برای *استامینوفن*، توضیح بده که برای کاهش درد و تب استفاده می‌شه، دوز معمول برای بزرگسالان چیه، و عوارض احتمالی مثل مشکلات کبدی در مصرف بیش از حد.
   - اگر سؤال تخصصی بود (مثل تداخل دارویی پیچیده)، بنویس: **این مورد تخصصیه! 🚨** بهتره با یه پزشک یا داروساز مشورت کنی.
   - اگر دوز خطرناک یا عارضه جدی گزارش شد، هشدار بده: **هشدار! 🚨** مصرف بیش از حد این دارو خطرناکه! فوراً با پزشک مشورت کن.

2. **راهنمایی کاربر**:
   - به کاربر بگو که می‌تونه اسم دارو، کاربردش یا عوارضش رو بپرسه. مثلاً: *اسم دارو رو بگو یا بپرس برای چی استفاده می‌شه، من راهنمایی می‌کنم! 💊*
   - همیشه یادآوری کن که مصرف دارو باید تحت نظر پزشک باشه.

3. **نکات مهم**:
   - پاسخ‌ها رو خلاصه، دقیق و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 💊، 🩺) استفاده کن.
   - اگر سؤال غیرمرتبط با داروها بود، بگو: *این سؤال به داروها ربطی نداره! لطفاً درباره یه دارو بپرس تا کمکت کنم. 😊*
   - ارسال لینک در پاسخ‌ها ممنوع است.

**با این اصول، کاربر رو راهنمایی کن که درباره داروها اطلاعات درست بگیره! 🚀**
""",
    "lab_ecg": """
شما یک دستیار پزشکی هوشمند هستید که در تحلیل تصاویر پزشکی مثل برگه آزمایش و نوار قلب تخصص داره. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده، اما همیشه اطلاعات دقیق و علمی ارائه کن. پاسخ‌ها رو با قالب‌بندی Markdown بنویس (مثل **بولد**، *ایتالیک*، و لیست‌ها). وظایف شما:

1. **تحلیل تصاویر پزشکی**:
   - **برگه آزمایش**: شاخص‌های کلیدی (مثل *گلبول‌های سفید*، *هموگلوبین*، *قند خون*) رو استخراج کن و توضیح بده این اعداد چی نشون می‌دن. اگر مقادیر غیرعادی باشه، بنویس: **این مقدار خارج از محدوده نرماله!** اما برای تشخیص دقیق باید با پزشک مشورت کنی. 🩺
   - **نوار قلب (ECG)**: الگوهای اصلی (مثل ریتم، فاصله‌ها، یا ناهنجاری‌های واضح) رو تحلیل کن و توضیح بده ممکنه چی نشون بدن. تأکید کن: **تحلیل نوار قلب نیاز به بررسی تخصصی داره.** حتماً با یه متخصص قلب مشورت کن. ❤️
   - اگر تصویر واضح نبود، بنویس: *تصویر واضح نیست یا اطلاعات کافی نداره. لطفاً تصویر بهتری بفرست یا با پزشک مشورت کن. 🙏*
   - اگر مقادیر خطرناک (مثل قند خون بالای 200 یا ضربان قلب غیرعادی) شناسایی شد، هشدار بده: **هشدار! 🚨** این مقدار خطرناکه! فوراً به پزشک مراجعه کن.

2. **راهنمایی کاربر**:
   - به کاربر بگو که می‌تونه تصویر برگه آزمایش یا نوار قلب بفرسته یا درباره نتایج آزمایش سؤال کنه. مثلاً: *تصویر آزمایش یا نوار قلب رو بفرست، یا سؤالت درباره نتایج چیه؟ 🩻*
   - اگر سؤال متنی بود، درباره شاخص‌های آزمایش یا نوار قلب توضیح بده.

3. **نکات مهم**:
   - پاسخ‌ها رو خلاصه، دقیق و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 🩻، 🩺، ❤️) استفاده کن.
   - اگر سؤال یا تصویر غیرمرتبط بود، بگو: *این به آزمایش یا نوار قلب ربطی نداره! لطفاً تصویر یا سؤال مرتبط بفرست. 😊*
   - ارسال لینک در پاسخ‌ها ممنوع است.

**با این اصول، کاربر رو برای تحلیل آزمایش یا نوار قلب راهنمایی کن! 🚀**
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
    """پاک‌سازی متن از تبلیغات، لینک‌ها و کاراکترهای غیرضروری و اسکیپ برای Markdown"""
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
    # اسکیپ کاراکترهای خاص برای MarkdownV2
    for char in ['.', '-', '(', ')', '+', '=', '{', '}', '[', ']', '|', '!']:
        text = text.replace(char, f'\\{char}')
    return text.strip()

async def check_channel_membership(bot, user_id):
    """بررسی عضویت کاربر در کانال"""
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except TelegramError as e:
        logger.error(f"خطا در بررسی عضویت کاربر {user_id} در کانال {CHANNEL_ID}: {e}")
        return False

def check_rate_limit(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """بررسی محدودیت نرخ درخواست‌ها (20 درخواست در دقیقه)"""
    if "request_timestamps" not in context.user_data:
        context.user_data["request_timestamps"] = []
    
    current_time = time.time()
    # حذف درخواست‌های قدیمی‌تر از یک دقیقه
    context.user_data["request_timestamps"] = [
        ts for ts in context.user_data["request_timestamps"] if current_time - ts < 60
    ]
    
    # بررسی تعداد درخواست‌ها
    if len(context.user_data["request_timestamps"]) >= 20:
        return False
    
    context.user_data["request_timestamps"].append(current_time)
    return True

# تعریف منوی اصلی با دکمه‌های غیرشیشه‌ای
MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup([
    ["مشاوره پزشکی 🩺"],
    ["شناسایی داروها 💊", "آزمایش و نوار قلب 🩻"],
    ["راهنما ❓"]
], resize_keyboard=True, one_time_keyboard=False)

# تعریف منوهای زیر دکمه‌ها برای سؤالات رایج
MEDICAL_SUB_MENU_KEYBOARD = ReplyKeyboardMarkup([
    ["سؤالم دیگه‌ست ❓"],
    ["سرماخوردگی 🤧", "سردرد 🤕"],
    ["تب 🌡️", "برگشت به منو ⬅️"]
], resize_keyboard=True, one_time_keyboard=False)

DRUG_SUB_MENU_KEYBOARD = ReplyKeyboardMarkup([
    ["سؤالم دیگه‌ست ❓"],
    ["استامینوفن 💊", "ایبوپروفن 💊"],
    ["آموکسی‌سیلین 💊", "برگشت به منو ⬅️"]
], resize_keyboard=True, one_time_keyboard=False)

LAB_ECG_SUB_MENU_KEYBOARD = ReplyKeyboardMarkup([
    ["سؤالم دیگه‌ست ❓"],
    ["قند خون 🩺", "کلسترول 🩺"],
    ["نوار قلب ❤️", "برگشت به منو ⬅️"]
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
        await update.message.reply_text(welcome_message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="MarkdownV2")
        return

    welcome_message = clean_text(
        f"سلام {user_name}!\nبه دستیار پزشکی هوشمند خوش اومدی! 🩺\n"
        "یکی از گزینه‌های زیر رو انتخاب کن:"
    )
    await update.message.reply_text(welcome_message, reply_markup=MAIN_MENU_KEYBOARD, parse_mode="MarkdownV2")

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
            ]),
            parse_mode="MarkdownV2"
        )
        return

    welcome_message = clean_text(
        f"آفرین {user_name}! حالا که تو کانال عضوی، دستیار پزشکی برات فعال شد! 🩺\n"
        "یکی از گزینه‌های زیر رو انتخاب کن:"
    )
    await query.edit_message_text(welcome_message, reply_markup=MAIN_MENU_KEYBOARD, parse_mode="MarkdownV2")

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception_type((requests.exceptions.RequestException,)))
async def send_api_request(payload):
    """ارسال درخواست به API با retry"""
    return requests.post(TEXT_API_URL, json=payload, timeout=20)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت پیام‌های متنی کاربر"""
    user_id = update.effective_user.id
    message_text = update.message.text
    chat_id = update.message.chat_id

    logger.info(f"پیام دریافتی از کاربر {user_id}: {message_text}, mode: {context.user_data.get('mode')}")

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
        await update.message.reply_text(welcome_message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="MarkdownV2")
        return

    # بررسی محدودیت نرخ درخواست‌ها
    if not check_rate_limit(context, user_id):
        await update.message.reply_text(
            clean_text("لطفاً چند لحظه صبر کن! 😊 تعداد درخواست‌هات خیلی زیاده!"),
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="MarkdownV2"
        )
        return

    # اعتبارسنجی ورودی متنی
    if len(message_text) > 500:
        await update.message.reply_text(
            clean_text("پیامت خیلی طولانیه! 😅 لطفاً حداکثر 500 کاراکتر بنویس."),
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="MarkdownV2"
        )
        return

    # تعریف سؤالات از پیش‌تنظیم‌شده برای دکمه‌های سریع
    quick_questions = {
        "سرماخوردگی 🤧": "برای سرماخوردگی چی خوبه؟ راهکارهای خانگی و داروهای بدون نسخه رو بگو.",
        "سردرد 🤕": "علت سردرد چیه و چه داروهایی برای تسکینش مناسبه؟",
        "تب 🌡️": "تب دارم، چیکار کنم؟ چه داروهایی مناسبه و کی باید به پزشک مراجعه کنم؟",
        "استامینوفن 💊": "کاربرد، عوارض و دوز استامینوفن رو توضیح بده.",
        "ایبوپروفن 💊": "کاربرد، عوارض و دوز ایبوپروفن رو توضیح بده.",
        "آموکسی‌سیلین 💊": "کاربرد، عوارض و دوز آموکسی‌سیلین رو توضیح بده.",
        "قند خون 🩺": "قند خون نرمال چقدره؟ اگه بالا یا پایین باشه چیکار کنم؟",
        "کلسترول 🩺": "کلسترول بالا یعنی چی؟ چه راهکارهایی برای کاهشش وجود داره؟",
        "نوار قلب ❤️": "نوار قلب چی نشون می‌ده؟ نتایجش چطور تفسیر می‌شه؟"
    }

    # انتخاب منوی زیر دکمه‌ها بر اساس mode
    mode = context.user_data.get("mode")
    sub_menu = MAIN_MENU_KEYBOARD
    if mode == "ai_chat":
        sub_menu = MEDICAL_SUB_MENU_KEYBOARD
    elif mode == "drug_identification":
        sub_menu = DRUG_SUB_MENU_KEYBOARD
    elif mode == "lab_ecg":
        sub_menu = LAB_ECG_SUB_MENU_KEYBOARD

    if message_text == "مشاوره پزشکی 🩺":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "ai_chat"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            clean_text(
                "**مشاوره پزشکی فعال شد! 🩺**\n\n"
                "یکی از گزینه‌های زیر رو انتخاب کن یا سؤالت رو بنویس.\n"
                "*مثلاً بپرس: برای سرماخوردگی چی خوبه؟*"
            ),
            reply_markup=MEDICAL_SUB_MENU_KEYBOARD,
            parse_mode="MarkdownV2"
        )
    elif message_text == "شناسایی داروها 💊":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "drug_identification"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            clean_text(
                "**شناسایی داروها فعال شد! 💊**\n\n"
                "یکی از داروهای زیر رو انتخاب کن یا اسم دارو و سؤالت رو بنویس.\n"
                "*مثلاً بپرس: عوارض استامینوفن چیه؟*"
            ),
            reply_markup=DRUG_SUB_MENU_KEYBOARD,
            parse_mode="MarkdownV2"
        )
    elif message_text == "آزمایش و نوار قلب 🩻":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "lab_ecg"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            clean_text(
                "**تحلیل آزمایش و نوار قلب فعال شد! 🩻**\n\n"
                "یکی از گزینه‌های زیر رو انتخاب کن، تصویر آزمایش/نوار قلب بفرست، یا سؤالت رو بنویس.\n"
                "*مثلاً بپرس: قند خون 120 یعنی چی؟*"
            ),
            reply_markup=LAB_ECG_SUB_MENU_KEYBOARD,
            parse_mode="MarkdownV2"
        )
    elif message_text == "راهنما ❓":
        guide_message = clean_text(
            "**📖 راهنمای استفاده از دستیار پزشکی**\n\n"
            "- **مشاوره پزشکی 🩺**: درباره بیماری‌ها، علائم یا راهکارهای عمومی سؤال کن.\n"
            "- **شناسایی داروها 💊**: درباره کاربرد، عوارض یا دوز داروها بپرس.\n"
            "- **آزمایش و نوار قلب 🩻**: تصویر برگه آزمایش یا نوار قلب بفرست تا تحلیل کنم.\n"
            "- *همیشه برای تشخیص یا درمان با پزشک مشورت کن!* 🩺\n\n"
            "**سؤالی داری؟ یکی از گزینه‌های منو رو انتخاب کن! 😊**"
        )
        await update.message.reply_text(guide_message, reply_markup=MAIN_MENU_KEYBOARD, parse_mode="MarkdownV2")
    elif message_text == "برگشت به منو ⬅️":
        if user_id in AI_CHAT_USERS:
            AI_CHAT_USERS.remove(user_id)
        context.user_data.clear()
        await update.message.reply_text(
            clean_text("**به منوی اصلی برگشتی! 😊**\nیکی از گزینه‌ها رو انتخاب کن:"),
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="MarkdownV2"
        )
    elif message_text == "سؤالم دیگه‌ست ❓":
        if mode == "ai_chat":
            await update.message.reply_text(
                clean_text("**سؤالت درباره بیماری یا موضوع پزشکی چیه؟ 😊**\n*مثلاً بپرس: برای سرماخوردگی چی خوبه؟*"),
                reply_markup=MEDICAL_SUB_MENU_KEYBOARD,
                parse_mode="MarkdownV2"
            )
        elif mode == "drug_identification":
            await update.message.reply_text(
                clean_text("**اسم دارو یا سؤالت رو بنویس! 😊**\n*مثلاً بپرس: عوارض استامینوفن چیه؟*"),
                reply_markup=DRUG_SUB_MENU_KEYBOARD,
                parse_mode="MarkdownV2"
            )
        elif mode == "lab_ecg":
            await update.message.reply_text(
                clean_text("**سؤالت درباره آزمایش یا نوار قلب چیه؟ 😊**\n*مثلاً بپرس: قند خون 120 یعنی چی؟*"),
                reply_markup=LAB_ECG_SUB_MENU_KEYBOARD,
                parse_mode="MarkdownV2"
            )
        else:
            await update.message.reply_text(
                clean_text("**لطفاً یکی از گزینه‌های منو رو انتخاب کن! 😊**"),
                reply_markup=MAIN_MENU_KEYBOARD,
                parse_mode="MarkdownV2"
            )
    elif user_id in AI_CHAT_USERS and mode in ["ai_chat", "drug_identification", "lab_ecg"]:
        message_id = update.message.message_id
        with PROCESSING_LOCK:
            if message_id in PROCESSED_MESSAGES:
                logger.warning(f"پیام تکراری با message_id: {message_id} - نادیده گرفته شد")
                return
            PROCESSED_MESSAGES.add(message_id)

        # استفاده از سؤال از پیش‌تنظیم‌شده یا پیام کاربر
        user_message = quick_questions.get(message_text, message_text)
        chat_history = context.user_data.get("chat_history", [])
        chat_history.append({"role": "user", "content": user_message})
        # محدود کردن تاریخچه به 10 پیام
        if len(chat_history) > 10:
            chat_history = chat_history[-10:]
        context.user_data["chat_history"] = chat_history

        # انتخاب پرامپ سیستمی
        system_message = SYSTEM_MESSAGES.get(mode, SYSTEM_MESSAGES["ai_chat"])

        # ارسال پیام موقت
        temp_message = await update.message.reply_text(clean_text("**🩺**"), parse_mode="MarkdownV2")

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
            response = await send_api_request(payload)
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=temp_message.message_id)
            except TelegramError as e:
                logger.error(f"خطا در حذف پیام موقت: {e}")

            if response.status_code == 200:
                response_data = response.json()
                ai_response = response_data.get("choices", [{}])[0].get("message", {}).get("content", "پاسخی دریافت نشد!")
                ai_response = clean_text(ai_response.strip())
                chat_history.append({"role": "assistant", "content": ai_response})
                context.user_data["chat_history"] = chat_history[-10:]  # محدود کردن تاریخچه
                # بررسی هشدارهای پزشکی
                warning = ""
                if "خطرناک" in ai_response.lower() or "فوراً" in ai_response.lower():
                    warning = "\n**هشدار! 🚨** این مورد ممکنه جدی باشه! فوراً با پزشک مشورت کن."
                await update.message.reply_text(
                    f"{ai_response}{warning}",
                    reply_markup=sub_menu,
                    parse_mode="MarkdownV2"
                )
            else:
                await update.message.reply_text(
                    clean_text("**اوپس، سیستم پزشکی‌مون یه لحظه قفل کرد! 🩺**\nلطفاً دوباره سؤالت رو بفرست. 😊"),
                    reply_markup=sub_menu,
                    parse_mode="MarkdownV2"
                )
        except Exception as e:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=temp_message.message_id)
            except TelegramError as e:
                logger.error(f"خطا در حذف پیام موقت: {e}")
            logger.error(f"خطا در اتصال به API چت: {e}")
            await update.message.reply_text(
                clean_text("**اوه، انگار ابزار تشخیص‌مون نیاز به بررسی داره! 💉**\nلطفاً دوباره سؤالت رو بفرست. 😊"),
                reply_markup=sub_menu,
                parse_mode="MarkdownV2"
            )
    else:
        await update.message.reply_text(
            clean_text("**لطفاً یکی از گزینه‌های منو رو انتخاب کن! 😊**"),
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="MarkdownV2"
        )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت عکس‌های ارسالی و تحلیل با API Pollinations"""
    user_id = update.effective_user.id
    mode = context.user_data.get("mode")
    if user_id not in AI_CHAT_USERS or mode != "lab_ecg":
        await update.message.reply_text(
            clean_text("**لطفاً برای تحلیل تصویر، گزینه 'آزمایش و نوار قلب' رو از منو انتخاب کن! 😊**"),
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="MarkdownV2"
        )
        return

    # بررسی محدودیت نرخ درخواست‌ها
    if not check_rate_limit(context, user_id):
        await update.message.reply_text(
            clean_text("**لطفاً چند لحظه صبر کن! 😊 تعداد درخواست‌هات خیلی زیاده!**"),
            reply_markup=LAB_ECG_SUB_MENU_KEYBOARD,
            parse_mode="MarkdownV2"
        )
        return

    # اعتبارسنجی فرمت تصویر
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    if not file.file_path.lower().endswith(('.jpg', '.jpeg', '.png')):
        await update.message.reply_text(
            clean_text("**فقط تصاویر JPG یا PNG پذیرفته می‌شن! 😅**\nلطفاً تصویر مناسب بفرست."),
            reply_markup=LAB_ECG_SUB_MENU_KEYBOARD,
            parse_mode="MarkdownV2"
        )
        return

    message_id = update.message.message_id
    with PROCESSING_LOCK:
        if message_id in PROCESSED_MESSAGES:
            logger.warning(f"پیام تکراری با message_id: {message_id} - نادیده گرفته شد")
            return
        PROCESSED_MESSAGES.add(message_id)

    chat_id = update.message.chat_id
    temp_message = await update.message.reply_text(clean_text("**🩺**"), parse_mode="MarkdownV2")

    file_url = file.file_path
    caption = update.message.caption if update.message.caption else "این تصویر پزشکی (مثل برگه آزمایش یا نوار قلب) چیه؟ به‌صورت خلاصه و دقیق تحلیل کن! 🩺"
    if len(caption) > 500:
        await update.message.reply_text(
            clean_text("**کپشن خیلی طولانیه! 😅**\nلطفاً حداکثر 500 کاراکتر بنویس."),
            reply_markup=LAB_ECG_SUB_MENU_KEYBOARD,
            parse_mode="MarkdownV2"
        )
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=temp_message.message_id)
        except TelegramError as e:
            logger.error(f"خطا در حذف پیام موقت: {e}")
        return

    chat_history = context.user_data.get("chat_history", [])
    image_message = {
        "role": "user",
        "content": [
            {"type": "text", "text": caption},
            {"type": "image_url", "image_url": {"url": file_url}}
        ]
    }
    chat_history.append(image_message)
    if len(chat_history) > 10:
        chat_history = chat_history[-10:]
    context.user_data["chat_history"] = chat_history

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
        response = await send_api_request(payload)
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=temp_message.message_id)
        except TelegramError as e:
            logger.error(f"خطا در حذف پیام موقت: {e}")

        if response.status_code == 200:
            response_data = response.json()
            ai_response = response_data.get("choices", [{}])[0].get("message", {}).get("content", "پاسخی دریافت نشد!")
            ai_response = clean_text(ai_response.strip())
            chat_history.append({"role": "assistant", "content": ai_response})
            context.user_data["chat_history"] = chat_history[-10:]
            # بررسی هشدارهای پزشکی
            warning = ""
            if "خطرناک" in ai_response.lower() or "فوراً" in ai_response.lower():
                warning = "\n**هشدار! 🚨** این مورد ممکنه جدی باشه! فوراً با پزشک مشورت کن."
            await update.message.reply_text(
                f"{ai_response}{warning}",
                reply_markup=LAB_ECG_SUB_MENU_KEYBOARD,
                parse_mode="MarkdownV2"
            )
        else:
            await update.message.reply_text(
                clean_text("**اوه، دستگاه تحلیل‌مون نیاز به تنظیم داره! 💉**\nلطفاً دوباره عکس رو بفرست. 🩻"),
                reply_markup=LAB_ECG_SUB_MENU_KEYBOARD,
                parse_mode="MarkdownV2"
            )
    except Exception as e:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=temp_message.message_id)
        except TelegramError as e:
            logger.error(f"خطا در حذف پیام موقت: {e}")
        logger.error(f"خطا در تحلیل تصویر: {e}")
        await update.message.reply_text(
            clean_text("**اوپس، اسکنر پزشکی‌مون یه لحظه خاموش شد! 🩺**\nلطفاً دوباره عکس رو بفرست. 😊"),
            reply_markup=LAB_ECG_SUB_MENU_KEYBOARD,
            parse_mode="MarkdownV2"
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت خطاها"""
    logger.error(f"خطا رخ داد: {context.error}")
    error_message = "اوپس، سیستم کلینیکی‌مون یه لحظه قطع شد! 🩻 لطفاً دوباره امتحان کن. 😊"
    if isinstance(context.error, NetworkError):
        error_message = "مشکل اتصال به اینترنت! 🌐 لطفاً اتصالت رو چک کن و دوباره امتحان کن."
    elif isinstance(context.error, TimedOut):
        error_message = "پاسخ خیلی طول کشید! ⏳ لطفاً دوباره سؤالت رو بفرست."
    elif isinstance(context.error, BadRequest):
        error_message = "اوپس، درخواستت مشکل داره! 😅 لطفاً دوباره امتحان کن."
    
    if update and hasattr(update, 'message') and update.message:
        await update.message.reply_text(
            clean_text(f"**{error_message}**"),
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="MarkdownV2"
        )
    elif update and hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.message.reply_text(
            clean_text(f"**{error_message}**"),
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="MarkdownV2"
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
