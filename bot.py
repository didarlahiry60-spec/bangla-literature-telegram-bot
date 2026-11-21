import asyncio
import datetime
import logging
import sys
from typing import Optional
import pytz

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.error import BadRequest, Forbidden, RetryAfter, TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config import (
    TELEGRAM_BOT_TOKEN,
    TIMEZONE,
    SCHEDULE_SLOTS,
    CATEGORIES,
)
import database
import curator

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("BanglaLekhaBot")

AUTHORS_DIRECTORY = {
    "tagore": "রবীন্দ্রনাথ ঠাকুর",
    "nazrul": "কাজী নজরুল ইসলাম",
    "humayun": "হুমায়ূন আহমেদ",
    "sunil": "সুনীল গঙ্গোপাধ্যায়",
    "shirshendu": "শীর্ষেন্দু মুখোপাধ্যায়",
    "jibanananda": "জীবনানন্দ দাশ",
    "helal": "হেলাল হাফিজ",
    "rudra": "রুদ্র মুহম্মদ শহিদুল্লাহ",
    "joy": "জয় গোস্বামী",
    "sadat": "সাদাত হোসাইন",
    "trending": "সমকালীন ও ট্রেন্ডিং"
}

def get_dhaka_tz():
    try:
        return pytz.timezone(TIMEZONE)
    except Exception:
        return pytz.timezone("Asia/Dhaka")

def ensure_user_registered(user, chat):
    """Ensures user is stored in subscribers database on any interaction."""
    if user and chat:
        uname = user.username if isinstance(getattr(user, "username", None), str) else None
        fname = user.first_name if isinstance(getattr(user, "first_name", None), str) else None
        database.add_or_update_subscriber(
            user_id=user.id,
            chat_id=chat.id,
            username=uname,
            first_name=fname
        )

async def send_snippet_to_chat(bot_instance, chat_id: int, text: str, reply_markup=None):
    """Safely sends snippet text to a chat, splitting into chunks if exceeding 4000 characters."""
    chunks = curator.split_text_chunks(text, max_chars=4000)
    for i, chunk in enumerate(chunks):
        is_last = (i == len(chunks) - 1)
        markup = reply_markup if is_last else None
        await bot_instance.send_message(
            chat_id=chat_id,
            text=chunk,
            reply_markup=markup
        )
        if not is_last:
            await asyncio.sleep(0.05)

async def reply_snippet(message, text: str, reply_markup=None):
    """Safely replies snippet text, splitting into chunks if exceeding 4000 characters."""
    chunks = curator.split_text_chunks(text, max_chars=4000)
    for i, chunk in enumerate(chunks):
        is_last = (i == len(chunks) - 1)
        markup = reply_markup if is_last else None
        await message.reply_text(
            text=chunk,
            reply_markup=markup
        )
        if not is_last:
            await asyncio.sleep(0.05)

# ----------------- KEYBOARD BUILDERS -----------------

