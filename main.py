import asyncio
import logging
import requests
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram.error import TelegramError
from bs4 import BeautifulSoup  # اضافه شده اما استفاده نشده
from fastapi import FastAPI, Request
from fastapi.responses import Response
import uvicorn
from threading import Lock
from datetime import datetime, timedelta
from collections import defaultdict
from utils import PersistentStorage, BackupManager, RateLimiter, ErrorReporter, ReminderSystem, AutoReporter

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

# تنظیمات مدیر
ADMIN_ID = "6753257929"  # آیدی عددی مدیر به صورت رشته

# ایجاد نمونه‌های سیستم‌های جدید
storage = PersistentStorage()
backup_manager = BackupManager()
rate_limiter = RateLimiter(max_requests=5, time_window=60)
error_reporter = ErrorReporter(ADMIN_ID)
reminder_system = ReminderSystem()
auto_reporter = AutoReporter(ADMIN_ID)

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

class Statistics:
    def __init__(self):
        self.storage = storage
        self.load_from_storage()

    def load_from_storage(self):
        stored_stats = self.storage.data["stats"]
        self.total_users = stored_stats.get("total_users", 0)
        self.daily_users = defaultdict(set, stored_stats.get("daily_users", {}))
        self.total_queries = stored_stats.get("total_queries", 0)
        self.image_analyses = stored_stats.get("image_analyses", 0)
        self.user_sessions = stored_stats.get("user_sessions", {})
        self.popular_topics = defaultdict(int, stored_stats.get("popular_topics", {}))
        self.active_users = set(stored_stats.get("active_users", []))
        self.last_activity = stored_stats.get("last_activity", {})

    async def add_user(self, user_id: int):
        """ثبت کاربر جدید"""
        self.total_users += 1
        today = datetime.now().strftime('%Y-%m-%d')
        self.daily_users[today].add(user_id)
        self.active_users.add(user_id)
        self.last_activity[user_id] = datetime.now()
        await self.storage.update_stats(self)

    async def log_query(self, user_id: int, query_type: str, query_text: str):
        """ثبت پرسش جدید"""
        self.total_queries += 1
        if query_type == 'image':
            self.image_analyses += 1
        
        # بروزرسانی آخرین فعالیت
        self.last_activity[user_id] = datetime.now()
        
        # ذخیره موضوعات پرتکرار
        keywords = self.extract_keywords(query_text)
        for keyword in keywords:
            self.popular_topics[keyword] += 1
            
        await self.storage.update_stats(self)

    def extract_keywords(self, text: str) -> list:
        """استخراج کلمات کلیدی از متن"""
        common_medical_terms = ['سردرد', 'تب', 'درد', 'فشار خون', 'دیابت', 'قلب']
        return [word for word in text.split() if word in common_medical_terms]

    async def get_dashboard_stats(self) -> str:
        """تولید آمار داشبورد"""
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        stats = {
            "📊 آمار کلی": {
                "👥 تعداد کل کاربران": self.total_users,
                "🆕 کاربران جدید امروز": len(self.daily_users[today]),
                "👤 کاربران دیروز": len(self.daily_users[yesterday]),
                "❓ تعداد کل پرسش‌ها": self.total_queries,
                "🖼 تحلیل تصاویر": self.image_analyses
            },
            "📈 موضوعات پرتکرار": dict(sorted(self.popular_topics.items(), 
                                            key=lambda x: x[1], 
                                            reverse=True)[:5]),
            "👥 کاربران فعال": len([uid for uid, last in self.last_activity.items() 
                                 if datetime.now() - last < timedelta(days=1)])
        }
        
        return self.format_stats(stats)

    def format_stats(self, stats: dict) -> str:
        """فرمت‌بندی آمار برای نمایش"""
        output = "📊 داشبورد مدیریت ربات پزشکی\n\n"
        
        for section, data in stats.items():
            output += f"{section}:\n"
            if isinstance(data, dict):
                for key, value in data.items():
                    output += f"{key}: {value}\n"
            else:
                output += f"{data}\n"
            output += "\n"
            
        return output

