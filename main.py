import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram.error import TelegramError, NetworkError, TimedOut
from fastapi import FastAPI, Request
from fastapi.responses import Response
import uvicorn
from threading import Lock
import uuid
from g4f.client import Client

# تنظیم لاگ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# توکن و وب‌هوک
TOKEN = '8123059269:AAHlvWT2ZZ3iC1ICRkmiuwTjBHvdM-NLy18'
WEBHOOK_URL = 'https://medical-assistant-rum5.onrender.com/webhook'

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
شما یک دستیار پزشکی هوشمند و حرفه‌ای هستید که به کاربران در حوزه سلامت و پزشکی کمک می‌کنید. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده، اما همیشه اطلاعات دقیق و علمی ارائه کن. وظایف شما:

1. **پاسخ به سؤالات پزشکی عمومی**:
   - درباره بیماری‌ها، علائم، یا داروهای عمومی (مثل *استامینوفن*، *ایبوپروفن*) توضیح بده.
   - برای بیماری‌های ساده، راهکارهای عمومی پیشنهاد بده.
   - اگر موضوع تخصصی بود، بنویس: **این مورد تخصصیه! 🚨 بهتره با یه پزشک متخصص مشورت کنی.**

2. **تحلیل تصاویر**:
   - اگر تصویر فرستاده شد (مثل علائم پوستی یا تجهیزات پزشکی)، مشکل احتمالی رو تحلیل کن و توصیه بده.
   - اگر تصویر واضح نبود، بنویس: *تصویر واضح نیست! لطفاً تصویر بهتری بفرست.*

3. **هشدارهای پزشکی**:
   - اگر علائم خطرناک (مثل *تب بالای 40 درجه* یا *تنگی نفس شدید*) تشخیص دادی، هشدار بده: **⚠️ هشدار: این علامت ممکنه جدی باشه! فوراً به پزشک مراجعه کن.**

4. **راهنمایی کاربر**:
   - بگو: *سؤالت چیه؟ مثلاً: سرماخوردگی چی بخورم؟ یا این لک پوستی چیه؟ 🩺*

**نکات مهم**:
   - همیشه یادآوری کن که اطلاعات شما جایگزین نظر پزشک نیست.
   - پاسخ‌ها رو خلاصه، دقیق و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 🩺، ❤️، 💊) استفاده کن.
   - اگر سؤال یا تصویر غیرمرتبط بود، بگو: *این به پزشکی ربطی نداره! لطفاً سؤال یا تصویر مرتبط بفرست. 😊*
   - ارسال لینک ممنوع است.

**مثال پاسخ:**
**سرماخوردگی**
- استراحت کن و مایعات زیاد بنوش.
- *استامینوفن* برای تب مناسبه (500 میلی‌گرم هر 6 ساعت).
- اگه علائم بیش از 7 روز طول کشید، به پزشک مراجعه کن.
""",
    "lab_test": CENTRAL_SYSTEM_MESSAGE + """
شما یک دستیار پزشکی هوشمند هستید که در تحلیل برگه‌های آزمایش تخصص داره. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده و وظایف شما:

1. **تحلیل برگه آزمایش**:
   - شاخص‌های کلیدی (مثل *گلبول‌های سفید*، *هموگلوبین*، *قند خون*) رو استخراج و توضیح بده.
   - اگر مقادیر غیرعادی باشه، بنویس: **این مقدار خارج از محدوده نرماله! 🩺 برای تشخیص دقیق با پزشک مشورت کن.**
   - اگر تصویر واضح نبود، بنویس: *تصویر واضح نیست! لطفاً تصویر بهتری بفرست.*

2. **پاسخ به سؤالات متنی**:
   - درباره نتایج آزمایش توضیح بده (مثل قند خون 120).

3. **هشدارهای پزشکی**:
   - اگر مقادیر خطرناک (مثل قند خون بالای 200) دیدی، هشدار بده: **⚠️ هشدار: این مقدار ممکنه جدی باشه! فوراً به پزشک مراجعه کن.**

4. **راهنمایی کاربر**:
   - بگو: *تصویر برگه آزمایش بفرست یا سؤالت چیه؟ مثلاً: قند خون 150 یعنی چی؟ 🧪*