def get_main_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("✨ এখনই একটি লেখা পড়ুন", callback_data="read_now"),
            InlineKeyboardButton("🏷️ ক্যাটাগরি বাছুন", callback_data="show_categories"),
        ],
        [
            InlineKeyboardButton("📚 সাহিত্য ও লেখক ব্রাউজার", callback_data="browse_menu"),
            InlineKeyboardButton("⏰ দৈনিক শিডিউল ও স্থিতি", callback_data="view_schedule"),
        ],
        [
            InlineKeyboardButton("📜 সাহায্য ও নির্দেশিকা", callback_data="show_help"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_category_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("💖 প্রেম ও বিরহ", callback_data="set_cat_romance"),
            InlineKeyboardButton("📜 কালজয়ী ও হাইপ কবিতা", callback_data="set_cat_poetry"),
        ],
        [
            InlineKeyboardButton("📖 উপন্যাসের আকর্ষক অংশ", callback_data="set_cat_novel"),
            InlineKeyboardButton("🌌 জীবনদর্শন ও জ্ঞান", callback_data="set_cat_philosophy"),
        ],
        [
            InlineKeyboardButton("🔥 ট্রেন্ডিং ও আধুনিক", callback_data="set_cat_trending"),
            InlineKeyboardButton("🎲 সব ধারার মিশ্রণ", callback_data="set_cat_all"),
        ],
        [
            InlineKeyboardButton("🔙 মূল মেনুতে ফিরুন", callback_data="main_menu"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_authors_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("📖 রবীন্দ্রনাথ ঠাকুর", callback_data="author_tagore"),
            InlineKeyboardButton("✍️ হুমায়ূন আহমেদ", callback_data="author_humayun"),
        ],
        [
            InlineKeyboardButton("📜 কাজী নজরুল ইসলাম", callback_data="author_nazrul"),
            InlineKeyboardButton("🌿 জীবনানন্দ দাশ", callback_data="author_jibanananda"),
        ],
        [
            InlineKeyboardButton("☕ সুনীল গঙ্গোপাধ্যায়", callback_data="author_sunil"),
            InlineKeyboardButton("🌌 শীর্ষেন্দু মুখোপাধ্যায়", callback_data="author_shirshendu"),
        ],
        [
            InlineKeyboardButton("💔 হেলাল হাফিজ", callback_data="author_helal"),
            InlineKeyboardButton("⚡ রুদ্র মুহম্মদ শহিদুল্লাহ", callback_data="author_rudra"),
        ],
        [
            InlineKeyboardButton("🌧️ জয় গোস্বামী", callback_data="author_joy"),
            InlineKeyboardButton("🔥 সমকালীন ও ট্রেন্ডিং", callback_data="author_trending"),
        ],
        [
            InlineKeyboardButton("🔙 মূল মেনুতে ফিরুন", callback_data="main_menu"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_snippet_action_keyboard(category: str = "all"):
    keyboard = [
        [
            InlineKeyboardButton("🎲 আরেকটি পড়ুন", callback_data=f"read_again_{category}"),
            InlineKeyboardButton("🏷️ ক্যাটাগরি বদলান", callback_data="show_categories"),
        ],
        [
            InlineKeyboardButton("📚 লেখক বাছুন", callback_data="browse_authors"),
            InlineKeyboardButton("🔙 মূল মেনু", callback_data="main_menu"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ----------------- COMMAND HANDLERS -----------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Poetic welcome and automatic subscription."""
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user or not chat:
        return

    ensure_user_registered(user, chat)

    welcome_text = (
        f"🌸 *স্বাগতম, প্রিয় সুহৃদ {user.first_name or ''}!* 🌸\n\n"
        "শব্দ ও অনুভূতির এই নির্জন সাহিত্য আঙিনায় আপনাকে আন্তরিক অভিবাদন।\n\n"
        "প্রতিদিনের একঘেয়ে যান্ত্রিক ব্যস্ততার মাঝে আমরা আপনার হৃদয়ে পৌঁছে দেব একমুঠো সাহিত্যের সুবাস— "
        "রবীন্দ্রনাথ, নজরুল, জীবনানন্দ, হুমায়ূন আহমেদ, সুনীল থেকে শুরু করে আধুনিক তরুণ প্রজন্মের সর্বাধিক পঠিত ও আলোচিত লেখার নির্যাস।\n\n"
        "🗓️ *আপনার দৈনিক কাব্যিক সূচি (বাংলাদেশ সময়):*\n"
        "• *সকাল ১০:০০* — প্রভাতী সাহিত্যরস ও অনুপ্রেরণা\n"
        "• *দুপুর ০২:০০* — উপন্যাসের টানটান দৃশ্য ও প্রেমের উপাখ্যান\n"
        "• *রাত ১০:০০* — নিশীথ প্রহর, গভীর জীবনদর্শন ও শান্তিময় কবিতা\n\n"
        "🔔 _আপনাকে স্বয়ংক্রিয়ভাবে দৈনিক সাহিত্য সেবায় যুক্ত করা হয়েছে।_\n"
        "নিচের বোতামগুলো ছুঁয়ে এখনই আপনার সাহিত্যযাত্রা শুরু করতে পারেন:"
    )

    await message.reply_text(
        text=welcome_text,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )

async def now_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Deliver an instant literary excerpt.
    Accepts optional args: category name or author name (e.g. /now poetry, /now রবীন্দ্রনাথ).
    """
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user:
        return

    ensure_user_registered(user, chat)

    sub = database.get_subscriber(user.id)
    preferred_cat = sub["preferred_category"] if sub else "all"
    author_kw = None

    # Check for arguments passed with /now
    if context.args:
        arg_str = " ".join(context.args).strip().lower()
        # Check if arg matches any category
        for cat_key, cat_name in CATEGORIES.items():
            if arg_str in cat_key.lower() or arg_str in cat_name.lower():
                preferred_cat = cat_key
                break
        else:
            # Check if arg matches author keywords
            for a_key, a_name in AUTHORS_DIRECTORY.items():
                if arg_str in a_key or arg_str in a_name.lower():
                    author_kw = a_name
                    break
            else:
                author_kw = arg_str

    # Determine current slot based on time
    dhaka_now = datetime.datetime.now(get_dhaka_tz())
    current_hour = dhaka_now.hour

    slot = "morning"
    if 12 <= current_hour < 18:
        slot = "afternoon"
    elif current_hour >= 18 or current_hour < 5:
        slot = "night"

    snippet = curator.curate_snippet(
        user_id=user.id, 
        category=preferred_cat, 
        slot_name=slot, 
        author_keyword=author_kw
    )
    message_text = curator.format_snippet(snippet, slot_name=slot)

    await reply_snippet(
        message=message,
        text=message_text,
        reply_markup=get_snippet_action_keyboard(preferred_cat)
    )

async def category_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show categories or set directly via argument (e.g. /category poetry)."""
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user:
        return

    ensure_user_registered(user, chat)

    if context.args:
        arg_str = " ".join(context.args).strip().lower()
        matched_cat = None
        for cat_key, cat_name in CATEGORIES.items():
            if arg_str in cat_key.lower() or arg_str in cat_name.lower():
                matched_cat = cat_key
                break
        if matched_cat:
            database.set_preferred_category(user.id, matched_cat, chat_id=chat.id if chat else None)
            cat_display = CATEGORIES.get(matched_cat, "সব ধারা")
            confirm_msg = (
                f"✅ আপনার পছন্দের ধারা পরিবর্তিত হয়ে *{cat_display}* হিসেবে সংরক্ষিত হয়েছে!\n\n"
                "এখন থেকে আপনার কাছে এই ধারার লেখা বেশি প্রাধান্য পাবে।"
            )
            await message.reply_text(
                text=confirm_msg,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📖 এই ধারার একটি লেখা পড়ুন", callback_data=f"read_again_{matched_cat}")],
                    [InlineKeyboardButton("🔙 মূল মেনু", callback_data="main_menu")]
                ])
            )
            return

    sub = database.get_subscriber(user.id)
    current_cat = sub["preferred_category"] if sub else "all"
    current_name = CATEGORIES.get(current_cat, "সব ধারা")

    msg = (
        "🏷️ *সাহিত্যের রসধারা নির্বাচন*\n\n"
        f"আপনার বর্তমান পছন্দ: *{current_name}*\n\n"
        "আপনার মন কোন ধরনের সাহিত্যের স্পর্শ পেতে চায়? নিচের তালিকা থেকে আপনার প্রিয় ধারাটি নির্বাচন করুন:"
    )

    await message.reply_text(
        text=msg,
        parse_mode="Markdown",
        reply_markup=get_category_keyboard()
    )

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show scheduled slots and subscription status."""
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user:
        return

    ensure_user_registered(user, chat)
    sub = database.get_subscriber(user.id)

    is_active = sub["is_active"] == 1 if sub else True
    cat = sub["preferred_category"] if sub else "all"
    cat_name = CATEGORIES.get(cat, "সব ধারা")

    status_icon = "🟢 সক্রিয়" if is_active else "🔴 স্থগিত"

    schedule_msg = (
        "⏰ *প্রাত্যহিক সাহিত্য বিতরণের সময়সূচি*\n\n"
        "প্রতিদিন নির্দিষ্ট তিনটি প্রহরে আপনার ইনবক্সে পৌঁছে যাবে একখণ্ড অনবদ্য শব্দমালা:\n\n"
        "🌅 *সকাল ১০:০০* (১০:০০ AM) — মননশীল চিন্তা, উদ্দীপনা ও প্রভাতী কবিতা\n"
        "☀️ *দুপুর ০২:০০* (০২:০০ PM) — উপন্যাসের টানটান পর্ব ও প্রেমের গল্প\n"
        "🌙 *রাত ১০:০০* (১০:০০ PM) — গভীর জীবনদর্শন, আত্মানুসন্ধান ও নিশীথ কবিতা\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *আপনার বর্তমান স্থিতি:* {status_icon}\n"
        f"🏷️ *পছন্দের ধারা:* {cat_name}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "💡 _আপনি চাইলে যেকোনো সময় /unsubscribe দিয়ে নোটিফিকেশন সাময়িক স্থগিত করতে পারেন, এবং /start বা /subscribe দিয়ে পুনরায় সক্রিয় করতে পারেন।_"
    )

    toggle_btn = (
        InlineKeyboardButton("🔕 দৈনিক ডেলিভারি স্থগিত করুন", callback_data="toggle_pause")
        if is_active else
        InlineKeyboardButton("🔔 ডেলিভারি পুনরায় চালু করুন", callback_data="toggle_resume")
    )

    kb = InlineKeyboardMarkup([
        [toggle_btn],
        [InlineKeyboardButton("🔙 মূল মেনুতে ফিরুন", callback_data="main_menu")]
    ])

    await message.reply_text(
        text=schedule_msg,
        parse_mode="Markdown",
        reply_markup=kb
    )

async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Alias & detailed layout for daily reading plan."""
    await schedule_command(update, context)

async def browser_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Interactive browser for literature categories and authors."""
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user:
        return

    ensure_user_registered(user, chat)

    browse_text = (
        "📚 *সাহিত্য ও লেখক ব্রাউজার*\n\n"
        "বাংলা সাহিত্যের কালজয়ী রত্নভাণ্ডারে আপনাকে স্বাগতম। আপনি কোন লেখকের লেখা বা কোন বিশেষ সাহিত্যের স্বাদ নিতে চান?\n\n"
        "নিচের তালিকা থেকে আপনার প্রিয় লেখকের নাম স্পর্শ করুন, অথবা ক্যাটাগরি অনুসারে পড়তে পারেন:"
    )

    await message.reply_text(
        text=browse_text,
        parse_mode="Markdown",
        reply_markup=get_authors_keyboard()
    )

async def learn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deliver a mind-expanding philosophical and wisdom literature snippet."""
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user:
        return

    ensure_user_registered(user, chat)

    snippet = curator.curate_snippet(user_id=user.id, category="philosophy", slot_name="learn")
    msg_text = curator.format_snippet(snippet, slot_name="learn")

    await reply_snippet(
        message=message,
        text=msg_text,
        reply_markup=get_snippet_action_keyboard("philosophy")
    )

async def boost_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deliver a high-hype poem or uplifting trending literary snippet."""
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user:
        return

    ensure_user_registered(user, chat)

    snippet = curator.curate_snippet(user_id=user.id, category="poetry", slot_name="boost")
    msg_text = curator.format_snippet(snippet, slot_name="boost")

    await reply_snippet(
        message=message,
        text=msg_text,
        reply_markup=get_snippet_action_keyboard("poetry")
    )

async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Activate daily deliveries."""
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user or not chat:
        return

    ensure_user_registered(user, chat)
    database.set_subscriber_status(user.id, is_active=True, chat_id=chat.id)

    text = (
        "🔔 *সাহিত্য-ডেলিভারি সফলভাবে সক্রিয় করা হয়েছে!*\n\n"
        "প্রতিদিন নির্দিষ্ট তিনটি প্রহরে (সকাল ১০:০০, দুপুর ০২:০০ ও রাত ১০:০০) আপনার কাছে পৌঁছে যাবে "
        "বাংলা সাহিত্যের সেরা ৫০০+ শব্দের সমৃদ্ধ নির্যাস।\n\n"
        "আনন্দে কাটুক আপনার প্রতিটি মুহূর্ত!"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ এখনই একটি লেখা পড়ুন", callback_data="read_now")],
        [InlineKeyboardButton("🔙 মূল মেনু", callback_data="main_menu")]
    ])
    await message.reply_text(text=text, parse_mode="Markdown", reply_markup=kb)

async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pause daily delivery."""
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user:
        return

    if user and chat:
        database.set_subscriber_status(user.id, is_active=False, chat_id=chat.id)

    text = (
        "🔕 *সাহিত্য-ডেলিভারি সাময়িক স্থগিত করা হলো*\n\n"
        "আপনার প্রাত্যহিক সাহিত্য পাঠানোর অনুরোধটি সাময়িক স্থগিত রাখা হয়েছে। "
        "তবে সাহিত্যের দরজা সবসময় আপনার জন্য উন্মুক্ত।\n\n"
        "যখনই আবার শব্দ ও কবিতার সান্নিধ্যে ফিরতে ইচ্ছা করবে, "
        "শুধু একবার `/start` বা `/subscribe` চাপলেই আপনার সেবা পুনরায় সচল হয়ে যাবে। "
        "ভালো থাকুন, শান্তিতে থাকুন।"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔔 পুনরায় চালু করুন", callback_data="toggle_resume")],
        [InlineKeyboardButton("📖 এখনই একটি লেখা পড়ুন", callback_data="read_now")]
    ])
    await message.reply_text(text=text, parse_mode="Markdown", reply_markup=kb)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show poetic help guide."""
    message = update.effective_message
    if not message:
        return

    help_text = (
        "📖 *বাংলা সাহিত্য বট — সহায়িকা ও নির্দেশিকা* 📖\n\n"
        "এই বটটি প্রতিদিন বাংলা সাহিত্যের সেরা ও হৃদয়স্পর্শী ৫০০+ শব্দের পূর্ণাঙ্গ নির্যাস আপনার নিকট পৌঁছে দেয়।\n\n"
        "📌 *ব্যবহারযোগ্য কমান্ডসমূহ:*\n"
        "• `/start` — কাব্যিক স্বাগতম ও দৈনিক ডেলিভারিতে সাবস্ক্রিপশন\n"
        "• `/now` — এখনই তাৎক্ষণিক একটি সাহিত্য পাঠ (যেমন: `/now poetry` বা `/now রবীন্দ্রনাথ`)\n"
        "• `/category` — পছন্দের সাহিত্যধারা নির্বাচন (প্রেম, কবিতা, উপন্যাস, দর্শন, ট্রেন্ডিং)\n"
        "• `/browser` — প্রিয় লেখক ও সাহিত্যধারা ব্রাউজ করার পাতা\n"
        "• `/learn` — গভীর জীবনদর্শন ও মননশীল জ্ঞান পাঠ\n"
        "• `/boost` — উদ্দীপনামূলক ও হাইপ তোলা কবিতা পাঠ\n"
        "• `/schedule` বা `/plan` — প্রতিদিনের পাঠের সময় ও সাবস্ক্রিপশন স্থিতি\n"
        "• `/subscribe` — দৈনিক নোটিফিকেশন সচল করা\n"
        "• `/unsubscribe` — প্রাত্যহিক নোটিফিকেশন সাময়িক বন্ধ রাখা\n"
        "• `/help` — এই সহায়িকা বার্তা\n\n"
        "🌿 *লেখকদের সম্ভার:*\n"
        "রবীন্দ্রনাথ ঠাকুর, কাজী নজরুল ইসলাম, হুমায়ূন আহমেদ, সুনীল গঙ্গোপাধ্যায়, "
        "শীর্ষেন্দু মুখোপাধ্যায়, জীবনানন্দ দাশ, হেলাল হাফিজ, রুদ্র মুহম্মদ শহিদুল্লাহ, জয় গোস্বামী ও আধুনিক ট্রেন্ডিং লেখকদের অনবদ্য রচনা।"
    )
    await message.reply_text(
        text=help_text,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )

async def chat_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Poetic conversation responder when user sends general text to the bot."""
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user:
        return

    ensure_user_registered(user, chat)

    poetic_replies = (
        f"🌸 *প্রিয় সুহৃদ {user.first_name or ''},*\n\n"
        "আপনার পাঠানো প্রতিটি শব্দই অনুভূতির এক একটি স্নিগ্ধ ঢেউ। "
        "শব্দের এই নিভৃত সাহিত্য কাননে আপনার উপস্থিতি আমাদের অনুপ্রাণিত করে।\n\n"
        "আপনি কি এই মুহূর্তে কোনো বিশেষ কবিতা, উপন্যাস বা গভীর দর্শনের স্বাদ নিতে চান? "
        "নিচের বোতামগুলো ছুঁয়ে এখনই সাহিত্যের অপার সমুদ্রে ডুব দিতে পারেন:"
    )

    await message.reply_text(
        text=poetic_replies,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )

# ----------------- CALLBACK QUERY HANDLERS -----------------

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return

    try:
        await query.answer()
    except Exception:
        pass

    data = query.data
    user = update.effective_user
    chat = update.effective_chat

    if user and chat:
        ensure_user_registered(user, chat)

    try:
        if data == "main_menu":
            await query.edit_message_text(
                text="✨ *বাংলা সাহিত্য কানন — মূল পাতা*\n\nশব্দ আর কল্পনার জগতে আপনাকে স্বাগতম। আপনি কী করতে চান?",
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard()
            )
        elif data == "browse_menu" or data == "browse_authors":
            await query.edit_message_text(
                text="📚 *সাহিত্য ও লেখক সম্ভার*\n\nকোন লেখকের অনবদ্য লেখনী আপনার হৃদয় স্পর্শ করে? নিচে থেকে প্রিয় লেখক নির্বাচন করুন:",
                parse_mode="Markdown",
                reply_markup=get_authors_keyboard()
            )
        elif data.startswith("author_"):
            a_key = data.replace("author_", "")
            author_name = AUTHORS_DIRECTORY.get(a_key, "")
            snippet = curator.curate_snippet(user_id=user.id if user else None, author_keyword=author_name)
            msg_text = curator.format_snippet(snippet)
            if query.message:
                await reply_snippet(
                    message=query.message,
                    text=msg_text,
                    reply_markup=get_snippet_action_keyboard("all")
                )
        elif data == "read_now" or data.startswith("read_again_"):
            cat = "all"
            if data.startswith("read_again_"):
                cat = data.replace("read_again_", "")
            elif user:
                sub = database.get_subscriber(user.id)
                if sub:
                    cat = sub["preferred_category"]

            dhaka_now = datetime.datetime.now(get_dhaka_tz())
            current_hour = dhaka_now.hour
            slot = "morning" if current_hour < 12 else ("afternoon" if current_hour < 18 else "night")

            snippet = curator.curate_snippet(user_id=user.id if user else None, category=cat, slot_name=slot)
            msg_text = curator.format_snippet(snippet, slot_name=slot)

            if query.message:
                await reply_snippet(
                    message=query.message,
                    text=msg_text,
                    reply_markup=get_snippet_action_keyboard(cat)
                )
        elif data == "show_categories":
            sub = database.get_subscriber(user.id) if user else None
            curr = sub["preferred_category"] if sub else "all"
            cat_name = CATEGORIES.get(curr, "সব ধারা")

            await query.edit_message_text(
                text=f"🏷️ *সাহিত্যের ধারা নির্বাচন*\n\nবর্তমান পছন্দ: *{cat_name}*\n\nনিচের যেকোনো একটি ধারায় স্পর্শ করুন:",
                parse_mode="Markdown",
                reply_markup=get_category_keyboard()
            )
        elif data.startswith("set_cat_"):
            new_cat = data.replace("set_cat_", "")
            if user:
                database.set_preferred_category(user.id, new_cat, chat_id=chat.id if chat else None)
            cat_name = CATEGORIES.get(new_cat, "সব ধারা")

            confirm_msg = f"✅ আপনার পছন্দের ধারা পরিবর্তিত হয়ে *{cat_name}* হিসেবে সংরক্ষিত হয়েছে!\n\nএখন থেকে আপনার কাছে এই ধারার লেখা বেশি প্রাধান্য পাবে।"
            await query.edit_message_text(
                text=confirm_msg,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📖 এই ধারার একটি লেখা পড়ুন", callback_data=f"read_again_{new_cat}")],
                    [InlineKeyboardButton("🔙 মূল মেনু", callback_data="main_menu")]
                ])
            )
        elif data == "view_schedule":
            sub = database.get_subscriber(user.id) if user else None
            is_active = sub["is_active"] == 1 if sub else True
            cat = sub["preferred_category"] if sub else "all"
            cat_name = CATEGORIES.get(cat, "সব ধারা")
            status_icon = "🟢 সক্রিয়" if is_active else "🔴 স্থগিত"

            schedule_msg = (
                "⏰ *প্রাত্যহিক সাহিত্য বিতরণের সময়সূচি*\n\n"
                "🌅 *সকাল ১০:০০* — প্রভাতী কবিতা ও মননশীল চিন্তা\n"
                "☀️ *দুপুর ০২:০০* — উপন্যাসের টানটান পর্ব ও প্রেমের গল্প\n"
                "🌙 *রাত ১০:০০* — নিশীথ প্রহর ও গভীর জীবনদর্শন\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 *আপনার স্থিতি:* {status_icon}\n"
                f"🏷️ *পছন্দের ধারা:* {cat_name}\n"
                "━━━━━━━━━━━━━━━━━━━━"
            )
            toggle_btn = (
                InlineKeyboardButton("🔕 ডেলিভারি স্থগিত করুন", callback_data="toggle_pause")
                if is_active else
                InlineKeyboardButton("🔔 ডেলিভারি চালু করুন", callback_data="toggle_resume")
            )
            kb = InlineKeyboardMarkup([
                [toggle_btn],
                [InlineKeyboardButton("🔙 মূল মেনু", callback_data="main_menu")]
            ])
            await query.edit_message_text(text=schedule_msg, parse_mode="Markdown", reply_markup=kb)
        elif data == "toggle_pause":
            if user:
                database.set_subscriber_status(user.id, is_active=False, chat_id=chat.id if chat else None)
            await query.edit_message_text(
                text="🔕 আপনার প্রাত্যহিক সাহিত্য-ডেলিভারি সাময়িক স্থগিত করা হয়েছে।",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔔 পুনরায় চালু করুন", callback_data="toggle_resume")],
                    [InlineKeyboardButton("🔙 মূল মেনু", callback_data="main_menu")]
                ])
            )
        elif data == "toggle_resume":
            if user:
                database.set_subscriber_status(user.id, is_active=True, chat_id=chat.id if chat else None)
            await query.edit_message_text(
                text="🔔 আপনার প্রাত্যহিক সাহিত্য-ডেলিভারি পুনরায় সক্রিয় করা হয়েছে! প্রতিদিন সকাল ১০টা, দুপুর ২টা ও রাত ১০টায় লেখা পৌঁছে যাবে।",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📖 এখনই একটি লেখা পড়ুন", callback_data="read_now")],
                    [InlineKeyboardButton("🔙 মূল মেনু", callback_data="main_menu")]
                ])
            )
        elif data == "show_help":
            help_text = (
                "📖 *সহায়িকা ও কমান্ডসমূহ:*\n\n"
                "• `/start` — বটের সাথে পরিচিতি ও সাবস্ক্রিপশন\n"
                "• `/now` — এখনই চমৎকার একটি লেখা পড়া (যেমন: `/now poetry`)\n"
                "• `/category` — ক্যাটাগরি নির্ধারণ\n"
                "• `/browser` — লেখক ও সাহিত্যের পাতা ব্রাউজ করা\n"
                "• `/learn` — গভীর মনন ও জীবনদর্শন পাঠ\n"
                "• `/boost` — উদ্দীপনামূলক ও হাইপ কবিতা পাঠ\n"
                "• `/schedule` / `/plan` — সময়সূচি ও স্ট্যাটাস\n"
                "• `/subscribe` — দৈনিক ডেলিভারি সচল করা\n"
                "• `/unsubscribe` — নোটিফিকেশন বন্ধ রাখা"
            )
            await query.edit_message_text(
                text=help_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 মূল মেনু", callback_data="main_menu")]
                ])
            )
    except BadRequest as br:
        # Ignore message is not modified errors if user double-clicks inline buttons
        if "not modified" not in str(br).lower():
            logger.warning("Callback query BadRequest: %s", br)
    except Exception as e:
        logger.error("Unhandled exception in callback_query_handler: %s", e)