# ایجاد نمونه از کلاس آمار
stats = Statistics()

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
    """
    نقطه ورود پایه برای بررسی سرور و پینگ UptimeRobot.
    برای جلوگیری از خوابیدن سرویس در پلن رایگان Render، از UptimeRobot برای ارسال درخواست GET به این endpoint هر 5 دقیقه استفاده کنید.
    مراحل تنظیم UptimeRobot:
    1. در UptimeRobot ثبت‌نام کنید (https://uptimerobot.com/).
    2. یک مانیتور جدید از نوع HTTP(s) ایجاد کنید.
    3. URL را روی https://medical-assistant-rum5.onrender.com/ تنظیم کنید.
    4. بازه زمانی را روی 5 دقیقه قرار دهید.
    5. مانیتور را ذخیره کنید و مطمئن شوید پاسخ 200 OK دریافت می‌شود.
    لاگ‌های Render را چک کنید تا درخواست‌های پینگ هر 5 دقیقه ثبت شوند.
    """
    # بررسی هدر User-Agent برای شناسایی درخواست‌های UptimeRobot
    user_agent = request.headers.get("User-Agent", "Unknown")
    if "UptimeRobot" in user_agent:
        logger.info("دریافت درخواست پینگ از UptimeRobot")
    else:
        logger.info(f"دریافت درخواست به / از User-Agent: {user_agent}")
    
    # پاسخ به درخواست
    try:
        response = {"message": "Bot is running!"}
        return response
    except Exception as e:
        logger.error(f"خطا در پاسخ به درخواست پینگ: {e}")
        raise

@app.head("/")
async def root_head():
    """
    پشتیبانی از متد HEAD برای پینگ‌های UptimeRobot.
    این endpoint به درخواست‌های HEAD پاسخ می‌دهد تا از خطای 405 جلوگیری شود.
    """
    return Response(status_code=200)

@app.get("/favicon.ico")
async def favicon():
    """
    پاسخ به درخواست‌های favicon.ico برای جلوگیری از خطای 404.
    در حال حاضر یک پاسخ خالی با کد 204 برمی‌گرداند.
    """
    return Response(status_code=204)  # No Content