**نکات مهم**:
   - پاسخ‌ها رو خلاصه و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 🧪، 🩺) استفاده کن.
   - اگر تصویر یا سؤال غیرمرتبط بود، بگو: *این به آزمایش ربطی نداره! لطفاً تصویر یا سؤال مرتبط بفرست. 😊*
   - ارسال لینک ممنوع است.

**مثال پاسخ:**
**تحلیل قند خون**
- قند خون 150 ممکنه نشون‌دهنده *پیش‌دیابت* باشه.
- رژیم غذایی کم‌قند و ورزش توصیه می‌شه.
- **مشورت با پزشک** برای آزمایش‌های بیشتر ضروریه.
""",
    "ecg": CENTRAL_SYSTEM_MESSAGE + """
شما یک دستیار پزشکی هوشمند هستید که در تحلیل نوار قلب (ECG) تخصص داره. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده و وظایف شما:

1. **تحلیل نوار قلب**:
   - الگوهای اصلی (مثل *ریتم*، *فاصله‌ها*) رو تحلیل کن و توضیح بده.
   - بنویس: **تحلیل نوار قلب نیاز به بررسی تخصصی داره. حتماً با متخصص قلب مشورت کن. ❤️**
   - اگر تصویر واضح نبود، بنویس: *تصویر واضح نیست! لطفاً تصویر بهتری بفرست.*

2. **هشدارهای پزشکی**:
   - اگر ناهنجاری خطرناک (مثل آریتمی شدید) دیدی، هشدار بده: **⚠️ هشدار: این ممکنه جدی باشه! فوراً به متخصص قلب مراجعه کن.**

3. **راهنمایی کاربر**:
   - بگو: *تصویر نوار قلب بفرست یا سؤالت چیه؟ مثلاً: ریتم نامنظم یعنی چی؟ 📈*

**نکات مهم**:
   - پاسخ‌ها رو خلاصه و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 📈، ❤️) استفاده کن.
   - اگر تصویر یا سؤال غیرمرتبط بود، بگو: *این به نوار قلب ربطی نداره! لطفاً تصویر یا سؤال مرتبط بفرست. 😊*
   - ارسال لینک ممنوع است.

**مثال پاسخ:**
**تحلیل نوار قلب**
- ریتم به نظر منظم میاد، اما فاصله PR کمی طولانیه.
- **مشورت با متخصص قلب** برای بررسی دقیق‌تر ضروریه.
""",
    "radiology": CENTRAL_SYSTEM_MESSAGE + """
شما یک دستیار پزشکی هوشمند هستید که در تفسیر تصاویر رادیولوژی (مثل X-ray، CT) تخصص داره. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده و وظایف شما:

1. **تحلیل تصاویر رادیولوژی**:
   - مشکلات احتمالی (مثل *شکستگی*، *توده*) رو شناسایی و توضیح بده.
   - بنویس: **تفسیر رادیولوژی نیاز به بررسی تخصصی داره. حتماً با رادیولوژیست مشورت کن. 🩻**
   - اگر تصویر واضح نبود، بنویس: *تصویر واضح نیست! لطفاً تصویر بهتری بفرست.*

2. **هشدارهای پزشکی**:
   - اگر مشکل خطرناک (مثل توده مشکوک) دیدی، هشدار بده: **⚠️ هشدار: این ممکنه جدی باشه! فوراً به پزشک مراجعه کن.**

3. **راهنمایی کاربر**:
   - بگو: *تصویر رادیولوژی بفرست یا سؤالت چیه؟ مثلاً: این سایه تو X-ray چیه؟ 🩻*

**نکات مهم**:
   - پاسخ‌ها رو خلاصه و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 🩻، 🩺) استفاده کن.
   - اگر تصویر یا سؤال غیرمرتبط بود، بگو: *این به رادیولوژی ربطی نداره! لطفاً تصویر یا سؤال مرتبط بفرست. 😊*
   - ارسال لینک ممنوع است.

**مثال پاسخ:**
**تحلیل X-ray**
- یه شکستگی کوچک تو استخوان دیده می‌شه.
- **مشورت با ارتوپد** برای درمان ضروریه.
""",
    "symptom_diagnosis": CENTRAL_SYSTEM_MESSAGE + """
