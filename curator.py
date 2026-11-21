import hashlib
import json
import logging
import random
import re
from typing import Optional, Dict, Set

from config import GEMINI_API_KEY, GEMINI_MODEL, SCHEDULE_SLOTS, CATEGORIES
from content_library import LITERATURE_ITEMS
import database

logger = logging.getLogger(__name__)

# Cached Gemini client
_genai_client = None

def get_genai_client():
    global _genai_client
    if _genai_client is None and GEMINI_API_KEY:
        try:
            from google import genai
            _genai_client = genai.Client(api_key=GEMINI_API_KEY)
        except Exception as e:
            logger.warning("Could not initialize google-genai Client: %s", e)
    return _genai_client

def count_words(text: str) -> int:
    """Accurately count Bengali words."""
    cleaned = re.sub(r'[^\w\s\u0980-\u09FF]', ' ', text)
    return len(cleaned.split())

def split_text_chunks(text: str, max_chars: int = 4000) -> list:
    """
    Splits text cleanly into chunks <= max_chars to respect Telegram's 4096 limit.
    Splits on paragraph breaks (\n\n), line breaks (\n), or spaces without cutting words.
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    remaining = text.strip()

    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break

        # Find best split point before max_chars
        split_pos = -1
        # Try splitting by double newline (paragraph boundary)
        p_pos = remaining.rfind("\n\n", 0, max_chars)
        if p_pos != -1 and p_pos >= max_chars // 2:
            split_pos = p_pos + 2
        else:
            # Try single newline
            nl_pos = remaining.rfind("\n", 0, max_chars)
            if nl_pos != -1 and nl_pos >= max_chars // 2:
                split_pos = nl_pos + 1
            else:
                # Try sentence end like Bengali dori "। "
                dori_pos = remaining.rfind("। ", 0, max_chars)
                if dori_pos != -1 and dori_pos >= max_chars // 2:
                    split_pos = dori_pos + 2
                else:
                    # Try space
                    sp_pos = remaining.rfind(" ", 0, max_chars)
                    if sp_pos != -1:
                        split_pos = sp_pos + 1
                    else:
                        # Hard split if no whitespace found
                        split_pos = max_chars

        chunk = remaining[:split_pos].rstrip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_pos:].lstrip()

    return chunks

def format_snippet(snippet: Dict, slot_name: Optional[str] = None) -> str:
    """
    Formats the snippet into the requested aesthetic Bengali layout:
    - বই/গ্রন্থের নাম (Source / Book)
    - লেখকের নাম (Author)
    - ৫০০+ শব্দের অনবদ্য নির্যাস (500+ word captivating excerpt)
    - ভাবানুভূতি / কাব্যিক মন্তব্য (Aesthetic commentary/vibe)
    """
    if slot_name == "learn":
        header = "🌌 জ্ঞান, প্রজ্ঞা ও মননশীল অনুধ্যান"
    elif slot_name == "boost":
        header = "🔥 হৃদয়ে উদ্দীপনা ও কাব্যিক অনুরণন"
    elif slot_name and slot_name in SCHEDULE_SLOTS:
        header = SCHEDULE_SLOTS[slot_name]["header"]
    else:
        header = "✨ একখণ্ড সাহিত্য ও হৃদয়ের শব্দকথা ✨"

    book = snippet.get("book", "কালজয়ী সাহিত্য")
    author = snippet.get("author", "অজ্ঞাত গুণী লেখক")
    category_key = snippet.get("category", "all")
    category_label = CATEGORIES.get(category_key, "সাহিত্যসুধা")
    excerpt = snippet.get("excerpt", "").strip()
    commentary = snippet.get("commentary", "").strip()

    message = (
        f"{header}\n\n"
        f"📖 গ্রন্থ / উৎস: {book}\n"
        f"✍️ লেখক: {author}\n"
        f"🏷️ ধারা: {category_label}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"\"{excerpt}\"\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🌿 ভাবানুভূতি: {commentary}"
    )
    return message

def get_local_snippet(
    category: str = "all", 
    slot_name: Optional[str] = None, 
    author_keyword: Optional[str] = None,
    exclude_ids: Optional[Set[str]] = None
) -> Dict:
    """
    Selects a snippet from the curated local library.
    Filters by author_keyword, category, and period_slot if specified, avoiding already seen items.
    """
    exclude_ids = exclude_ids or set()
    candidates = LITERATURE_ITEMS

    # 1. Filter by author keyword if provided
    if author_keyword:
        kw = author_keyword.strip().lower()
        if kw in ("trending", "সমকালীন", "সমকালীন ও ট্রেন্ডিং", "সমকালীন ও সমসাময়িক"):
            author_matched = [
                item for item in candidates
                if "সমকালীন" in item.get("author", "")
                or "সাদাত" in item.get("author", "")
                or item.get("id", "").startswith("sadat_")
                or item.get("id", "").startswith("trending_")
            ]
        elif kw in ("sadat", "sadat hossain", "সাদাত", "সাদাত হোসাইন"):
            author_matched = [
                item for item in candidates
                if "সাদাত" in item.get("author", "") or item.get("id", "").startswith("sadat_")
            ]
        else:
            author_matched = [
                item for item in candidates
                if kw in item.get("author", "").lower() or kw in item.get("id", "").lower()
            ]
        if author_matched:
            candidates = author_matched

    # 2. Filter by category
    if category and category != "all":
        cat_matched = [item for item in candidates if item.get("category") == category]
        if cat_matched:
            candidates = cat_matched

    # 3. Filter by slot preference if available (ignore special non-time slots like learn/boost)
    if slot_name and slot_name in SCHEDULE_SLOTS:
        slot_matched = [item for item in candidates if item.get("period_slot") in (slot_name, "any")]
        if slot_matched:
            candidates = slot_matched

    # 4. Filter out previously seen items
    unseen = [item for item in candidates if item["id"] not in exclude_ids]
    if unseen:
        return random.choice(unseen)

    # If all candidate items have been seen, fall back to any candidate
    return random.choice(candidates)

def get_gemini_dynamic_snippet(
    category: str = "all", 
    slot_name: Optional[str] = None,
    author: Optional[str] = None
) -> Optional[Dict]:
    """
    Uses Gemini API (via google-genai SDK) to dynamically generate or curate
    an authentic Bengali literature excerpt strictly >= 500 words.
    """
    if not GEMINI_API_KEY:
        return None

    client = get_genai_client()
    if not client:
        return None

    try:
        from google.genai import types

        author_instruction = f"লেখক প্রাধান্য: {author}" if author else "লেখক: রবীন্দ্রনাথ ঠাকুর, কাজী নজরুল ইসলাম, হুমায়ূন আহমেদ, সুনীল গঙ্গোপাধ্যায়, শীর্ষেন্দু মুখোপাধ্যায়, জীবনানন্দ দাশ, হেলাল হাফিজ, রুদ্র মুহম্মদ শহিদুল্লাহ, জয় গোস্বামী, কিংবা সমকালীন জনপ্রিয় ধারা"

        prompt = f"""