def clean_text(text):
    """پاک‌سازی متن از تبلیغات و کاراکترهای غیرضروری"""
    if not text:
        return ""
    # حذف متن بعد از ---
    if '---' in text:
        text = text.split('---')[0].strip()
    # حذف کاراکترهای غیرضروری
    text = text.replace("*", "").replace("`", "").replace("]", "").replace("!", "!")
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
    """مدیریت دستور شروع"""
    user_id = update.effective_user.id
    user_name = update.message.from_user.first_name

    # ثبت کاربر جدید در آمار
    await stats.add_user(user_id)

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
        "می‌تونی درباره بیماری‌ها، داروها، برگه آزمایش یا نوار قلب سؤال کنی. چی تو سرته؟ 🧑🏻‍⚕"
    )
    
    # دکمه‌های پایه برای همه کاربران
    keyboard = [
        [InlineKeyboardButton("شروع مشاوره پزشکی 🤖", callback_data="chat_with_ai")],
        [InlineKeyboardButton("راهنما ❓", callback_data="help")]
    ]
    
    # اضافه کردن دکمه مدیریت فقط برای مدیر
    if str(user_id) == ADMIN_ID:
        admin_keyboard = [[InlineKeyboardButton("پنل مدیریت 👨‍💻", callback_data="admin_panel")]]
        keyboard.extend(admin_keyboard)
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

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
                f"اوپس! 😅 هنوز تو کانال عضو نشدی\n"
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
        "می‌تونی درباره بیماری‌ها، داروها، برگه آزمایش یا نوار قلب سؤال کنی. چی تو سرته؟ 🧑🏻‍⚕"
    )
    
    # دکمه‌های پایه برای همه کاربران
    keyboard = [
        [InlineKeyboardButton("شروع مشاوره پزشکی 🤖", callback_data="chat_with_ai")],
        [InlineKeyboardButton("راهنما ❓", callback_data="help")]
    ]
    
    # اضافه کردن دکمه مدیریت فقط برای مدیر
    if str(user_id) == ADMIN_ID:
        admin_keyboard = [[InlineKeyboardButton("پنل مدیریت 👨‍💻", callback_data="admin_panel")]]
        keyboard.extend(admin_keyboard)
    
    await query.edit_message_text(
        welcome_message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

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

    # بررسی محدودیت نرخ درخواست
    if not await rate_limiter.check_limit(user_id):
        await update.message.reply_text(
            clean_text("⏳ لطفاً کمی صبر کنید و دوباره تلاش کنید. برای جلوگیری از سوء استفاده، تعداد درخواست‌ها محدود شده است.")
        )
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
        await error_reporter.report_error(context.bot, e, "AI Message Handler")
        await update.message.reply_text(
            clean_text("اوه، انگار ابزار تشخیص‌مون نیاز به بررسی داره! 💉 لطفاً دوباره سؤالت رو بفرست. 😊"),
            reply_markup=reply_markup
        )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت عکس‌های ارسالی و تحلیل با API Pollinations"""
    user_id = update.effective_user.id
    if user_id not in AI_CHAT_USERS or context.user_data.get("mode") != "ai_chat":
        return

    # بررسی محدودیت نرخ درخواست
    if not await rate_limiter.check_limit(user_id):
        await update.message.reply_text(
            clean_text("⏳ لطفاً کمی صبر کنید و دوباره تلاش کنید. برای جلوگیری از سوء استفاده، تعداد درخواست‌ها محدود شده است.")
        )
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
        await error_reporter.report_error(context.bot, e, "Photo Handler")
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
        "می‌تونی درباره بیماری‌ها، داروها، برگه آزمایش یا نوار قلب سؤال کنی. چی تو سرته؟ 🧑🏻‍⚕"
    )
    
    # دکمه‌های پایه برای همه کاربران
    keyboard = [
        [InlineKeyboardButton("شروع مشاوره پزشکی 🤖", callback_data="chat_with_ai")],
        [InlineKeyboardButton("راهنما ❓", callback_data="help")]
    ]
    
    # اضافه کردن دکمه مدیریت فقط برای مدیر
    if str(user_id) == ADMIN_ID:
        admin_keyboard = [[InlineKeyboardButton("پنل مدیریت 👨‍💻", callback_data="admin_panel")]]
        keyboard.extend(admin_keyboard)
    
    await query.message.edit_text(
        welcome_message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت خطاها"""
    error = context.error
    logger.error(f"خطا رخ داد: {error}")
    
    # گزارش خطا به مدیر
    try:
        await error_reporter.report_error(context.bot, error, "Error Handler")
    except Exception as e:
        logger.error(f"خطا در گزارش خطا به مدیر: {e}")
    
    # پاسخ به کاربر
    if update and hasattr(update, 'message') and update.message:
        await update.message.reply_text(clean_text("اوپس، سیستم کلینیکی‌مون یه لحظه قطع شد! 🩻 لطفاً دوباره امتحان کن. 😊"))
    elif update and hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.message.reply_text(clean_text("اوپس، سیستم کلینیکی‌مون یه لحظه قطع شد! 🩻 لطفاً دوباره امتحان کن. 😊"))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش راهنمای ربات"""
    help_text = """
    🩺 راهنمای استفاده از دستیار پزشکی:
    
    1️⃣ سؤال پزشکی:
       - هر سؤالی در مورد بیماری‌ها و داروها بپرسید
       - راهنمایی درباره علائم و درمان‌های عمومی
    
    2️⃣ تحلیل آزمایش:
       - عکس برگه آزمایش خود را ارسال کنید
       - دریافت تحلیل شاخص‌های مهم
    
    3️⃣ تحلیل نوار قلب:
       - تصویر ECG خود را ارسال کنید
       - بررسی الگوهای اصلی
    
    ⚠️ یادآوری مهم:
    این ربات جایگزین مشاوره پزشک نیست!
    برای موارد حاد و تخصصی حتماً به پزشک مراجعه کنید.
    """
    keyboard = [
        [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="back_to_home")]
    ]
    await update.callback_query.message.edit_text(
        clean_text(help_text),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش پنل مدیریت"""
    user_id = update.callback_query.from_user.id
    
    if str(user_id) != ADMIN_ID:
        await update.callback_query.answer("شما دسترسی به این بخش را ندارید! ⛔️")
        return
    
    # دریافت آمار
    dashboard_text = await stats.get_dashboard_stats()
    
    keyboard = [
        [InlineKeyboardButton("🔄 بروزرسانی آمار", callback_data="refresh_stats")],
        [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="back_to_home")]
    ]
    
    await update.callback_query.message.edit_text(
        dashboard_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def refresh_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بروزرسانی آمار در پنل مدیریت"""
    user_id = update.callback_query.from_user.id
    
    if str(user_id) != ADMIN_ID:
        await update.callback_query.answer("شما دسترسی به این بخش را ندارید! ⛔️")
        return
    
    await admin_panel(update, context)

async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور پشتیبانی"""
    support_text = """
👨‍💼 پشتیبانی فنی:
برای گزارش مشکلات یا پیشنهادات می‌توانید:
1. پیام خود را به @admin ارسال کنید
2. از طریق ایمیل support@example.com با ما در تماس باشید
3. در ساعات اداری با شماره 021-XXXXXXX تماس بگیرید

⏰ ساعات پاسخگویی:
شنبه تا چهارشنبه: 9:00 تا 17:00
پنجشنبه: 9:00 تا 13:00
    """
    keyboard = [
        [InlineKeyboardButton("📞 تماس با پشتیبانی", url="https://t.me/admin")],
        [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="back_to_home")]
    ]
    await update.message.reply_text(
        clean_text(support_text),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def create_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ایجاد پشتیبان از داده‌ها"""
    user_id = update.callback_query.from_user.id
    
    if str(user_id) != ADMIN_ID:
        await update.callback_query.answer("شما دسترسی به این بخش را ندارید! ⛔️")
        return
    
    try:
        backup_file = backup_manager.create_backup(storage.filename)
        await update.callback_query.answer("✅ پشتیبان با موفقیت ایجاد شد!")
        await update.callback_query.message.reply_text(
            f"📦 پشتیبان جدید ایجاد شد:\n{backup_file}"
        )
    except Exception as e:
        await error_reporter.report_error(context.bot, e, "Backup Creation")
        await update.callback_query.answer("❌ خطا در ایجاد پشتیبان!")
        await update.callback_query.message.reply_text(
            "متأسفانه در ایجاد پشتیبان خطایی رخ داد. لطفاً دوباره تلاش کنید."
        )

async def main():
    """راه‌اندازی ربات"""
    global application
    try:
        application = Application.builder().token(TOKEN).read_timeout(60).write_timeout(60).connect_timeout(60).build()
        
        # تنظیم وب‌هوک
        await application.bot.set_webhook(url=WEBHOOK_URL)
        
        # اضافه کردن هندلرها
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("support", support_command))
        application.add_handler(CallbackQueryHandler(check_membership, pattern="^check_membership$"))
        application.add_handler(CallbackQueryHandler(chat_with_ai, pattern="^chat_with_ai$"))
        application.add_handler(CallbackQueryHandler(help_command, pattern="^help$"))
        application.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
        application.add_handler(CallbackQueryHandler(refresh_stats, pattern="^refresh_stats$"))
        application.add_handler(CallbackQueryHandler(create_backup, pattern="^create_backup$"))
        application.add_handler(CallbackQueryHandler(back_to_home, pattern="^back_to_home$"))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai_message))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        
        # اضافه کردن هندلر خطا
        application.add_error_handler(error_handler)
        
        # شروع ربات
        await application.initialize()
        await application.start()
        
        # راه‌اندازی FastAPI
        config = uvicorn.Config(app, host="0.0.0.0", port=8000)
        server = uvicorn.Server(config)
        
        # ایجاد پشتیبان اولیه
        backup_manager.create_backup(storage.filename)
        
        # شروع چک کردن یادآوری‌ها
        asyncio.create_task(check_reminders_periodically(application.bot))
        
        # شروع ارسال گزارش‌های خودکار
        asyncio.create_task(send_auto_reports_periodically(application.bot))
        
        await server.serve()
        
    except Exception as e:
        logger.error(f"خطا در راه‌اندازی ربات: {e}")
        raise

async def check_reminders_periodically(bot):
    """چک کردن دوره‌ای یادآوری‌ها"""
    while True:
        try:
            await reminder_system.check_reminders(bot)
        except Exception as e:
            logger.error(f"خطا در چک کردن یادآوری‌ها: {e}")
        await asyncio.sleep(60)  # هر دقیقه چک کن

async def send_auto_reports_periodically(bot):
    """ارسال دوره‌ای گزارش‌های خودکار"""
    while True:
        try:
            await auto_reporter.send_daily_report(bot, stats)
        except Exception as e:
            logger.error(f"خطا در ارسال گزارش خودکار: {e}")
        await asyncio.sleep(3600)  # هر ساعت چک کن

if __name__ == "__main__":
    asyncio.run(main())
