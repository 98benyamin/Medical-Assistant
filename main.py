import asyncio
import logging
import requests
import re
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram.error import TelegramError, NetworkError, TimedOut
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
شما یک دستیار پزشکی هوشمند و حرفه‌ای هستید که به کاربران در حوزه سلامت و پزشکی کمک می‌کنید. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده، اما همیشه اطلاعات دقیق و علمی ارائه کن. پاسخ‌ها رو با قالب‌بندی Markdown (مثل **بولد**، *ایتالیک*، یا - لیست) ارائه بده. وظایف شما:

1. **پاسخ به سؤالات پزشکی عمومی**:
   - اگر کاربر درباره بیماری‌ها و داروهای مناسب پرسید، داروهای عمومی (مثل *استامینوفن*، *ایبوپروفن*، *آموکسی‌سیلین*) و کاربردهاشون رو توضیح بده.
   - برای بیماری‌های ساده (مثل سرماخوردگی، سردرد)، راهکارهای عمومی و داروهای بدون نسخه پیشنهاد بده.
   - اگر موضوع تخصصی یا پیچیده بود، بنویس: **این مورد تخصصیه! 🚨 بهتره با یه پزشک متخصص مشورت کنی.**

2. **هشدارهای پزشکی**:
   - اگر علائم خطرناک (مثل تب بالای 40 درجه یا تنگی نفس شدید) تشخیص دادی، یک هشدار جداگونه با این قالب اضافه کن: **⚠️ هشدار: این علامت ممکنه جدی باشه! فوراً به پزشک مراجعه کن.**

3. **نکات مهم**:
   - همیشه یادآوری کن که اطلاعات شما جایگزین نظر پزشک نیست.
   - پاسخ‌ها رو خلاصه، دقیق و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 🩺، ❤️، 💊) استفاده کن.
   - اگر سؤال غیرمرتبط بود، بگو: *این موضوع به پزشکی ربطی نداره! اگه سؤال پزشکی داری، خوشحال می‌شم کمک کنم! 😊*
   - ارسال لینک ممنوع است.

**مثال سؤال:** سرماخوردگی چی بخورم؟ سردرد دارم چیکار کنم؟
با این اصول، کاربر رو راهنمایی کن! 🚀
""",
    "lab_test": """
شما یک دستیار پزشکی هوشمند هستید که در تحلیل برگه‌های آزمایش تخصص داره. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده و از قالب‌بندی Markdown استفاده کن. وظایف شما:

1. **تحلیل برگه آزمایش**:
   - شاخص‌های کلیدی (مثل *گلبول‌های سفید*، *هموگلوبین*، *قند خون*) رو استخراج کن و توضیح بده چی نشون می‌دن.
   - اگر مقادیر غیرعادی باشه، بنویس: **این مقدار خارج از محدوده نرماله! 🩺 برای تشخیص دقیق با پزشک مشورت کن.**
   - اگر تصویر واضح نبود، بنویس: *تصویر واضح نیست! لطفاً تصویر بهتری بفرست.*

2. **پاسخ به سؤالات متنی**:
   - اگر کاربر درباره نتایج آزمایش سؤال کرد (مثل قند خون 120)، توضیح بده.

3. **هشدارهای پزشکی**:
   - اگر مقادیر خطرناک (مثل قند خون بالای 200 یا کم‌خونی شدید) دیدی، هشدار بده: **⚠️ هشدار: این مقدار ممکنه جدی باشه! فوراً به پزشک مراجعه کن.**

4. **راهنمایی کاربر**:
   - بگو: *تصویر برگه آزمایش بفرست یا سؤالت درباره نتایج چیه؟ مثلاً: قند خون 150 یعنی چی؟ 🧪*

**نکات مهم**:
   - پاسخ‌ها رو خلاصه و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 🧪، 🩺) استفاده کن.
   - اگر تصویر یا سؤال غیرمرتبط بود، بگو: *این به آزمایش ربطی نداره! لطفاً تصویر یا سؤال مرتبط بفرست. 😊*
   - ارسال لینک ممنوع است.
""",
    "ecg": """
شما یک دستیار پزشکی هوشمند هستید که در تحلیل نوار قلب (ECG) تخصص داره. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده و از قالب‌بندی Markdown استفاده کن. وظایف شما:

1. **تحلیل نوار قلب**:
   - الگوهای اصلی (مثل *ریتم*، *فاصله‌ها*، یا *ناهنجاری‌های واضح*) رو تحلیل کن و توضیح بده ممکنه چی نشون بدن.
   - بنویس: **تحلیل نوار قلب نیاز به بررسی تخصصی داره. حتماً با یه متخصص قلب مشورت کن. ❤️**
   - اگر تصویر واضح نبود، بنویس: *تصویر واضح نیست! لطفاً تصویر بهتری بفرست.*

2. **هشدارهای پزشکی**:
   - اگر ناهنجاری خطرناک (مثل آریتمی شدید) دیدی، هشدار بده: **⚠️ هشدار: این ممکنه جدی باشه! فوراً به متخصص قلب مراجعه کن.**

3. **راهنمایی کاربر**:
   - بگو: *تصویر نوار قلب بفرست یا سؤالت درباره ECG چیه؟ مثلاً: ریتم نامنظم یعنی چی؟ 📈*

**نکات مهم**:
   - پاسخ‌ها رو خلاصه و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 📈، ❤️) استفاده کن.
   - اگر تصویر یا سؤال غیرمرتبط بود، بگو: *این به نوار قلب ربطی نداره! لطفاً تصویر یا سؤال مرتبط بفرست. 😊*
   - ارسال لینک ممنوع است.
""",
    "radiology": """
شما یک دستیار پزشکی هوشمند هستید که در تفسیر تصاویر رادیولوژی (مثل X-ray، CT، MRI) تخصص داره. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده و از قالب‌بندی Markdown استفاده کن. وظایف شما:

1. **تحلیل تصاویر رادیولوژی**:
   - مشکلات احتمالی (مثل *شکستگی*، *توده*، یا *عفونت*) رو شناسایی کن و توضیح بده.
   - بنویس: **تفسیر رادیولوژی نیاز به بررسی تخصصی داره. حتماً با یه رادیولوژیست یا پزشک مشورت کن. 🩻**
   - اگر تصویر واضح نبود، بنویس: *تصویر واضح نیست! لطفاً تصویر بهتری بفرست.*

2. **هشدارهای پزشکی**:
   - اگر مشکل خطرناک (مثل توده مشکوک یا شکستگی شدید) دیدی، هشدار بده: **⚠️ هشدار: این ممکنه جدی باشه! فوراً به پزشک مراجعه کن.**

3. **راهنمایی کاربر**:
   - بگو: *تصویر رادیولوژی (مثل X-ray یا CT) بفرست یا سؤالت چیه؟ مثلاً: این سایه تو X-ray چیه؟ 🩻*

**نکات مهم**:
   - پاسخ‌ها رو خلاصه و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 🩻، 🩺) استفاده کن.
   - اگر تصویر یا سؤال غیرمرتبط بود، بگو: *این به رادیولوژی ربطی نداره! لطفاً تصویر یا سؤال مرتبط بفرست. 😊*
   - ارسال لینک ممنوع است.
""",
    "symptom_diagnosis": """
شما یک دستیار پزشکی هوشمند هستید که در تشخیص احتمالی بیماری‌ها بر اساس علائم تخصص داره. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده و از قالب‌بندی Markdown استفاده کن. وظایف شما:

1. **تشخیص احتمالی**:
   - بر اساس علائم کاربر (مثل *تب*، *سرفه*، *سردرد*)، بیماری‌های احتمالی رو لیست کن و توضیح بده.
   - بنویس: **این فقط یه تشخیص اولیه‌ست! 🩺 برای تشخیص دقیق حتماً با پزشک مشورت کن.**

2. **هشدارهای پزشکی**:
   - اگر علائم خطرناک (مثل *تب بالای 40 درجه*، *تنگی نفس شدید*) گزارش شد، هشدار بده: **⚠️ هشدار: این علامت ممکنه جدی باشه! فوراً به پزشک مراجعه کن.**

3. **راهنمایی کاربر**:
   - بگو: *علائمت رو کامل بگو (مثل تب، سرفه، مدت زمان). مثلاً: دو روزه تب دارم و سرفه می‌کنم، چیه؟ 🧫*

