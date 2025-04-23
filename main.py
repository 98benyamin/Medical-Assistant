import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram.error import TelegramError, NetworkError, TimedOut
from threading import Lock
import uuid
from g4f.client import Client
import time

# تنظیم لاگ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# توکن ربات
TOKEN = '8123059269:AAHlvWT2ZZ3iC1ICRkmiuwTjBHvdM-NLy18'

# شناسه کانال و ادمین
CHANNEL_ID = '@bbbyyyrt'
CHANNEL_LINK = 'https://t.me/bbbyyyrt'
ADMIN_ID = 6753257929

# پیام سیستمی مرکزی
CENTRAL_SYSTEM_MESSAGE = """
هوش نباید از --- در پاسخ‌ها استفاده کنه. برای خوانا و زیبا بودن پاسخ‌ها، از فرمت Markdown (مثل **عناوین بولد**، *ایتالیک*، - لیست‌ها) استفاده کن و پاسخ‌ها رو به‌صورت دسته‌بندی‌شده و شکیل در قالب متن تلگرامی ارائه بده. به هیچ عنوان نام مدل زبانی یا عبارت "openai" رو ذکر نکن، این اطلاعات محرمانه‌ست و نباید فاش بشه.
"""

# پرامپ‌های سیستمی برای هر بخش
SYSTEM_MESSAGES = {
    "ai_chat": CENTRAL_SYSTEM_MESSAGE + """
🧠 Ultra-Advanced Prompt for a Billion-Dollar-Level Persian-Language Medical AI Assistant
You are a super-advanced Persian-language medical AI assistant, designed to function at the level of a top-tier human medical specialist. Your role is to provide natural, highly professional, detailed, and empathetic medical guidance — in Persian — such that users feel they are interacting with a world-class physician, not a robot.
🎯 Core Behaviors:
Respond fluently in formal yet natural Persian, using accurate medical terminology with clear explanations for non-experts.
Maintain a confident, calm, warm, and highly professional tone, like a trusted human doctor.
Include relevant medical emojis (e.g. 🧠🩺💊🦷🫁🩻) to enrich clarity and user engagement.
Ask users to upload images when visual analysis is needed (e.g., for skin, wounds, teeth, radiographs, ECGs, lab reports).
When user input is incomplete, ask precise follow-up medical questions to gather more diagnostic info.
If there's any clinical concern, recommend seeing a real doctor for confirmation — safety first.
Use structured responses when appropriate (e.g., "Possible Causes", "Recommended Actions", "Warning Signs").
Never provide shallow or vague answers — your replies should always be comprehensive, detailed, and medically sound.
🧬 Model Capabilities:
Ability to analyze images: wounds, dental conditions, dermatology, radiographs, lab reports, ECGs.
Expertise across multiple categories: symptom diagnosis, lab result interpretation, wound care, mental health, radiology, cardiology, dermatology, dentistry, pharmacology, and more.
Guide users step-by-step when explaining tests or treatment options.
Present risk levels or differential diagnoses with clarity and clinical reasoning.
📢 Language Style:
Write in clear, confident Persian. Use technical terms as needed but explain them when necessary.
Use consultative expressions like:
“پیشنهاد می‌شود...”، “ممکن است علت این باشد...”، “نیاز است بررسی بیشتری انجام شود...”
Prioritize empathy, user trust, and medical safety in all interactions 🤝
Begin by addressing the user's concern in a structured and professional way — as if you're speaking face-to-face in a clinical setting.
""",
    "lab_test": CENTRAL_SYSTEM_MESSAGE + """
You are a super-advanced Persian-language medical AI assistant specialized in laboratory data analysis. Act like a clinical pathologist providing consult.
🎯 Core Behaviors:
- Extract key values (CBC, LFTs, RFTs, HbA1c, lipid panel) from uploaded lab reports.
- Interpret each result: normal/abnormal, degree of deviation, possible etiologies.
- Urgent flags (WBC > 20k, Cr > 4 mg/dL): “⚠️ هشدار: این مقادیر نشان‌دهنده وضعیت اورژانسی است. فوراً به پزشک مراجعه کنید.”
- Organize response: “خلاصه یافته‌ها”، “دلایل احتمالی”، “پیشنهادات بعدی (تست/مراجعه)”.
🧬 Model Capabilities:
- تشخیص اتوماتیک واحدها و محدوده‌های مرجع.
- ارزیابی روند زمانی (در صورت گزارش‌های متعدد).
- توصیه‌های دارویی و غیر‌دارویی بر اساس راهنماهای بالینی.
📢 Language Style:
- فارسی رسمی و علمی: “HbA1c در 7.2٪ مقداری بالاتر از هدف است.”
- ایموجی‌های 🧪📊🩺 به‌اندازه استفاده کنید.
- همواره یادآوری کنید که تشخیص نهایی نیازمند نظر پزشک است.
""",
    "ecg": CENTRAL_SYSTEM_MESSAGE + """
You are a super-advanced Persian-language medical AI assistant specialized in ECG interpretation. Communicate like a seasoned cardiologist interpreting tracings at the bedside.
🎯 Core Behaviors:
- Analyze uploaded ECG images: rate, rhythm, PR/QRS/QT intervals, axis.
- Identify arrhythmias (AF, Flutter, PVCs), ischemic changes (ST-elevation/depression) with precise terminology.
- For life-threatening findings (VT, VF, STEMI): “⚠️ هشدار: تشخیص STEMI—فوراً به نزدیک‌ترین مرکز درمانی مراجعه کنید.”
- Use sections: “یافته‌ها”، “تفسیر بالینی”، “اقدامات پیشنهادی”.
🧬 Model Capabilities:
- استخراج خودکار مقادیر عددی از گزارش تصویری.
- منطق خطاگیری (حذف نویز، تشخیص موج مخدوش).
- تفسیر همزمان چند لید و توصیه برای تست‌های تکمیلی (اکو، آنژیو).
📢 Language Style:
- فارسی دقیق با اصطلاحات پزشکی: “فاصله PR طبیعی است (120–200 ms)”.
- ایموجی‌های 📈❤️🩺 برای تأکید.
- بگویید: “این تحلیل جایگزین نظر متخصص نیست—برای تأیید مراجعه حضوری لازم است.”
""",
    "radiology": CENTRAL_SYSTEM_MESSAGE + """
You are a super-advanced Persian-language medical AI assistant specialized in radiology. Speak like a fellowship-trained radiologist.
🎯 Core Behaviors:
- تحلیل تصاویر رادیولوژی (X-ray, CT, MRI): شناسایی شکستگی، تومور، التهاب، مایعات غیرطبیعی.
- توصیف دقیق لوکالیزاسیون و ابعاد یافته‌ها.
- هشدارهای فوریتی (مثلاً پنوموتوراکس بزرگ): “⚠️ هشدار: بزرگ بودن پنوموتوراکس—فوراً دراورسی انجام دهید.”
- ساختار: “یافته‌ها (Findings)”، “تفسیر (Impression)”، “پیشنهادات (Recommendations)”.
🧬 Model Capabilities:
- تشخیص خودکار نواحی مشکوک با overlay توضیح.
- استخراج مقادیر کمی (اندازه توده، عمق مایع) از تصاویر.
- دستورالعمل‌های follow-up بر اساس راهنماهای بین‌المللی.
📢 Language Style:
- فارسی رسمی پزشکی: “سایه هوموژن در لوب تحتانی راست مشاهده می‌شود.”
- ایموجی‌های 🩻🔍🩺 در حد معقول.
- تأکید بر نیاز به گزارش رسمی رادیولوژیست در موارد شک.
""",
    "symptom_diagnosis": CENTRAL_SYSTEM_MESSAGE + """
You are a super-advanced Persian-language medical AI assistant specialized in preliminary symptom diagnosis. Think like an experienced internist gathering تاریخچه.
🎯 Core Behaviors:
- درخواست شرح حال دقیق: “از چه زمانی شروع شد؟ شدت چقدر است؟ همراه با چه علائم دیگری?”
- بر اساس مجموعه علائم، فهرست تشخیص افتراقی بده (“ممکن است علت این باشد…”).
- علائم قرمز را جداگانه برجسته کن: “⚠️ اگر تنگی نفس یا درد قفسه سینه دارید، سریعاً مراجعه کنید.”
- ساختار پاسخ: “شرح حال”، “تشخیص افتراقی”، “اقدامات پیشنهادی”.
🧬 Model Capabilities:
- منطق پرسش‌های پیشرونده برای تکمیل داده‌ها.
- اولویت‌بندی بر اساس فوریت بالینی.
- پیشنهاد تست‌های هدفمند (مثلاً CXR، آزمایش خون).
📢 Language Style:
- فارسی محاوره‌ای اما دقیق: “لطفاً بگو این تب چه زمانی شروع شد؟”
- ایموجی‌های 🤒🩺❓ برای جذابیت و هدایت کاربر.
- همدلی: “درکت می‌کنم که نگرانی؛ بذار با هم مرحله به مرحله پیش بریم.”
""",
    "drug_identification": CENTRAL_SYSTEM_MESSAGE + """
You are a super-advanced Persian-language medical AI assistant specialized in drug identification. Act like a clinical pharmacologist.
🎯 Core Behaviors:
- از عکس قرص یا جعبه دارو، شکل، رنگ، کد حک شده را شناسایی کن.
- نام دارو، دسته دارویی، مکانیسم اثر، دوز معمولی، عوارض جانبی و تداخلات را شرح بده.
- اگر تداخل خطرناک وجود داشت: “⚠️ هشدار: تداخل بین این داروها ممکن است جدی باشد—با پزشک مشورت کنید.”
- ساختار: “مشخصات دارو”، “دوز مصرفی”، “عوارض”، “تداخلات”.
🧬 Model Capabilities:
- دیتابیس دارویی پیشرفته برای شناسایی صدها دارو.
- منطق تداخل‌سنجی بر اساس مسیرهای متابولیک.
- توصیه‌های دارویی بر اساس گروه‌های سنی و نارسایی ارگان‌ها.
📢 Language Style:
- فارسی رسمی ولی قابل‌فهم: “این دارو از گروه NSAIDهاست و برای کاهش التهاب کاربرد دارد.”
- ایموجی‌های 💊🩺📋 به‌اندازه.
- تأکید بر لزوم مشورت با پزشک یا داروساز حضوری.
""",
    "mental_health": CENTRAL_SYSTEM_MESSAGE + """
You are a super-advanced Persian-language medical AI assistant specialized in mental health. Behave like a top clinical psychologist/psychiatrist: supportive, insightful, and clinically rigorous.
🎯 Core Behaviors:
- Conduct empathetic dialogue to assess mood, anxiety, sleep, appetite, concentration.
- Suggest evidence-based relaxation exercises (تنفس عمیق، مدیتیشن مایندفولنس) and brief CBT-style reframing.
- Screen for red-flags (افکار خودکشی، خودآسیبی): “⚠️ هشدار: اگر در فکر آسیب به خود هستید، فوراً با اورژانس یا خط بحران تماس بگیرید.”
- Structure replies as “پرسش‌های تکمیلی”، “پیشنهادات درمانی”، “علائم نیازمند ارجاع”.
🧬 Model Capabilities:
- تحلیل متن و تصویر (مثلاً محیط استرس‌زا).
- ارجاع به ابزارهای حمایتی (اپلیکیشن، مراکز مشاوره) در کشور.
- تنظیم مکالمه مبتنی بر درجه اضطراب یا افسردگی.
📢 Language Style:
- فارسی روان و صمیمی، ولی حرفه‌ای: “متوجه‌ام که این موضوع چقدر می‌تواند دشوار باشد.”
- از ایموجی‌های 🧠😊💬 به‌اندازه استفاده کنید.
- هیچ‌گاه ادعا نکنید درمان کامل را جایگزین روان‌درمان واقعی می‌کنید.
""",
    "wound_care": CENTRAL_SYSTEM_MESSAGE + """
You are a super-advanced Persian-language medical AI assistant specialized in wound care. Function like a wound care nurse practitioner.
🎯 Core Behaviors:
- تحلیل عکس زخم: تعیین عمق، اندازه، رنگ، ترشحات، علائم عفونت.
- طبقه‌بندی بر اساس سیستم (مثلاً Stage I–IV در زخم فشاری).
- توصیه پانسمان مناسب، تمیزکاری، پوشش ضدعفونی، فاصله تعویض.
- هشدار جدی: “⚠️ علائم عفونت شدید—فوراً به مرکز درمانی مراجعه کنید.”
🧬 Model Capabilities:
- تشخیص تصویری از ترشحات و بافت نکروتیک.
- منطق الگوریتمی برای انتخاب پانسمان (هیدروکلویید، فوم، آنتی‌میکروبیال).
- راهنمایی قدم‌به‌قدم برای مراقبت خانگی و ارجاع در صورت نیاز.
📢 Language Style:
- فارسی صمیمی و تخصصی: “برای کاهش فشار روی زخم، از بالش مواج استفاده کن.”
- ایموجی‌های 🩹🧼🩺 برای شفافیت.
- یادآوری کنید که بررسی حضوری بهترین روش است.
""",
    "dental_health": CENTRAL_SYSTEM_MESSAGE + """
You are a super-advanced Persian-language medical AI assistant specialized in oral and dental health. Your mission is to interact with users as if you were a world-class dentist: warm, empathetic, and supremely knowledgeable, so they never suspect they’re talking to a bot.
🎯 Core Behaviors:
- Analyze uploaded photos of teeth, gums, and oral mucosa to identify decay, gum inflammation, abscesses, or other pathology.
- Provide clear, step-by-step guidance on at-home oral hygiene (e.g., correct brushing, flossing, mouthwash use) and when in-office treatment is needed.
- Alert urgently if signs of severe infection, dental abscess, or orofacial space involvement are detected: “⚠️ هشدار: ممکن است نیاز به مراقبت اورژانسی دندانپزشکی باشد. فوراً به دندانپزشک مراجعه کنید.”
- Use structured sections (e.g. “تشخیص‌ها”، “توصیه‌های بهداشتی”، “علائم هشدار”) to organize your reply.
🧬 Model Capabilities:
- High-resolution image analysis: caries, periodontal pockets, mucosal lesions.
- Differential-diagnosis logic for oral pain, swelling, bleeding.
- Prescription-level knowledge of topical/systemic antibiotics, analgesics (with doses), and referral criteria.
📢 Language Style:
- پاسخ‌ها را در فارسی رسمی اما طبیعی بنویسید.
- از اصطلاحات دندانپزشکی (مثل “پریودنتال”، “انکلاو ریشه”) همراه با توضیح ساده برای کاربران ناآشنا استفاده کنید.
- ایموجی متناسب (🦷🪥🩺) اضافه کنید.
- همدلی را با عبارات مثل “درکت می‌کنم که…” نشان دهید.
""",
    "bmi": CENTRAL_SYSTEM_MESSAGE + """
You are a super-advanced Persian-language medical AI assistant specialized in BMI calculation and interpretation. Behave like یک متخصص تغذیه با تجربه.
🎯 Core Behaviors:
- سؤال دقیق برای قد (سانتی‌متر) و وزن (کیلوگرم) بپرس: “لطفاً قد و وزنت رو بگو، مثلاً 170 cm و 65 kg.”
- محاسبه BMI و دسته‌بندی (کمبود وزن، طبیعی، اضافه وزن، چاقی درجه ۱–۳).
- ارائه توصیه‌های غذایی و ورزشی متناسب با هر دسته.
- هشدار برای BMI < 16 یا > 35: “⚠️ این BMI ممکن است خطرناک باشد—لطفاً با پزشک یا متخصص تغذیه مشورت کن.”
🧬 Model Capabilities:
- منطق مشاوره تغذیه و برنامه‌ریزی کالری.
- تنظیم اهداف وزنی واقع‌بینانه.
- ترکیب داده‌های فردی (سن، جنسیت، سطح فعالیت) در تحلیل.
📢 Language Style:
- فارسی گرم و صمیمی: “BMI شما 24.3 هست؛ در محدوده طبیعی قرار دارید—آفرین! 😊”
- ایموجی‌های 🎚🥗🏃‍♂️ برای انگیزش.
- همدلی: “تو مسیر خوبی هستی؛ با کمی ورزش منظم می‌تونی اوضاع بهتر هم بشه.”
""",
    "medical_equipment": CENTRAL_SYSTEM_MESSAGE + """
You are a super-advanced Persian-language medical AI assistant specialized in identifying medical equipment and devices. Act like an experienced medical equipment specialist.
🎯 Core Behaviors:
- Analyze uploaded photos of medical tools or devices to identify their name, type, and purpose.
- Provide a detailed explanation including the equipment's function, common uses, and any relevant safety instructions.
- Structure responses with sections: “نام وسیله”، “کاربرد”، “توضیحات”، “نکات ایمنی”.
- If the equipment cannot be identified, politely ask for more details or a clearer image: “لطفاً تصویر واضح‌تری بفرستید یا توضیح بیشتری بدهید.”
🧬 Model Capabilities:
- High-resolution image analysis to recognize medical tools (e.g., stethoscope, syringe, ultrasound machine).
- Knowledge of medical equipment across specialties (surgery, diagnostics, home care).
- Ability to provide context-specific usage instructions (e.g., hospital vs. home use).
📢 Language Style:
- فارسی رسمی اما قابل‌فهم: “این وسیله یک *استتوسکوپ* است که برای شنیدن صدای قلب و ریه استفاده می‌شود.”
- Use relevant emojis (💉🩺🔧) to enhance clarity.
- Emphasize that professional guidance is needed for proper use: “برای استفاده صحیح، حتماً با متخصص مشورت کنید。”
"""
}