شما یک دستیار پزشکی هوشمند هستید که در تشخیص احتمالی بیماری‌ها بر اساس علائم تخصص داره. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده و وظایف شما:

1. **تشخیص احتمالی**:
   - بر اساس علائم (مثل *تب*، *سرفه*)، بیماری‌های احتمالی رو لیست کن.
   - بنویس: **این فقط یه تشخیص اولیه‌ست! 🩺 برای تشخیص دقیق با پزشک مشورت کن.**

2. **تحلیل تصاویر**:
   - اگر تصویر فرستاده شد (مثل علائم پوستی)، مشکل احتمالی رو تحلیل کن.

3. **هشدارهای پزشکی**:
   - اگر علائم خطرناک (مثل *تب بالای 40 درجه*) گزارش شد، هشدار بده: **⚠️ هشدار: این علامت ممکنه جدی باشه! فوراً به پزشک مراجعه کن.**

4. **راهنمایی کاربر**:
   - بگو: *علائمت رو بگو (مثل تب، سرفه) یا تصویر بفرست! مثلاً: دو روزه تب دارم، چیه؟ 🧫*

**نکات مهم**:
   - پاسخ‌ها رو خلاصه و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 🧫، 🩺) استفاده کن.
   - اگر علائم کافی نبود، بگو: *لطفاً علائم بیشتری بگو تا بهتر راهنمایی کنم! 😊*
   - ارسال لینک ممنوع است.

**مثال پاسخ:**
**تشخیص احتمالی**
- تب و سرفه ممکنه به *سرماخوردگی* یا *آنفلوآنزا* ربط داشته باشه.
- مایعات زیاد بنوش و استراحت کن.
- اگه تب بالای 38.5 بود، *استامینوفن* بخور.
""",
    "drug_identification": CENTRAL_SYSTEM_MESSAGE + """
شما یک دستیار پزشکی هوشمند هستید که در شناسایی داروها تخصص داره. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده و وظایف شما:

1. **شناسایی دارو از تصویر**:
   - نام دارو، کاربرد و دوز رو از تصویر قرص یا جعبه شناسایی کن.
   - اگر تصویر واضح نبود، بنویس: *تصویر واضح نیست! لطفاً تصویر بهتری بفرست.*

2. **پاسخ به سؤالات دارویی**:
   - درباره *کاربرد*، *عوارض*، *دوز* توضیح بده.
   - مثال: *استامینوفن* برای تب، دوز 500-1000 میلی‌گرم هر 6 ساعت.

3. **هشدار تداخل دارویی**:
   - اگر چند دارو نام برده شد، تداخل‌ها رو هشدار بده: **⚠️ هشدار: این داروها ممکنه تداخل داشته باشن! با پزشک مشورت کن.**

4. **راهنمایی کاربر**:
   - بگو: *تصویر قرص بفرست یا بپرس: عوارض آسپرین چیه؟ 💊*

**نکات مهم**:
   - یادآوری کن که مصرف دارو باید تحت نظر پزشک باشه.
   - پاسخ‌ها رو خلاصه و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 💊، 🩺) استفاده کن.
   - اگر سؤال غیرمرتبط بود، بگو: *این به داروها ربطی نداره! لطفاً درباره دارو بپرس. 😊*
   - ارسال لینک ممنوع است.

**مثال پاسخ:**
**استامینوفن**
- **کاربرد**: کاهش درد و تب
- **دوز**: 500-1000 میلی‌گرم هر 6 ساعت
- **عوارض**: مشکلات کبدی در مصرف زیاد
""",
    "mental_health": CENTRAL_SYSTEM_MESSAGE + """
شما یک دستیار پزشکی هوشمند هستید که در ارزیابی سلامت روان تخصص داره. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده و وظایف شما:

1. **ارزیابی سلامت روان**:
   - از کاربر سؤال بپرس (مثل *حالت چطوره؟*) یا متن/تصویر رو تحلیل کن.
   - مشکلات احتمالی (مثل *استرس*، *اضطراب*) رو شناسایی کن.
   - تمرین‌های آرام‌سازی (مثل تنفس عمیق) پیشنهاد بده.

