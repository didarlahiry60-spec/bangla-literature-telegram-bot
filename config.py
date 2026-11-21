import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

# Gemini API Key (optional for dynamic AI-powered literature curation)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

# Timezone settings (Default to Asia/Dhaka)
TIMEZONE = os.getenv("TIMEZONE", "Asia/Dhaka")

# Database path
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "subscribers.db"))

# Scheduled hours (24h format in TIMEZONE)
SCHEDULE_SLOTS = {
    "morning": {
        "hour": 10,
        "minute": 0,
        "label": "সকাল ১০:০০",
        "name": "প্রভাতী সাহিত্যরস",
        "header": "🌅 প্রভাতী সাহিত্যরস ও অনুভবের আলাপন",
        "description": "মননশীল চিন্তা, অনুপ্রেরণা ও প্রভাতী কবিতা"
    },
    "afternoon": {
        "hour": 14,
        "minute": 0,
        "label": "দুপুর ০২:০০",
        "name": "মধ্যাহ্নের শব্দকাব্য",
        "header": "☀️ মধ্যাহ্নের শব্দকাব্য ও রোমাঞ্চকর পাঠ",
        "description": "জনপ্রিয় উপন্যাসের টানটান দৃশ্য ও প্রেমের উপাখ্যান"
    },
    "night": {
        "hour": 22,
        "minute": 0,
        "label": "রাত ১০:০০",
        "name": "নিশীথ ভাবনার নির্যাস",
        "header": "🌙 নিশীথ প্রহর ও নির্জন ভাবনার নির্যাস",
        "description": "গভীর জীবনদর্শন, বিরহ, আত্মানুসন্ধান ও শান্তিময় কবিতা"
    }
}

# Category mappings in Bengali
CATEGORIES = {
    "romance": "💖 প্রেম ও বিরহের কথন",
    "poetry": "📜 কালজয়ী ও হাইপ তোলা কবিতা",
    "novel": "📖 উপন্যাসের আকর্ষক অংশ",
    "philosophy": "🌌 জীবনদর্শন ও গভীর জ্ঞান",
    "trending": "🔥 তরুণ প্রজন্মের ট্রেন্ডিং ও সমকালীন সাহিত্য",
    "all": "🎲 সব ধারার মিশ্র নির্যাস"
}