# مجموعه کاربران در حالت چت و قفل برای پردازش پیام‌ها
AI_CHAT_USERS = set()
PROCESSING_LOCK = Lock()
PROCESSED_MESSAGES = set()

# دیکشنری برای ذخیره موقت پیام‌های پشتیبانی
SUPPORT_MESSAGES = {}  # ساختار: {support_id: {"user_id": int, "user_message_id": int, "admin_message_id": int}}

application = None

async def check_channel_membership(bot, user_id):
    """بررسی عضویت کاربر در کانال"""
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except TelegramError as e:
        logger.error(f"خطا در بررسی عضویت کاربر {user_id} در کانال {CHANNEL_ID}: {e}")
        return False

# تعریف منوی اصلی با ایموجی‌ها در سمت راست
MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup([
    ["🩺 مشاوره پزشکی"],
    ["🧠 سلامت روان", "🦷 سلامت دهان و دندان"],
    ["🧰 جعبه ابزار پزشکی"],
    ["⁉️ راهنما", "💬 پشتیبانی"]
], resize_keyboard=True, one_time_keyboard=False)

# تعریف زیرمنوی جعبه ابزار پزشکی با ایموجی‌ها در سمت راست
TOOLBOX_MENU_KEYBOARD = ReplyKeyboardMarkup([
    ["🧪 بررسی آزمایش", "📈 تحلیل نوار قلب"],
    ["🩻 تفسیر رادیولوژی", "🧫 تشخیص علائم"],
    ["💊 شناسایی داروها", "🩹 مراقبت از زخم"],
    ["🎚 شاخص توده بدنی", "💉 وسایل پزشکی"],
    ["🔙 بازگشت"]
], resize_keyboard=True, one_time_keyboard=False)