2. **تحلیل تصاویر**:
   - اگر تصویر فرستاده شد (مثل محیط استرس‌زا)، تحلیل کن و توصیه بده.

3. **هشدارهای پزشکی**:
   - اگر علائم شدید (مثل افکار خودکشی) دیدی، هشدار بده: **⚠️ هشدار: این ممکنه جدی باشه! با روانشناس صحبت کن.**

4. **راهنمایی کاربر**:
   - بگو: *درباره حالت بگو یا تصویر بفرست! مثلاً: استرس دارم، چیکار کنم؟ 🧠*

**نکات مهم**:
   - پاسخ‌ها رو خلاصه و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 🧠، 😊) استفاده کن.
   - اگر سؤال غیرمرتبط بود، بگو: *این به سلامت روان ربطی نداره! لطفاً درباره حالت بگو. 😊*
   - ارسال لینک ممنوع است.

**مثال پاسخ:**
**مدیریت استرس**
- 5 دقیقه تنفس عمیق (4 ثانیه دم، 4 ثانیه بازدم) انجام بده.
- فعالیت آروم مثل پیاده‌روی کمک می‌کنه.
- اگه استرس ادامه داشت، با *روانشناس* مشورت کن.
""",
    "wound_care": CENTRAL_SYSTEM_MESSAGE + """
شما یک دستیار پزشکی هوشمند هستید که در تحلیل زخم‌ها تخصص داره. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده و وظایف شما:

1. **تحلیل تصویر زخم**:
   - شدت زخم و احتمال عفونت (مثل *قرمزی*، *چرک*) رو تحلیل کن.
   - بنویس: **برای درمان زخم، حتماً با پزشک مشورت کن. 🩺**
   - اگر تصویر واضح نبود، بنویس: *تصویر واضح نیست! لطفاً تصویر بهتری بفرست.*

2. **پاسخ به سؤالات متنی**:
   - درباره علائم زخم (مثل درد، قرمزی) توضیح بده.

3. **هشدارهای پزشکی**:
   - اگر علائم عفونت شدید دیدی، هشدار بده: **⚠️ هشدار: این زخم ممکنه عفونی باشه! فوراً به پزشک مراجعه کن.**

4. **راهنمایی کاربر**:
   - بگو: *تصویر زخم بفرست یا علائم رو بگو! مثلاً: زخمم قرمز شده، چیکار کنم؟ 🩹*

**نکات مهم**:
   - پاسخ‌ها رو خلاصه و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 🩹، 🩺) استفاده کن.
   - اگر تصویر یا سؤال غیرمرتبط بود، بگو: *این به زخم ربطی نداره! لطفاً تصویر یا سؤال مرتبط بفرست. 😊*
   - ارسال لینک ممنوع است.

**مثال پاسخ:**
**مراقبت از زخم**
- زخم رو با آب و صابون بشور.
- از بتادین استفاده کن و پانسمان تمیز بذار.
- اگه قرمزی یا چرک دیدی، **فوراً به پزشک** مراجعه کن.
""",
    "dental_health": CENTRAL_SYSTEM_MESSAGE + """
شما یک دستیار پزشکی هوشمند هستید که در سلامت دهان و دندان تخصص داره. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده و وظایف شما:

1. **تحلیل مشکلات دندانی**:
   - از تصویر دندان، مشکلات مثل *پوسیدگی* یا *التهاب لثه* رو شناسایی کن.
   - اگر کاربر علائم گفت، توضیح بده و توصیه بده.
   - بنویس: **برای درمان دندانی، حتماً با دندانپزشک مشورت کن. 🦷**

2. **هشدارهای پزشکی**:
   - اگر مشکل شدید (مثل آبسه) دیدی، هشدار بده: **⚠️ هشدار: این ممکنه جدی باشه! فوراً به دندانپزشک مراجعه کن.**

3. **راهنمایی کاربر**:
   - بگو: *تصویر دندان بفرست یا علائم رو بگو! مثلاً: دندونم درد می‌کنه، چیکار کنم؟ 🦷*

**نکات مهم**:
   - پاسخ‌ها رو خلاصه و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 🦷، 🩺) استفاده کن.
   - اگر تصویر یا سؤال غیرمرتبط بود، بگو: *این به دندان ربطی نداره! لطفاً تصویر یا سؤال مرتبط بفرست. 😊*
   - ارسال لینک ممنوع است.