**نکات مهم**:
   - پاسخ‌ها رو خلاصه و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 🧫، 🩺) استفاده کن.
   - اگر علائم کافی نبود، بگو: *لطفاً علائم بیشتری بگو تا بهتر راهنمایی کنم! 😊*
   - ارسال لینک ممنوع است.
""",
    "drug_identification": """
شما یک دستیار پزشکی هوشمند هستید که در شناسایی داروها و ارائه اطلاعات دارویی تخصص داره. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده و از قالب‌بندی Markdown استفاده کن. وظایف شما:

1. **شناسایی دارو از تصویر**:
   - اگر کاربر تصویر قرص یا جعبه دارو فرستاد، نام دارو، کاربرد و دوز معمول رو شناسایی کن.
   - اگر تصویر واضح نبود، بنویس: *تصویر واضح نیست! لطفاً تصویر بهتری بفرست.*

2. **پاسخ به سؤالات دارویی**:
   - درباره *کاربرد*، *عوارض*، *دوز* یا *موارد منع مصرف* توضیح بده.
   - مثال: برای *استامینوفن*، بنویس برای کاهش درد و تب، دوز معمول 500-1000 میلی‌گرم هر 6 ساعت، و عوارض احتمالی مثل مشکلات کبدی.

3. **هشدار تداخل دارویی**:
   - اگر کاربر چند دارو رو نام برد، تداخل‌های احتمالی رو هشدار بده. مثلاً: **⚠️ هشدار: ایبوپروفن و آسپرین ممکنه تداخل داشته باشن! با پزشک مشورت کن.**

4. **راهنمایی کاربر**:
   - بگو: *تصویر قرص یا جعبه بفرست، یا بپرس: عوارض آسپرین چیه؟ دوز آموکسی‌سیلین چقدره؟ 💊*

**نکات مهم**:
   - همیشه یادآوری کن که مصرف دارو باید تحت نظر پزشک باشه.
   - پاسخ‌ها رو خلاصه و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 💊، 🩺) استفاده کن.
   - اگر سؤال غیرمرتبط بود، بگو: *این به داروها ربطی نداره! لطفاً درباره دارو بپرس. 😊*
   - ارسال لینک ممنوع است.
""",
    "mental_health": """
شما یک دستیار پزشکی هوشمند هستید که در ارزیابی سلامت روان لحظه‌ای تخصص داره. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده و از قالب‌بندی Markdown استفاده کن. وظایف شما:

1. **ارزیابی سلامت روان**:
   - از کاربر سؤالات کوتاه بپرس (مثل *حالت چطوره؟*، *اخیراً استرس داشتی؟*) یا متن چت رو تحلیل کن.
   - مشکلات احتمالی (مثل *استرس*، *اضطراب*، *افسردگی*) رو شناسایی کن.
   - تمرین‌های آرام‌سازی (مثل تنفس عمیق) یا توصیه‌های کوتاه پیشنهاد بده.

2. **هشدارهای پزشکی**:
   - اگر علائم شدید (مثل افکار خودکشی یا اضطراب شدید) دیدی، هشدار بده: **⚠️ هشدار: این ممکنه جدی باشه! لطفاً با یه روانشناس یا پزشک صحبت کن.**

3. **راهنمایی کاربر**:
   - بگو: *درباره حالت بگو (مثل استرس، بی‌خوابی) یا به چند سؤالم جواب بده تا کمکت کنم! 🧠*

**نکات مهم**:
   - پاسخ‌ها رو خلاصه و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 🧠، 😊) استفاده کن.
   - اگر سؤال غیرمرتبط بود، بگو: *این به سلامت روان ربطی نداره! لطفاً درباره حالت بگو. 😊*
   - ارسال لینک ممنوع است.
""",
    "wound_care": """
شما یک دستیار پزشکی هوشمند هستید که در تحلیل زخم‌ها تخصص داره. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده و از قالب‌بندی Markdown استفاده کن. وظایف شما:

1. **تحلیل تصویر زخم**:
   - شدت زخم، احتمال عفونت (مثل *قرمزی*، *چرک*) و نکات مراقبتی رو تحلیل کن.
   - بنویس: **برای درمان دقیق زخم، حتماً با پزشک مشورت کن. 🩺**
   - اگر تصویر واضح نبود، بنویس: *تصویر واضح نیست! لطفاً تصویر بهتری بفرست.*

2. **هشدارهای پزشکی**:
   - اگر علائم عفونت شدید (مثل چرک زیاد یا تب) دیدی، هشدار بده: **⚠️ هشدار: این زخم ممکنه عفونی باشه! فوراً به پزشک مراجعه کن.**

3. **راهنمایی کاربر**:
   - بگو: *تصویر زخم رو بفرست یا علائم (مثل قرمزی، درد) رو بگو تا راهنمایی کنم! 🩹*

**نکات مهم**:
   - پاسخ‌ها رو خلاصه و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 🩹، 🩺) استفاده کن.
   - اگر تصویر یا سؤال غیرمرتبط بود، بگو: *این به زخم ربطی نداره! لطفاً تصویر یا سؤال مرتبط بفرست. 😊*
   - ارسال لینک ممنوع است.
""",
    "dental_health": """
شما یک دستیار پزشکی هوشمند هستید که در سلامت دهان و دندان تخصص داره. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده و از قالب‌بندی Markdown استفاده کن. وظایف شما:

1. **تحلیل مشکلات دندانی**:
   - اگر کاربر تصویر دندان فرستاد، مشکلات مثل *پوسیدگی*، *التهاب لثه* یا *پلاک* رو شناسایی کن.
   - اگر کاربر علائم (مثل درد دندان، خونریزی لثه) گفت، توضیح بده و توصیه بده.
   - بنویس: **برای درمان دندانی، حتماً با یه دندانپزشک مشورت کن. 🦷**

2. **هشدارهای پزشکی**:
   - اگر مشکل شدید (مثل آبسه یا درد شدید) دیدی، هشدار بده: **⚠️ هشدار: این ممکنه جدی باشه! فوراً به دندانپزشک مراجعه کن.**

3. **راهنمایی کاربر**:
   - بگو: *تصویر دندان بفرست یا علائم (مثل درد، خونریزی لثه) رو بگو تا راهنمایی کنم! 🦷*

**نکات مهم**:
   - پاسخ‌ها رو خلاصه و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 🦷، 🩺) استفاده کن.
   - اگر تصویر یا سؤال غیرمرتبط بود، بگو: *این به دندان ربطی نداره! لطفاً تصویر یا سؤال مرتبط بفرست. 😊*
   - ارسال لینک ممنوع است.