# ----------------- SCHEDULED JOB CALLBACKS -----------------

async def scheduled_broadcast(context: ContextTypes.DEFAULT_TYPE, slot_name: str) -> None:
    """Broadcasts a curated snippet to all active subscribers for the designated slot."""
    logger.info("Executing scheduled broadcast for slot: %s", slot_name)
    subscribers = database.get_active_subscribers()

    if not subscribers:
        logger.info("No active subscribers for broadcast.")
        return

    success_count = 0
    failure_count = 0

    for sub in subscribers:
        user_id = sub["user_id"]
        chat_id = sub["chat_id"]
        category = sub.get("preferred_category", "all")

        try:
            snippet = curator.curate_snippet(user_id=user_id, category=category, slot_name=slot_name)
            message_text = curator.format_snippet(snippet, slot_name=slot_name)

            await send_snippet_to_chat(
                bot_instance=context.bot,
                chat_id=chat_id,
                text=message_text,
                reply_markup=get_snippet_action_keyboard(category)
            )
            success_count += 1
            # Respect Telegram rate limits (~30 msgs/sec)
            await asyncio.sleep(0.05)
        except RetryAfter as r:
            logger.warning("Telegram flood limit reached. Sleeping for %s seconds.", r.retry_after)
            await asyncio.sleep(r.retry_after)
            try:
                await send_snippet_to_chat(
                    bot_instance=context.bot,
                    chat_id=chat_id,
                    text=message_text,
                    reply_markup=get_snippet_action_keyboard(category)
                )
                success_count += 1
            except Exception as e2:
                logger.warning("Retry delivery failed for user %s: %s", user_id, e2)
                failure_count += 1
        except Forbidden as blocked_err:
            logger.info("Subscriber %s blocked bot: %s. Pausing delivery.", user_id, blocked_err)
            database.set_subscriber_status(user_id, is_active=False)
            failure_count += 1
        except Exception as e:
            logger.warning("Failed to send scheduled message to user %s (chat %s): %s", user_id, chat_id, e)
            failure_count += 1
            err_str = str(e).lower()
            if "blocked" in err_str or "not found" in err_str or "deactivated" in err_str:
                logger.info("Deactivating subscriber %s due to permanent error.", user_id)
                database.set_subscriber_status(user_id, is_active=False)

    logger.info("Slot %s broadcast completed: %d succeeded, %d failed.", slot_name, success_count, failure_count)