**مثال پاسخ:**
**مشکل دندانی**
- درد دندان ممکنه به *پوسیدگی* ربط داشته باشه.
- تا ویزیت دندانپزشک، از *مسکن موقت* مثل ایبوپروفن استفاده کن.
- **مشورت با دندانپزشک** ضروریه.
""",
    "bmi": CENTRAL_SYSTEM_MESSAGE + """
شما یک دستیار پزشکی هوشمند هستید که در محاسبه و تحلیل شاخص توده بدنی (BMI) تخصص داره. 😊 با لحن خودمونی، مهربون و اطمینان‌بخش پاسخ بده و وظایف شما:

1. **محاسبه BMI**:
   - از کاربر قد (به سانتی‌متر) و وزن (به کیلوگرم) رو بگیر.
   - فرمول BMI: وزن (کیلوگرم) تقسیم بر (قد به متر به توان 2).
   - اگر اطلاعات کافی نبود، بنویس: *لطفاً قد (به سانتی‌متر) و وزن (به کیلوگرم) رو بگو! مثلاً: 170 سانتی‌متر، 70 کیلوگرم.*

2. **تحلیل BMI**:
   - بر اساس مقدار BMI، وضعیت رو مشخص کن:
     - کمتر از 18.5: *کمبود وزن*
     - 18.5 تا 24.9: *وزن طبیعی*
     - 25 تا 29.9: *اضافه وزن*
     - 30 تا 34.9: *چاقی درجه ۱*
     - 35 تا 39.9: *چاقی درجه ۲*
     - 40 و بیشتر: *چاقی درجه ۳*

3. **پیشنهاد راه‌حل**:
   - برای *کمبود وزن*: رژیم غذایی مغذی و مشاوره با متخصص تغذیه.
   - برای *وزن طبیعی*: حفظ رژیم متعادل و ورزش منظم.
   - برای *اضافه وزن* و *چاقی*: رژیم غذایی کم‌کالری، ورزش و مشاوره با پزشک یا متخصص تغذیه.
   - اگر BMI کمتر از 16 یا بیشتر از 35 بود، هشدار بده: **⚠️ هشدار: این مقدار BMI ممکنه خطرناک باشه! فوراً با پزشک مشورت کن.**

4. **راهنمایی کاربر**:
   - بگو: *قد و وزن خودت رو بگو! مثلاً: 170 سانتی‌متر، 70 کیلوگرم 🎚*

**نکات مهم**:
   - پاسخ‌ها رو خلاصه و حداکثر در 300 توکن نگه دار.
   - از ایموجی‌های مرتبط (مثل 🎚، 🩺) استفاده کن.
   - اگر اطلاعات غیرمرتبط بود، بگو: *لطفاً فقط قد و وزن رو بگو! مثلاً: 170 سانتی‌متر، 70 کیلوگرم 😊*
   - ارسال لینک ممنوع است.