তুমি একজন বিদগ্ধ বাঙালি সাহিত্য সমালোচক ও সংগ্রাহক।
বাংলা সাহিত্যের কালজয়ী লেখকদের থেকে একটি অনবদ্য, গভীর ও মননশীল সাহিত্য উদ্ধৃতি/নির্যাস নির্বাচন করো।

{author_instruction}
বিভাগ: {category if category != 'all' else 'প্রেম, কবিতা, উপন্যাস, অথবা জীবনদর্শন'}
সময় প্রহর: {slot_name if slot_name else 'সাধারণ'}

কঠোর শর্তাবলি:
1. উদ্ধৃতাংশটি (excerpt) অবশ্যই নূন্যতম ৫০০ বাংলা শব্দ (৫০০ থেকে ৭৫০ শব্দ) হতে হবে। এটি যেন একটি পূর্ণাঙ্গ, মনোমুগ্ধকর দৃশ্য বা ভাবানুভূতির সম্পূর্ণ সমাপ্তি বহন করে এবং মাঝপথে হঠাৎ কেটে না যায়। সুন্দর পরিসমাপ্তির জন্য প্রয়োজনে ৫০০ শব্দের অধিক হতে পারে।
2. বই/গ্রন্থের নাম (book) এবং লেখকের নাম (author) খাঁটি ও সুনির্দিষ্ট হতে হবে।
3. ভাবানুভূতি (commentary) হবে কাব্যিক, নান্দনিক ও আধুনিক মনস্তত্ত্বের সাথে সঙ্গতিপূর্ণ (এক বা দুই লাইনে)।
4. কোনো ভূমিকা বা অতিরিক্ত কথা না বলে শুধুমাত্র নিচের JSON ফরম্যাটে আউটপুট দাও:

{{
  "book": "বই বা কাব্যগ্রন্থের নাম",
  "author": "লেখকের নাম",
  "category": "{category if category in CATEGORIES and category != 'all' else 'novel'}",
  "excerpt": "নূন্যতম ৫০০ শব্দের একটি পূর্ণাঙ্গ সাহিত্য দৃশ্য বা উদ্ধৃতি...",
  "commentary": "কাব্যিক ভাবানুভূতি..."
}}
"""
        models_to_try = [GEMINI_MODEL, "gemini-2.0-flash", "gemini-1.5-flash"]
        # Remove duplicate model names while preserving order
        unique_models = []
        for m in models_to_try:
            if m and m not in unique_models:
                unique_models.append(m)

        response = None
        for model_name in unique_models:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.7
                    )
                )
                if response and response.text:
                    break
            except Exception as e_model:
                logger.warning("Gemini model %s call failed: %s", model_name, e_model)

        if not response or not response.text:
            return None

        # Clean JSON using regex in case model includes Markdown code fences or extra text
        raw_text = response.text.strip()
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if not match:
            return None

        data = json.loads(match.group(0))
        if "excerpt" in data and "author" in data and "book" in data:
            wc = count_words(data["excerpt"])
            if wc >= 500:
                h = hashlib.sha256(data["excerpt"].encode("utf-8")).hexdigest()[:12]
                data["id"] = f"gemini_{h}"
                data["period_slot"] = slot_name or "any"
                return data
            else:
                logger.warning("Gemini generated text outside word count: %d words", wc)
    except Exception as e:
        logger.warning("Gemini dynamic curation error: %s", e)

    return None

def curate_snippet(
    user_id: Optional[int] = None, 
    category: str = "all", 
    slot_name: Optional[str] = None,
    author_keyword: Optional[str] = None,
    allow_ai: bool = True
) -> Dict:
    """
    Main entry point for getting a literary snippet.
    Picks from Gemini AI if available and enabled, otherwise uses rich local curated library.
    Tracks user history in database.
    """
    seen_ids: Set[str] = set()
    if user_id:
        seen_ids = database.get_seen_snippet_ids(user_id)

    chosen: Optional[Dict] = None

    # Occasionally or when GEMINI_API_KEY is available, try dynamic generation
    if allow_ai and GEMINI_API_KEY and random.random() < 0.4:
        chosen = get_gemini_dynamic_snippet(category=category, slot_name=slot_name, author=author_keyword)

    if not chosen:
        chosen = get_local_snippet(
            category=category, 
            slot_name=slot_name, 
            author_keyword=author_keyword, 
            exclude_ids=seen_ids
        )

    if user_id and chosen and "id" in chosen:
        database.record_delivery(user_id, chosen["id"])

    return chosen