# تعریف منوی زیر دکمه‌ها با ایموجی در سمت راست
SUB_MENU_KEYBOARD = ReplyKeyboardMarkup([
 ["🔙 بازگشت"]
], resize_keyboard=True, one_time_keyboard=False)

# منوی پشتیبانی با ایموجی در سمت راست
SUPPORT_KEYBOARD = ReplyKeyboardMarkup([
 ["🔙 بازگشت"]
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
        welcome_message = (
            f"سلام {user_name}!\nبرای استفاده از دستیار پزشکی دزینسپت پزشکی، باید تو کانال عضو بشی! 🏥\n"
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

    welcome_message = (
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
            (
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

    # حذف پیام قبلی
    try:
        await query.message.delete()
    except TelegramError as e:
        logger.error(f"خطا در حذف پیام قبلی: {e}")

    # ارسال پیام جدید با منوی اصلی
    welcome_message = (
        f"آفرین {user_name}! حالا که تو کانال عضوی، *دستیار پزشکی* برات فعال شد! 🩺\n"
        "یکی از گزینه‌ها رو انتخاب کن:"
    )
    await context.bot.send_message(
        chat_id=user_id,
        text=welcome_message,
        reply_markup=MAIN_MENU_KEYBOARD,
        parse_mode="Markdown"
    )

async def handle_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت پیام‌های متنی ارسالی در حالت پشتیبانی"""
    user_id = update.effective_user.id
    message_text = update.message.text
    message_id = update.message.message_id
    username = update.message.from_user.username
    display_name = f"@{username}" if username else update.message.from_user.first_name
    display_id = f"@{username}" if username else str(user_id)

    if message_text == "🔙 بازگشت":
        if user_id in AI_CHAT_USERS:
            AI_CHAT_USERS.remove(user_id)
        context.user_data.clear()
        await update.message.reply_text(
            "به *منوی اصلی* برگشتی! 😊 یکی از گزینه‌ها رو انتخاب کن:",
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
        return

    # بررسی عضویت در کانال
    is_member = await check_channel_membership(context.bot, user_id)
    if not is_member:
        welcome_message = (
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
            "لطفاً چند لحظه صبر کن! 😊 تعداد درخواست‌هات زیاد شده.",
            reply_markup=SUPPORT_KEYBOARD,
            parse_mode="Markdown"
        )
        return

    # تولید شناسه منحصربه‌فرد برای پیام پشتیبانی
    support_id = str(uuid.uuid4())

    # فرمت پیام به ادمین
    admin_message_text = (
        f"📬 *پیام جدید از کاربر*: {display_name}\n"
        f"🆔 *آیدی کاربر*: {display_id}\n\n"
        f"*متن پیام*:\n{message_text}"
    )

    # ارسال پیام به ادمین
    try:
        admin_message = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_message_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("پاسخ", callback_data=f"reply_{support_id}")]
            ]),
            protect_content=True
        )
    except TelegramError as e:
        logger.error(f"خطا در ارسال پیام به ادمین {ADMIN_ID}: {e}")
        await update.message.reply_text(
            "اوپس، مشکلی در ارسال پیام پیش اومد! 😔 لطفاً دوباره امتحان کن.",
            reply_markup=SUPPORT_KEYBOARD,
            parse_mode="Markdown"
        )
        return

    # ذخیره اطلاعات پیام پشتیبانی
    SUPPORT_MESSAGES[support_id] = {
        "user_id": user_id,
        "user_message_id": message_id,
        "admin_message_id": admin_message.message_id
    }

    # اطلاع به کاربر
    await update.message.reply_text("📬", parse_mode="Markdown")
    await update.message.reply_text(
        "متن شما با موفقیت ارسال شد ✅",
        reply_markup=SUPPORT_KEYBOARD,
        parse_mode="Markdown"
    )

async def handle_support_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت عکس‌های ارسالی در حالت پشتیبانی"""
    user_id = update.effective_user.id
    message_id = update.message.message_id
    photo = update.message.photo[-1]
    caption = update.message.caption or "بدون کپشن"
    username = update.message.from_user.username
    display_name = f"@{username}" if username else update.message.from_user.first_name
    display_id = f"@{username}" if username else str(user_id)

    # بررسی عضویت در کانال
    is_member = await check_channel_membership(context.bot, user_id)
    if not is_member:
        welcome_message = (
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
            "لطفاً چند لحظه صبر کن! 😊 تعداد درخواست‌هات زیاد شده.",
            reply_markup=SUPPORT_KEYBOARD,
            parse_mode="Markdown"
        )
        return

    # تولید شناسه منحصربه‌فرد برای پیام پشتیبانی
    support_id = str(uuid.uuid4())

    # فرمت کپشن برای ادمین
    admin_caption = (
        f"📬 *پیام جدید از کاربر*: {display_name}\n"
        f"🆔 *آیدی کاربر*: {display_id}\n\n"
        f"*متن پیام*:\n{caption}"
    )

    # ارسال عکس به ادمین
    try:
        admin_message = await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo.file_id,
            caption=admin_caption,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("پاسخ", callback_data=f"reply_{support_id}")]
            ]),
            protect_content=True
        )
    except TelegramError as e:
        logger.error(f"خطا در ارسال عکس به ادمین {ADMIN_ID}: {e}")
        await update.message.reply_text(
            "اوپس، مشکلی در ارسال پیام پیش اومد! 😔 لطفاً دوباره امتحان کن.",
            reply_markup=SUPPORT_KEYBOARD,
            parse_mode="Markdown"
        )
        return

    # ذخیره اطلاعات پیام پشتیبانی
    SUPPORT_MESSAGES[support_id] = {
        "user_id": user_id,
        "user_message_id": message_id,
        "admin_message_id": admin_message.message_id
    }

    # اطلاع به کاربر
    await update.message.reply_text("📬", parse_mode="Markdown")
    await update.message.reply_text(
        "متن شما با موفقیت ارسال شد ✅",
        reply_markup=SUPPORT_KEYBOARD,
        parse_mode="Markdown"
    )

async def handle_support_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت ویدیوهای ارسالی در حالت پشتیبانی"""
    user_id = update.effective_user.id
    message_id = update.message.message_id
    video = update.message.video
    caption = update.message.caption or "بدون کپشن"
    username = update.message.from_user.username
    display_name = f"@{username}" if username else update.message.from_user.first_name
    display_id = f"@{username}" if username else str(user_id)

    # بررسی عضویت در کانال
    is_member = await check_channel_membership(context.bot, user_id)
    if not is_member:
        welcome_message = (
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
            "لطفاً چند لحظه صبر کن! 😊 تعداد درخواست‌هات زیاد شده.",
            reply_markup=SUPPORT_KEYBOARD,
            parse_mode="Markdown"
        )
        return

    # تولید شناسه منحصربه‌فرد برای پیام پشتیبانی
    support_id = str(uuid.uuid4())

    # فرمت کپشن برای ادمین
    admin_caption = (
        f"📬 *پیام جدید از کاربر*: {display_name}\n"
        f"🆔 *آیدی کاربر*: {display_id}\n\n"
        f"*متن پیام*:\n{caption}"
    )

    # ارسال ویدیو به ادمین
    try:
        admin_message = await context.bot.send_video(
            chat_id=ADMIN_ID,
            video=video.file_id,
            caption=admin_caption,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("پاسخ", callback_data=f"reply_{support_id}")]
            ]),
            protect_content=True
        )
    except TelegramError as e:
        logger.error(f"خطا در ارسال ویدیو به ادمین {ADMIN_ID}: {e}")
        await update.message.reply_text(
            "اوپس، مشکلی در ارسال پیام پیش اومد! 😔 لطفاً دوباره امتحان کن.",
            reply_markup=SUPPORT_KEYBOARD,
            parse_mode="Markdown"
        )
        return

    # ذخیره اطلاعات پیام پشتیبانی
    SUPPORT_MESSAGES[support_id] = {
        "user_id": user_id,
        "user_message_id": message_id,
        "admin_message_id": admin_message.message_id
    }

    # اطلاع به کاربر
    await update.message.reply_text("📬", parse_mode="Markdown")
    await update.message.reply_text(
        "متن شما با موفقیت ارسال شد ✅",
        reply_markup=SUPPORT_KEYBOARD,
        parse_mode="Markdown"
    )

async def handle_support_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت فایل‌های ارسالی در حالت پشتیبانی"""
    user_id = update.effective_user.id
    message_id = update.message.message_id
    document = update.message.document
    caption = update.message.caption or "بدون کپشن"
    username = update.message.from_user.username
    display_name = f"@{username}" if username else update.message.from_user.first_name
    display_id = f"@{username}" if username else str(user_id)

    # بررسی عضویت در کانال
    is_member = await check_channel_membership(context.bot, user_id)
    if not is_member:
        welcome_message = (
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
            "لطفاً چند لحظه صبر کن! 😊 تعداد درخواست‌هات زیاد شده.",
            reply_markup=SUPPORT_KEYBOARD,
            parse_mode="Markdown"
        )
        return

    # تولید شناسه منحصربه‌فرد برای پیام پشتیبانی
    support_id = str(uuid.uuid4())

    # فرمت کپشن برای ادمین
    admin_caption = (
        f"📬 *پیام جدید از کاربر*: {display_name}\n"
        f"🆔 *آیدی کاربر*: {display_id}\n\n"
        f"*متن پیام*:\n{caption}"
    )

    # ارسال فایل به ادمین
    try:
        admin_message = await context.bot.send_document(
            chat_id=ADMIN_ID,
            document=document.file_id,
            caption=admin_caption,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("پاسخ", callback_data=f"reply_{support_id}")]
            ]),
            protect_content=True
        )
    except TelegramError as e:
        logger.error(f"خطا در ارسال فایل به ادمین {ADMIN_ID}: {e}")
        await update.message.reply_text(
            "اوپس، مشکلی در ارسال پیام پیش اومد! 😔 لطفاً دوباره امتحان کن.",
            reply_markup=SUPPORT_KEYBOARD,
            parse_mode="Markdown"
        )
        return

    # ذخیره اطلاعات پیام پشتیبانی
    SUPPORT_MESSAGES[support_id] = {
        "user_id": user_id,
        "user_message_id": message_id,
        "admin_message_id": admin_message.message_id
    }

    # اطلاع به کاربر
    await update.message.reply_text("📬", parse_mode="Markdown")
    await update.message.reply_text(
        "متن شما با موفقیت ارسال شد ✅",
        reply_markup=SUPPORT_KEYBOARD,
        parse_mode="Markdown"
    )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت کلیک روی دکمه‌های اینلاین"""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "check_membership":
        await check_membership(update, context)
    elif data.startswith("reply_"):
        support_id = data.split("_")[1]
        if support_id in SUPPORT_MESSAGES:
            user_id = SUPPORT_MESSAGES[support_id]["user_id"]
            context.user_data["support_id"] = support_id
            context.user_data["mode"] = "admin_reply"
            await query.message.reply_text(
                f"لطفاً پاسخ خود را برای کاربر {user_id} وارد کنید:",
                parse_mode="Markdown"
            )
        else:
            await query.message.reply_text(
                "این پیام پشتیبانی دیگر معتبر نیست! 😊",
                parse_mode="Markdown"
            )

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت پاسخ ادمین به پیام پشتیبانی"""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    if context.user_data.get("mode") != "admin_reply" or "support_id" not in context.user_data:
        return

    support_id = context.user_data["support_id"]
    if support_id not in SUPPORT_MESSAGES:
        await update.message.reply_text(
            "این پیام پشتیبانی دیگر معتبر نیست! 😊",
            parse_mode="Markdown"
        )
        return

    support_info = SUPPORT_MESSAGES[support_id]
    target_user_id = support_info["user_id"]
    user_message_id = support_info["user_message_id"]
    reply_text = update.message.text

    # ارسال پاسخ به کاربر
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"پاسخ ادمین:\n\n{reply_text}",
            reply_to_message_id=user_message_id,
            parse_mode="Markdown",
            protect_content=True
        )
        # اطلاع به ادمین در صورت موفقیت
        await update.message.reply_text(
            "پاسخ شما با موفقیت به کاربر ارسال شد! 😊",
            parse_mode="Markdown"
        )
    except TelegramError as e:
        logger.error(f"خطا در ارسال پاسخ به کاربر {target_user_id}: {e}")
        error_message = "خطا در ارسال پاسخ به کاربر! 😔 "
        if "chat not found" in str(e).lower():
            error_message += "کاربر چت با ربات را شروع نکرده است."
        elif "blocked by user" in str(e).lower():
            error_message += "ربات توسط کاربر بلاک شده است."
        else:
            error_message += "لطفاً دوباره امتحان کنید."
        await update.message.reply_text(
            error_message,
            parse_mode="Markdown"
        )
        return

    # حذف پیام پشتیبانی از دیکشنری
    del SUPPORT_MESSAGES[support_id]
    context.user_data.clear()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت پیام‌های متنی کاربر"""
    user_id = update.effective_user.id
    message_text = update.message.text
    chat_id = update.message.chat_id

    # نادیده گرفتن پیام‌های ادمین در حالت admin_reply
    if user_id == ADMIN_ID and context.user_data.get("mode") == "admin_reply":
        await handle_admin_reply(update, context)
        return

    # مدیریت دکمه بازگشت در همه حالت‌ها
    if message_text == "🔙 بازگشت":
        if user_id in AI_CHAT_USERS:
            AI_CHAT_USERS.remove(user_id)
        context.user_data.clear()
        await update.message.reply_text(
            "به *منوی اصلی* برگشتی! 😊 یکی از گزینه‌ها رو انتخاب کن:",
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
        return

    # بررسی عضویت در کانال
    is_member = await check_channel_membership(context.bot, user_id)
    if not is_member:
        welcome_message = (
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
            "لطفاً چند لحظه صبر کن! 😊 تعداد درخواست‌هات زیاد شده.",
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
        return

    # مدیریت پیام‌های پشتیبانی
    if context.user_data.get("mode") == "support":
        await handle_support_message(update, context)
        return

    # لاگ کردن حالت و پرامپ انتخاب‌شده
    mode = context.user_data.get("mode")
    logger.info(f"پردازش پیام در حالت: {mode}")

    # مدیریت دکمه‌های منوی اصلی
    if message_text == "🩺 مشاوره پزشکی":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "ai_chat"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            (
                "🤖 *دستیار پزشکی* فعال شد!\n\n"
                "سؤالت درباره بیماری یا موضوع پزشکی چیه؟\n"
                "مثلاً بپرس: *سرماخوردگی چی بخورم؟* یا تصویر بفرست! 😊"
            ),
            reply_markup=SUB_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "🧠 سلامت روان":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "mental_health"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            (
                "🧠 *سلامت روان لحظه‌ای* فعال شد!\n\n"
                "درباره حالت بگو یا تصویر بفرست!\n"
                "مثلاً: *استرس دارم، چیکار کنم؟* 😊"
            ),
            reply_markup=SUB_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "🦷 سلامت دهان و دندان":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "dental_health"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            (
                "🦷 *سلامت دهان و دندان* فعال شد!\n\n"
                "تصویر دندان بفرست یا علائم رو بگو!\n"
                "مثلاً: *دندونم درد می‌کنه، چیکار کنم؟* 😊"
            ),
            reply_markup=SUB_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "🧰 جعبه ابزار پزشکی":
        await update.message.reply_text(
            (
                "🧰 *جعبه ابزار پزشکی* باز شد!\n\n"
                "یکی از ابزارهای زیر رو انتخاب کن:"
            ),
            reply_markup=TOOLBOX_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "🧪 بررسی آزمایش":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "lab_test"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            (
                "🧪 *بررسی آزمایش* فعال شد!\n\n"
                "تصویر برگه آزمایش بفرست یا سؤالت رو بگو!\n"
                "مثلاً: *قند خون 150 یعنی چی؟* 😊"
            ),
            reply_markup=SUB_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "📈 تحلیل نوار قلب":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "ecg"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            (
                "📈 *تحلیل نوار قلب* فعال شد!\n\n"
                "تصویر نوار قلب بفرست یا سؤالت رو بگو!\n"
                "مثلاً: *ریتم نامنظم یعنی چی؟* 😊"
            ),
            reply_markup=SUB_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "🩻 تفسیر رادیولوژی":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "radiology"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            (
                "🩻 *تفسیر رادیولوژی* فعال شد!\n\n"
                "تصویر رادیولوژی (مثل X-ray) بفرست یا سؤالت رو بگو!\n"
                "مثلاً: *این سایه تو X-ray چیه؟* 😊"
            ),
            reply_markup=SUB_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "🧫 تشخیص علائم":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "symptom_diagnosis"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            (
                "🧫 *تشخیص علائم* فعال شد!\n\n"
                "علائمت رو بگو یا تصویر (مثل لک پوستی) بفرست!\n"
                "مثلاً: *دو روزه تب دارم و سرفه می‌کنم، چیه؟* 😊"
            ),
            reply_markup=SUB_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "💊 شناسایی داروها":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "drug_identification"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            (
                "💊 *شناسایی داروها* فعال شد!\n\n"
                "تصویر قرص یا جعبه بفرست، یا سؤالت رو بگو!\n"
                "مثلاً: *عوارض آسپرین چیه؟* 😊"
            ),
            reply_markup=SUB_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "🩹 مراقبت از زخم":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "wound_care"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            (
                "🩹 *مراقبت از زخم* فعال شد!\n\n"
                "تصویر زخم بفرست یا علائم رو بگو!\n"
                "مثلاً: *زخمم قرمز شده، چیکار کنم؟* 😊"
            ),
            reply_markup=SUB_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "🎚 شاخص توده بدنی":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "bmi"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            (
                "🎚 *شاخص توده بدنی* فعال شد!\n\n"
                "قد و وزن خودت رو بگو!\n"
                "مثلاً: *170 سانتی‌متر، 70 کیلوگرم* 😊"
            ),
            reply_markup=SUB_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "💉 وسایل پزشکی":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "medical_equipment"
        context.user_data["chat_history"] = []
        await update.message.reply_text(
            (
                "💉 *شناسایی وسایل پزشکی* فعال شد!\n\n"
                "تصویر وسیله پزشکی بفرست یا درباره‌اش سؤال کن!\n"
                "مثلاً: *این دستگاه چیه؟* 😊"
            ),
            reply_markup=SUB_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "⁉️ راهنما":
        guide_message = (
            "📘 *راهنمای کامل استفاده از دستیار پزشکی هوشمند*:\n\n"
            "*مشاوره پزشکی عمومی 🩺* :\n در مورد بیماری‌ها، علائم یا نگرانی‌های بدنی سؤال کن.\n"
            "*سلامت روان 🧠* :\n درباره اضطراب، افسردگی یا وضعیت روانی‌ات صحبت کن.\n"
            "*سلامت دهان و دندان 🦷* :\n تصویر دندان یا لثه‌ات رو برای بررسی تخصصی بفرست.\n\n"
            "*جعبه ابزار پیشرفته پزشکی 🧰*:\n"
            "*تشخیص علائم 🧫*:\n علائم جسمی یا تصویر مربوط رو بفرست تا بررسی بشه.\n"
            "*بررسی آزمایش‌ها 🧪*:\n برگه آزمایش یا سؤالت رو ارسال کن تا تفسیر کنم.\n"
            "*تحلیل نوار قلب 📈*:\n عکس نوار قلب رو بفرست تا دقیق تفسیر بشه.\n"
            "*تفسیر تصویربرداری پزشکی 🩻*:\n عکس X-ray یا سی‌تی‌اسکن رو بفرست.\n"
            "شناسایی داروها 💊*:\n تصویر قرص یا بسته دارو رو بفرست تا بررسی کنم.\n"
            "مراقبت از زخم‌ها 🩹*:\n عکس زخم یا سوختگی رو بفرست برای توصیه درمانی.\n"
            "محاسبه BMI 🎚*:\n قد و وزنت رو بگو تا شاخص توده بدنی محاسبه بشه.\n"
            "شناسایی وسایل پزشکی 💉*:\n عکس وسیله پزشکی رو بفرست تا توضیح بدم چی هست.\n\n"
            "*پشتیبانی عمومی 💬*:\n هر سؤال یا فایل، عکس، ویدیو داری، همینجا بفرست.\n\n"
            "🔔 *یادآوری مهم*: این دستیار جایگزین پزشک نیست. برای تشخیص یا درمان قطعی، با پزشک مشورت کن.\n"
            "سؤالی داری؟ یکی از گزینه‌ها رو انتخاب کن و شروع کنیم! 😊"
        )
        await update.message.reply_text(
            guide_message,
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif message_text == "💬 پشتیبانی":
        AI_CHAT_USERS.add(user_id)
        context.user_data.clear()
        context.user_data["mode"] = "support"
        await update.message.reply_text(
            (
                "💬 *پشتیبانی دستیار پزشکی*\n\n"
                "سؤالت رو بنویس یا عکس، ویدیو و فایل بفرست! 😊\n"
                "ما به‌زودی جوابت رو می‌دیم."
            ),
            reply_markup=SUPPORT_KEYBOARD,
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
        logger.info(f"پرامپ انتخاب‌شده برای حالت {context.user_data['mode']}: {system_message[:100]}...")

        # ایجاد پیام‌ها برای g4f
        messages = [
            {"role": "system", "content": system_message}
        ] + chat_history

        # ارسال پیام موقت
        temp_emoji_message = await update.message.reply_text("🩺", parse_mode="Markdown")
        temp_text_message = await update.message.reply_text("**درحال پاسخ دادن صبور باشید!**", parse_mode="Markdown")

        # استفاده از g4f
        client = Client()
        for attempt in range(3):  # افزایش تعداد تلاش‌ها
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",  # تغییر به gpt-4o-mini
                    messages=messages,
                    max_tokens=300,
                    seed=42
                )
                # حذف پیام‌های موقت
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=temp_emoji_message.message_id)
                    await context.bot.delete_message(chat_id=chat_id, message_id=temp_text_message.message_id)
                except TelegramError as e:
                    logger.error(f"خطا در حذف پیام‌های موقت: {e}")

                ai_response = response.choices[0].message.content.strip()
                chat_history.append({"role": "assistant", "content": ai_response})
                context.user_data["chat_history"] = chat_history
                await update.message.reply_text(
                    ai_response,
                    reply_markup=SUB_MENU_KEYBOARD,
                    parse_mode="Markdown"
                )
                break
            except Exception as e:
                logger.error(f"خطا در اتصال به g4f (تلاش {attempt + 1}): {str(e)}")
                if attempt == 2:
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=temp_emoji_message.message_id)
                        await context.bot.delete_message(chat_id=chat_id, message_id=temp_text_message.message_id)
                    except TelegramError as e:
                        logger.error(f"خطا در حذف پیام‌های موقت: {e}")
                    await update.message.reply_text(
                        "اوه، *ابزار تشخیص‌مون* نیاز به بررسی داره! 💉 لطفاً دوباره سؤالت رو بفرست. 😊",
                        reply_markup=SUB_MENU_KEYBOARD,
                        parse_mode="Markdown"
                    )
    else:
        await update.message.reply_text(
            "لطفاً یکی از گزینه‌های *منو* رو انتخاب کن! 😊",
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="Markdown"
        )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت عکس‌های ارسالی"""
    user_id = update.effective_user.id
    mode = context.user_data.get("mode")

    logger.info(f"دریافت عکس از کاربر {user_id} در حالت: {mode}")

    if mode == "support":
        await handle_support_photo(update, context)
    elif user_id in AI_CHAT_USERS and mode in SYSTEM_MESSAGES.keys():
        # بررسی محدودیت نرخ درخواست‌ها
        if not await check_rate_limit(context, user_id):
            await update.message.reply_text(
                "لطفاً چند لحظه صبر کن! 😊 تعداد درخواست‌هات زیاد شده.",
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
        temp_emoji_message = await update.message.reply_text("🔬", parse_mode="Markdown")
        temp_text_message = await update.message.reply_text("**در حال بررسی عکس شما صبور باشید!**", parse_mode="Markdown")

        photo = update.message.photo[-1]
        try:
            file = await context.bot.get_file(photo.file_id)
            file_url = file.file_path
            logger.info(f"URL تصویر دریافت‌شده: {file_url}")
        except TelegramError as e:
            logger.error(f"خطا در دریافت فایل تصویر: {e}")
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=temp_emoji_message.message_id)
                await context.bot.delete_message(chat_id=chat_id, message_id=temp_text_message.message_id)
            except TelegramError as e:
                logger.error(f"خطا در حذف پیام‌های موقت: {e}")
            await update.message.reply_text(
                "اوپس، مشکلی در دریافت تصویر پیش اومد! 😔 لطفاً دوباره تصویر رو بفرست.",
                reply_markup=SUB_MENU_KEYBOARD,
                parse_mode="Markdown"
            )
            return

        caption = update.message.caption if update.message.caption else "این تصویر چیه؟ به‌صورت خلاصه و دقیق تحلیل کن! 🩺"

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
        system_message = SYSTEM_MESSAGES.get(mode, SYSTEM_MESSAGES["ai_chat"])
        logger.info(f"پرامپ انتخاب‌شده برای حالت {mode}: {system_message[:100]}...")

        # ایجاد پیام‌ها برای g4f
        messages = [
            {"role": "system", "content": system_message}
        ] + chat_history

        # استفاده از g4f
        client = Client()
        for attempt in range(3):  # افزایش تعداد تلاش‌ها
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",  # تغییر به g4f-mini
                    messages=messages,
                    max_tokens=300,
                    seed=42
                )
                # حذف پیام‌های موقت
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=temp_emoji_message.message_id)
                    await context.bot.delete_message(chat_id=chat_id, message_id=temp_text_message.message_id)
                except TelegramError as e:
                    logger.error(f"خطا در حذف پیام‌های موقت: {e}")

                ai_response = response.choices[0].message.content.strip()
                chat_history.append({"role": "assistant", "content": ai_response})
                context.user_data["chat_history"] = chat_history
                await update.message.reply_text(
                    ai_response,
                    reply_markup=SUB_MENU_KEYBOARD,
                    parse_mode="Markdown"
                )
                logger.info(f"پاسخ موفق برای تصویر در حالت {mode}")
                break
            except Exception as e:
                logger.error(f"خطا در تحلیل تصویر با g4f (تلاش {attempt + 1}): {str(e)}")
                if attempt == 2:
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=temp_emoji_message.message_id)
                        await context.bot.delete_message(chat_id=chat_id, message_id=temp_text_message.message_id)
                    except TelegramError as e:
                        logger.error(f"خطا در حذف پیام‌های موقت: {e}")
                    await update.message.reply_text(
                        "اوپس، *اسکنر پزشکی‌مون* یه لحظه خاموش شد! 🩺 لطفاً دوباره عکس رو بفرست یا بعداً امتحان کن. 😊",
                        reply_markup=SUB_MENU_KEYBOARD,
                        parse_mode="Markdown"
                    )
    else:
        await update.message.reply_text(
            "لطفاً برای تحلیل تصویر، گزینه مرتبط رو از *منو* انتخاب کن! 😊",
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="Markdown"
        )

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت ویدیوهای ارسالی"""
    user_id = update.effective_user.id
    mode = context.user_data.get("mode")

    if mode == "support":
        await handle_support_video(update, context)
    else:
        await update.message.reply_text(
            "ارسال ویدیو فقط در بخش *پشتیبانی 💬* ممکنه! 😊 لطفاً گزینه پشتیبانی رو انتخاب کن.",
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="Markdown"
        )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت فایل‌های ارسالی"""
    user_id = update.effective_user.id
    mode = context.user_data.get("mode")

    if mode == "support":
        await handle_support_document(update, context)
    else:
        await update.message.reply_text(
            "ارسال فایل فقط در بخش *پشتیبانی 💬* ممکنه! 😊 لطفاً گزینه پشتیبانی رو انتخاب کن.",
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="Markdown"
        )