async def morning_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    await scheduled_broadcast(context, "morning")

async def afternoon_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    await scheduled_broadcast(context, "afternoon")

async def night_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    await scheduled_broadcast(context, "night")

# ----------------- APPLICATION FACTORY -----------------

def build_application(token: Optional[str] = None) -> Application:
    """Builds and configures the Telegram Application with handlers and job queue."""
    bot_token = token or TELEGRAM_BOT_TOKEN
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not provided. Set it in .env or pass to build_application().")

    # Initialize SQLite database
    database.init_db()

    app = ApplicationBuilder().token(bot_token).build()

    # Register command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("now", now_command))
    app.add_handler(CommandHandler("category", category_command))
    app.add_handler(CommandHandler("schedule", schedule_command))
    app.add_handler(CommandHandler("plan", plan_command))
    app.add_handler(CommandHandler("browser", browser_command))
    app.add_handler(CommandHandler("browse", browser_command))
    app.add_handler(CommandHandler("learn", learn_command))
    app.add_handler(CommandHandler("boost", boost_command))
    app.add_handler(CommandHandler("subscribe", subscribe_command))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe_command))
    app.add_handler(CommandHandler("help", help_command))

    # Register callback query handler
    app.add_handler(CallbackQueryHandler(callback_query_handler))

    # Register general conversational text message handler (non-command)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_message_handler))

    # Configure JobQueue for 3 daily slots in Asia/Dhaka time
    if app.job_queue:
        tz = get_dhaka_tz()

        # Morning: 10:00 AM
        t_morning = datetime.time(hour=SCHEDULE_SLOTS["morning"]["hour"], minute=SCHEDULE_SLOTS["morning"]["minute"], tzinfo=tz)
        app.job_queue.run_daily(morning_job, time=t_morning, name="morning_literary_post")

        # Afternoon: 02:00 PM (14:00)
        t_afternoon = datetime.time(hour=SCHEDULE_SLOTS["afternoon"]["hour"], minute=SCHEDULE_SLOTS["afternoon"]["minute"], tzinfo=tz)
        app.job_queue.run_daily(afternoon_job, time=t_afternoon, name="afternoon_literary_post")

        # Night: 10:00 PM (22:00)
        t_night = datetime.time(hour=SCHEDULE_SLOTS["night"]["hour"], minute=SCHEDULE_SLOTS["night"]["minute"], tzinfo=tz)
        app.job_queue.run_daily(night_job, time=t_night, name="night_literary_post")

        logger.info("JobQueue scheduled for Asia/Dhaka at %s, %s, and %s.", 
                    SCHEDULE_SLOTS["morning"]["label"], 
                    SCHEDULE_SLOTS["afternoon"]["label"], 
                    SCHEDULE_SLOTS["night"]["label"])
    else:
        logger.warning("JobQueue is not enabled on Application. Ensure 'python-telegram-bot[job-queue]' is installed.")

    return app

def main():
    """Main entrypoint to run the Telegram bot."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("\n" + "=" * 60)
        print("❌ ত্রুটি: টেলিগ্রাম বট টোকেন পাওয়া যায়নি!")
        print("অনুগ্রহ করে আপনার .env ফাইলে TELEGRAM_BOT_TOKEN বসিয়ে নিন।")
        print("উদাহরণ: TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstUVwxyz")
        print("=" * 60 + "\n")
        sys.exit(1)

    print("🚀 বাংলা সাহিত্য বট শুরু হচ্ছে...")
    print("📍 টাইমজোন:", TIMEZONE)
    print("⏰ দৈনিক ডেলিভারি সূচি: সকাল ১০:০০, দুপুর ০২:০০, রাত ১০:০০")
    
    app = build_application()
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