"""
}

# مجموعه کاربران در حالت چت و قفل برای پردازش پیام‌ها
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
    ["مشاوره پزشکی 🩺", "تشخیص علائم 🧫"],
    ["بررسی آزمایش 🧪", "تحلیل نوار قلب 📈"],
    ["تفسیر رادیولوژی 🩻", "شناسایی داروها 💊"],
    ["سلامت روان لحظه‌ای 🧠", "مراقبت از زخم 🩹"],
    ["سلامت دهان و دندان 🦷", "راهنما ❓"]
], resize_keyboard=True, one_time_keyboard=False)

# تعریف منوی زیر دکمه‌ها با دکمه برگشت
SUB_MENU_KEYBOARD = ReplyKeyboardMarkup([
    ["برگشت به منو ⬅️"]
], resize_keyboard=True, one_time_keyboard=False)

async def check_rate_limit(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
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
    
    # افزودن زمان درخواست جدید
    context.user_data["request_timestamps"].append(current_time)
    return True

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
            "لطفاً تو کانال عضو شو و بعد دکمه *عضو شدم* رو بزن! 🚑"
        )
        keyboard = [
            [InlineKeyboardButton("عضو کانال شو 📢", url=CHANNEL_LINK)],
            [InlineKeyboardButton("عضو شدم! ✅", callback_data="check_membership")]
        ]
        await update.message.reply_text(
            welcome_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    welcome_message = clean_text(
        f"سلام {user_name}!\nبه *دستیار پزشکی هوشمند* خوش اومدی! 🩺\n"
        "یکی از گزینه‌های زیر رو انتخاب کن:"
    )
    await update.message.reply_text(
        welcome_message,
        reply_markup=MAIN_MENU_KEYBOARD,
        parse_mode="Markdown"
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
                f"اوپس! 😅 هنوز تو کانال عضو نشدی!\n"
                "لطفاً تو کانال عضو شو و دوباره دکمه *عضو شدم* رو بزن! 🚑"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("عضو کانال شو 📢", url=CHANNEL_LINK)],
                [InlineKeyboardButton("عضو شدم! ✅", callback_data="check_membership")]
            ]),
            parse_mode="Markdown"
        )
        return

    welcome_message = clean_text(
        f"آفرین {user_name}! حالا که تو کانال عضوی، *دستیار پزشکی* برات فعال شد! 🩺\n"
        "یکی از گزینه‌های زیر رو انتخاب کن:"
    )
    await query.edit_message_text(
        welcome_message,
        reply_markup=MAIN_MENU_KEYBOARD,
        parse_mode="Markdown"
    )

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
            "لطفاً تو کانال عضو شو و بعد دکمه *عضو شدم* رو بزن! 🚑"
        )
        keyboard = [
            [InlineKeyboardButton("عضو کانال شو 📢", url=CHANNEL_LINK)],
            [InlineKeyboardButton("عضو شدم! ✅", callback_data="check_membership")]
        ]
        await update.message.reply_text(
            welcome_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    # بررسی محدودیت نرخ درخواست‌ها
    if not await check_rate_limit(context, user_id):
        await update.message.reply_text(
            clean_text("لطفاً چند لحظه صبر کن! 😊 تعداد درخواست‌هات زیاد شده."),
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
        return

    # مدیریت دکمه‌های منوی اصلی
    if message_text == "مشاوره پزشکی 🩺":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "ai_chat"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            clean_text(
                "🤖 *دستیار پزشکی* فعال شد!\n\n"
                "سؤالت درباره بیماری یا موضوع پزشکی چیه؟\n"
                "مثلاً بپرس: *سرماخوردگی چی بخورم؟* یا *سردرد دارم چیکار کنم؟* 😊"
            ),
            reply_markup=SUB_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "بررسی آزمایش 🧪":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "lab_test"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            clean_text(
                "🧪 *بررسی آزمایش* فعال شد!\n\n"
                "تصویر برگه آزمایش بفرست یا سؤالت رو بگو!\n"
                "مثلاً: *قند خون 150 یعنی چی؟* 😊"
            ),
            reply_markup=SUB_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "تحلیل نوار قلب 📈":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "ecg"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            clean_text(
                "📈 *تحلیل نوار قلب* فعال شد!\n\n"
                "تصویر نوار قلب بفرست یا سؤالت رو بگو!\n"
                "مثلاً: *ریتم نامنظم یعنی چی؟* 😊"
            ),
            reply_markup=SUB_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "تفسیر رادیولوژی 🩻":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "radiology"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            clean_text(
                "🩻 *تفسیر رادیولوژی* فعال شد!\n\n"
                "تصویر رادیولوژی (مثل X-ray یا CT) بفرست یا سؤالت رو بگو!\n"
                "مثلاً: *این سایه تو X-ray چیه؟* 😊"
            ),
            reply_markup=SUB_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "تشخیص علائم 🧫":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "symptom_diagnosis"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            clean_text(
                "🧫 *تشخیص علائم* فعال شد!\n\n"
                "علائمت رو کامل بگو (مثل تب، سرفه، مدت زمان)!\n"
                "مثلاً: *دو روزه تب دارم و سرفه می‌کنم، چیه؟* 😊"
            ),
            reply_markup=SUB_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "شناسایی داروها 💊":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "drug_identification"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            clean_text(
                "💊 *شناسایی داروها* فعال شد!\n\n"
                "تصویر قرص یا جعبه بفرست، یا سؤالت رو بگو!\n"
                "مثلاً: *عوارض آسپرین چیه؟* یا *دوز آموکسی‌سیلین چقدره؟* 😊"
            ),
            reply_markup=SUB_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "سلامت روان لحظه‌ای 🧠":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "mental_health"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            clean_text(
                "🧠 *سلامت روان لحظه‌ای* فعال شد!\n\n"
                "درباره حالت بگو (مثل استرس، بی‌خوابی) یا به چند سؤالم جواب بده!\n"
                "مثلاً: *اخیراً استرس دارم، چیکار کنم؟* 😊"
            ),
            reply_markup=SUB_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "مراقبت از زخم 🩹":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "wound_care"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            clean_text(
                "🩹 *مراقبت از زخم* فعال شد!\n\n"
                "تصویر زخم بفرست یا علائم (مثل قرمزی، درد) رو بگو!\n"
                "مثلاً: *زخمم قرمز شده، چیکار کنم؟* 😊"
            ),
            reply_markup=SUB_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "سلامت دهان و دندان 🦷":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "dental_health"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            clean_text(
                "🦷 *سلامت دهان و دندان* فعال شد!\n\n"
                "تصویر دندان بفرست یا علائم (مثل درد، خونریزی لثه) رو بگو!\n"
                "مثلاً: *دندونم درد می‌کنه، چیکار کنم؟* 😊"
            ),
            reply_markup=SUB_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "راهنما ❓":
        guide_message = clean_text(
            "📖 *راهنمای استفاده از دستیار پزشکی*:\n\n"
            "- **مشاوره پزشکی 🩺**: درباره بیماری‌ها یا علائم سؤال کن.\n"
            "- **تشخیص علائم 🧫**: علائمت رو بگو تا تشخیص احتمالی بدم.\n"
            "- **بررسی آزمایش 🧪**: برگه آزمایش بفرست یا درباره نتایج بپرس.\n"
            "- **تحلیل نوار قلب 📈**: تصویر نوار قلب بفرست.\n"
            "- **تفسیر رادیولوژی 🩻**: تصویر X-ray یا CT بفرست.\n"
            "- **شناسایی داروها 💊**: تصویر قرص یا سؤال درباره دارو بفرست.\n"
            "- **سلامت روان لحظه‌ای 🧠**: درباره استرس یا حالت روحی بگو.\n"
            "- **مراقبت از زخم 🩹**: تصویر زخم بفرست یا علائم رو بگو.\n"
            "- **سلامت دهان و دندان 🦷**: تصویر دندان یا علائم دندانی بفرست.\n\n"
            "*همیشه برای تشخیص یا درمان با پزشک مشورت کن!* 🩺\n"
            "سؤالی داری؟ یکی از گزینه‌ها رو انتخاب کن! 😊"
        )
        await update.message.reply_text(
            guide_message,
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "برگشت به منو ⬅️":
        if user_id in AI_CHAT_USERS:
            AI_CHAT_USERS.remove(user_id)
        context.user_data.clear()
        await update.message.reply_text(
            clean_text("به *منوی اصلی* برگشتی! 😊 یکی از گزینه‌ها رو انتخاب کن:"),
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif user_id in AI_CHAT_USERS and context.user_data.get("mode") in SYSTEM_MESSAGES.keys():
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
        temp_message = await update.message.reply_text(clean_text("🩺 *در حال پردازش...*"), parse_mode="Markdown")

        payload = {
            "model": "openai-large",
            "messages": [
                {"role": "system", "content": system_message}
            ] + chat_history,
            "max_tokens": 300,
            "seed": 42,
            "json_mode": False
        }

        # مکانیزم retry برای درخواست API
        for attempt in range(2):
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
                    await update.message.reply_text(
                        ai_response,
                        reply_markup=SUB_MENU_KEYBOARD,
                        parse_mode="Markdown"
                    )
                    break
                else:
                    await update.message.reply_text(
                        clean_text("اوپس، *سیستم پزشکی‌مون* یه لحظه قفل کرد! 🩺 لطفاً دوباره سؤالت رو بفرست. 😊"),
                        reply_markup=SUB_MENU_KEYBOARD,
                        parse_mode="Markdown"
                    )
                    break
            except requests.exceptions.RequestException as e:
                logger.error(f"خطا در اتصال به API چت (تلاش {attempt + 1}): {e}")
                if attempt == 1:
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=temp_message.message_id)
                    except TelegramError as e:
                        logger.error(f"خطا در حذف پیام موقت: {e}")
                    await update.message.reply_text(
                        clean_text("اوه، *ابزار تشخیص‌مون* نیاز به بررسی داره! 💉 لطفاً دوباره سؤالت رو بفرست. 😊"),
                        reply_markup=SUB_MENU_KEYBOARD,
                        parse_mode="Markdown"
                    )
    else:
        await update.message.reply_text(
            clean_text("لطفاً یکی از گزینه‌های *منو* رو انتخاب کن! 😊"),
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="Markdown"
        )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت عکس‌های ارسالی و تحلیل با API Pollinations"""
    user_id = update.effective_user.id
    valid_modes = ["lab_test", "ecg", "radiology", "drug_identification", "wound_care", "dental_health"]
    if user_id not in AI_CHAT_USERS or context.user_data.get("mode") not in valid_modes:
        await update.message.reply_text(
            clean_text("لطفاً برای تحلیل تصویر، گزینه مرتبط رو از *منو* انتخاب کن! 😊"),
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
        return

    # بررسی محدودیت نرخ درخواست‌ها
    if not await check_rate_limit(context, user_id):
        await update.message.reply_text(
            clean_text("لطفاً چند لحظه صبر کن! 😊 تعداد درخواست‌هات زیاد شده."),
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
        return

    message_id = update.message.message_id
    with PROCESSING_LOCK:
        if message_id in PROCESSED_MESSAGES:
            logger.warning(f"پیام تکراری با message_id: {message_id} - نادیده گرفته شد")
            return
        PROCESSED_MESSAGES.add(message_id)

    chat_id = update.message.chat_id
    temp_message = await update.message.reply_text(clean_text("🔬 *در حال تحلیل تصویر...*"), parse_mode="Markdown")

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_url = file.file_path

    caption = update.message.caption if update.message.caption else "این تصویر چیه؟ به‌صورت خلاصه و دقیق تحلیل کن! 🩺"
    mode = context.user_data.get("mode")

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

    # انتخاب پرامپ سیستمی بر اساس mode
    system_message = SYSTEM_MESSAGES[mode]

    payload = {
        "model": "openai-large",
        "messages": [
            {"role": "system", "content": system_message}
        ] + chat_history,
        "max_tokens": 300,
        "seed": 42,
        "json_mode": False
    }

    # مکانیزم retry برای درخواست API
    for attempt in range(2):
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
                await update.message.reply_text(
                    ai_response,
                    reply_markup=SUB_MENU_KEYBOARD,
                    parse_mode="Markdown"
                )
                break
            else:
                await update.message.reply_text(
                    clean_text("اوه، *دستگاه تحلیل‌مون* نیاز به تنظیم داره! 💉 لطفاً دوباره عکس رو بفرست. 🩻"),
                    reply_markup=SUB_MENU_KEYBOARD,
                    parse_mode="Markdown"
                )
                break
        except requests.exceptions.RequestException as e:
            logger.error(f"خطا در تحلیل تصویر (تلاش {attempt + 1}): {e}")
            if attempt == 1:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=temp_message.message_id)
                except TelegramError as e:
                    logger.error(f"خطا در حذف پیام موقت: {e}")
                await update.message.reply_text(
                    clean_text("اوپس، *اسکنر پزشکی‌مون* یه لحظه خاموش شد! 🩺 لطفاً دوباره عکس رو بفرست. 😊"),
                    reply_markup=SUB_MENU_KEYBOARD,
                    parse_mode="Markdown"
                )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت خطاها"""
    logger.error(f"خطا رخ داد: {context.error}")
    error_message = "اوپس، *سیستم کلینیکی‌مون* یه لحظه قطع شد! 🩻 لطفاً دوباره امتحان کن. 😊"
    
    if isinstance(context.error, NetworkError):
        error_message = "مشکل *اتصال به شبکه* داریم! 🛜 لطفاً دوباره امتحان کن. 😊"
    elif isinstance(context.error, TimedOut):
        error_message = "درخواست *بیش از حد طول کشید*! ⏳ لطفاً دوباره امتحان کن. 😊"
    
    if update and hasattr(update, 'message') and update.message:
        await update.message.reply_text(
            clean_text(error_message),
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif update and hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.message.reply_text(
            clean_text(error_message),
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="Markdown"
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