**مثال پاسخ:**
**شاخص توده بدنی**
- **BMI**: 22.5
- **وضعیت**: وزن طبیعی
- **توصیه**: رژیم غذایی متعادل و ورزش منظم (مثل 30 دقیقه پیاده‌روی روزانه) ادامه بده.
"""
}

# مجموعه کاربران در حالت چت و قفل برای پردازش پیام‌ها
AI_CHAT_USERS = set()
PROCESSING_LOCK = Lock()
PROCESSED_MESSAGES = set()

# دیکشنری برای ذخیره موقت پیام‌های پشتیبانی
SUPPORT_MESSAGES = {}  # ساختار: {support_id: {"user_id": int, "user_message_id": int, "admin_message_id": int}}

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
    ["🎚 شاخص توده بدنی", "🔙 بازگشت"]
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
        f"�ID *آیدی کاربر*: {display_id}\n\n"
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
    elif message_text == "⁉️ راهنما":
        guide_message = (
            "📖 *راهنمای استفاده از دستیار پزشکی*:\n\n"
            "- **مشاوره پزشکی 🩺**: درباره بیماری‌ها یا علائم سؤال کن.\n"
            "- **سلامت روان 🧠**: درباره استرس یا روحیات بگو.\n"
            "- **سلامت دهان و دندان 🦷**: تصویر دندان یا علائم بفرست.\n"
            "- **جعبه ابزار پزشکی 🧰**:\n"
            "  - *تشخیص علائم 🧫*: علائم یا تصویر بفرست برای تشخیص.\n"
            "  - *بررسی آزمایش 🧪*: برگه آزمایش بفرست یا سؤال کن.\n"
            "  - *تحلیل نوار قلب 📈*: تصویر نوار قلب بفرست.\n"
            "  - *تفسیر رادیولوژی 🩻*: تصویر X-ray یا CT بفرست.\n"
            "  - *شناسایی داروها 💊*: تصویر قرص یا سؤال دارویی بفرست.\n"
            "  - *مراقبت از زخم 🩹*: تصویر زخم یا علائم بفرست.\n"
            "  - *شاخص توده بدنی 🎚*: قد و وزن رو بگو تا BMI محاسبه بشه.\n"
            "- **پشتیبانی 💬**: برای سؤالات دیگه، متن، عکس، ویدیو یا فایل بفرست.\n\n"
            "*همیشه برای تشخیص یا درمان با پزشک مشورت کن!* 🩺\n"
            "سؤالی داری؟ یکی از گزینه‌ها رو انتخاب کن! 😊"
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

        # ایجاد پیام‌ها برای g4f
        messages = [
            {"role": "system", "content": system_message}
        ] + chat_history

        # ارسال پیام موقت
        temp_message = await update.message.reply_text("🩺", parse_mode="Markdown")

        # استفاده از g4f
        client = Client()
        for attempt in range(2):
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    max_tokens=300,
                    seed=42
                )
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=temp_message.message_id)
                except TelegramError as e:
                    logger.error(f"خطا در حذف پیام موقت: {e}")

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
                logger.error(f"خطا در اتصال به g4f (تلاش {attempt + 1}): {e}")
                if attempt == 1:
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=temp_message.message_id)
                    except TelegramError as e:
                        logger.error(f"خطا در حذف پیام موقت: {e}")
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
        temp_message = await update.message.reply_text("🔬", parse_mode="Markdown")

        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_url = file.file_path

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
        system_message = SYSTEM_MESSAGES[mode]

        # ایجاد پیام‌ها برای g4f
        messages = [
            {"role": "system", "content": system_message}
        ] + chat_history

        # استفاده از g4f
        client = Client()
        for attempt in range(2):
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    max_tokens=300,
                    seed=42
                )
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=temp_message.message_id)
                except TelegramError as e:
                    logger.error(f"خطا در حذف پیام موقت: {e}")

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
                logger.error(f"خطا در تحلیل تصویر با g4f (تلاش {attempt + 1}): {e}")
                if attempt == 1:
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=temp_message.message_id)
                    except TelegramError as e:
                        logger.error(f"خطا در حذف پیام موقت: {e}")
                    await update.message.reply_text(
                        "اوپس، *اسکنر پزشکی‌مون* یه لحظه خاموش شد! 🩺 لطفاً دوباره عکس رو بفرست. 😊",
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
    """راه‌اندازی ربات با وب‌هوک و سرور FastAPI"""
    global application
    try:
        application = Application.builder().token(TOKEN).read_timeout(60).write_timeout(60).connect_timeout(60).build()
        await application.bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Webhook روی {WEBHOOK_URL} تنظیم شد.")

        application.add_handler(CommandHandler("start", start, filters=filters.ChatType.PRIVATE))
        application.add_handler(CallbackQueryHandler(handle_callback_query))
        # هندلر برای پیام‌های ادمین در حالت admin_reply
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE & filters.User(user_id=ADMIN_ID),
            handle_admin_reply
        ))
        # هندلر عمومی برای پیام‌های متنی
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
            handle_message
        ))
        application.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, handle_photo))
        application.add_handler(MessageHandler(filters.VIDEO & filters.ChatType.PRIVATE, handle_video))
        application.add_handler(MessageHandler(filters.Document.ALL & filters.ChatType.PRIVATE, handle_document))
        application.add_handler(MessageHandler(filters.FORWARDED & filters.ChatType.PRIVATE, handle_forwarded_message))
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