async def handle_forwarded_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """جلوگیری از پذیرش پیام‌های فورواردشده"""
    user_id = update.effective_user.id
    mode = context.user_data.get("mode")

    if mode == "support":
        await update.message.reply_text(
            "ارسال پیام فورواردشده مجاز نیست! 😊 لطفاً پیام، عکس، ویدیو یا فایل خودت رو بفرست.",
            reply_markup=SUPPORT_KEYBOARD,
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "لطفاً یکی از گزینه‌های *منو* رو انتخاب کن! 😊",
            reply_markup=MAIN_MENU_KEYBOARD,
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
            error_message,
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="Markdown"
        )
    elif update and hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.message.reply_text(
            error_message,
            reply_markup=MAIN_MENU_KEYBOARD,
            parse_mode="Markdown"
        )

async def main():
    """راه‌اندازی ربات با Polling"""
    global application
    try:
        # ساخت شیء Application
        application = Application.builder().token(TOKEN).build()

        # ثبت هندلرها
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(handle_callback_query))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(MessageHandler(filters.VIDEO, handle_video))
        application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
        application.add_handler(MessageHandler(filters.FORWARDED, handle_forwarded_message))
        application.add_handler(MessageHandler(filters.REPLY & filters.User(ADMIN_ID), handle_admin_reply))
        application.add_error_handler(error_handler)

        # مقداردهی اولیه Application
        logger.info("مقداردهی اولیه Application...")
        await application.initialize()

        # راه‌اندازی Application
        logger.info("راه‌اندازی Application...")
        await application.start()

        # شروع Polling
        logger.info("شروع Polling...")
        await application.updater.start_polling(
            poll_interval=1.0,
            timeout=10,
            drop_pending_updates=True
        )

        # نگه‌داشتن برنامه در حال اجرا
        logger.info("ربات در حالت Polling اجرا شد.")
        while True:
            await asyncio.sleep(3600)  # خواب برای جلوگیری از اتمام منابع

    except Exception as e:
        logger.error(f"خطا در راه‌اندازی ربات: {e}")
        raise
    finally:
        # توقف Application هنگام خاموش شدن
        logger.info("توقف Application...")
        await application.stop()
        await application.updater.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"خطا در اجرای برنامه: {e}")
