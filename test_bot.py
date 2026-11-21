import os
import json
import tempfile
import pytest
import datetime
import pytz
from unittest.mock import AsyncMock, MagicMock, patch
from telegram.error import BadRequest

import database
import curator
from content_library import LITERATURE_ITEMS
from config import SCHEDULE_SLOTS, CATEGORIES
import bot

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    database.init_db(db_path=path)
    yield path
    if os.path.exists(path):
        os.remove(path)

# ==================== 1. CONTENT LIBRARY TESTS ====================

def test_content_library_integrity():
    """Verify that all items have required fields and proper types."""
    assert len(LITERATURE_ITEMS) >= 40, f"Expected at least 40 items, got {len(LITERATURE_ITEMS)}"
    required_keys = {"id", "book", "author", "category", "period_slot", "excerpt", "commentary"}

    for item in LITERATURE_ITEMS:
        missing = required_keys - set(item.keys())
        assert not missing, f"Item {item.get('id')} missing keys: {missing}"
        assert item["category"] in CATEGORIES, f"Invalid category {item['category']} in {item['id']}"
        assert item["period_slot"] in ("morning", "afternoon", "night", "any")

def test_word_counts():
    """Verify that every excerpt has at least 500 words."""
    for item in LITERATURE_ITEMS:
        cwc = curator.count_words(item["excerpt"])
        assert cwc >= 500, (
            f"Item '{item['id']}' by '{item['author']}' has {cwc} Bengali words. Must be >= 500 words."
        )

def test_modular_modules_direct_import():
    """Verify that every modular item file can be imported and has >= 500 words."""
    import items_humayun
    import items_rabindranath
    import items_nazrul
    import items_sunil
    import items_jibanananda
    import items_shirshendu
    import items_helal_hafiz
    import items_rudra
    import items_joy_goswami
    import items_contemporary

    modules = [
        items_humayun.HUMAYUN_ITEMS,
        items_rabindranath.RABINDRANATH_ITEMS,
        items_nazrul.NAZRUL_ITEMS,
        items_sunil.SUNIL_ITEMS,
        items_jibanananda.JIBANANANDA_ITEMS,
        items_shirshendu.SHIRSHENDU_ITEMS,
        items_helal_hafiz.HELAL_HAFIZ_ITEMS,
        items_rudra.RUDRA_ITEMS,
        items_joy_goswami.JOY_GOSWAMI_ITEMS,
        items_contemporary.CONTEMPORARY_ITEMS,
    ]
    total_modular_items = sum(len(m) for m in modules)
    assert total_modular_items == len(LITERATURE_ITEMS) == 42
    for module_items in modules:
        for it in module_items:
            assert curator.count_words(it["excerpt"]) >= 500

def test_all_key_authors_represented():
    """Verify all requested core authors are represented in library."""
    all_authors = " ".join([item["author"] for item in LITERATURE_ITEMS])
    expected_authors = [
        "রবীন্দ্রনাথ",
        "নজরুল",
        "হুমায়ূন আহমেদ",
        "সুনীল গঙ্গোপাধ্যায়",
        "শীর্ষেন্দু",
        "জীবনানন্দ দাশ",
        "হেলাল হাফিজ",
        "রুদ্র মুহম্মদ শহিদুল্লাহ",
        "জয় গোস্বামী"
    ]
    for author in expected_authors:
        assert author in all_authors, f"Author '{author}' not found in content library!"

def test_all_categories_represented():
    """Verify romance, poetry, novel, philosophy, and trending categories are present."""
    present_categories = {item["category"] for item in LITERATURE_ITEMS}
    for cat in ["romance", "poetry", "novel", "philosophy", "trending"]:
        assert cat in present_categories, f"Category '{cat}' has no entries in content library!"

def test_slot_coverage():
    """Verify morning, afternoon, and night coverage across categories."""
    slots = {"morning", "afternoon", "night"}
    for cat in ["romance", "poetry", "novel", "philosophy", "trending"]:
        cat_items = [it for it in LITERATURE_ITEMS if it["category"] == cat]
        cat_slots = {it["period_slot"] for it in cat_items}
        # If 'any' is present or all slots covered
        for s in slots:
            matches = [it for it in cat_items if it["period_slot"] in (s, "any")]
            assert len(matches) > 0, f"Category {cat} has no matching items for slot {s}!"

# ==================== 2. CURATOR & FORMATTING TESTS ====================

def test_format_snippet_structure():
    """Verify the aesthetic Bengali layout containing book, author, excerpt, and commentary."""
    sample = {
        "book": "দেবী",
        "author": "হুমায়ূন আহমেদ",
        "category": "novel",
        "excerpt": "মানুষের মন এক গহীন অরণ্য...",
        "commentary": "যুক্তিবাদ ও রহস্যের দোলাচল।"
    }

    formatted = curator.format_snippet(sample, slot_name="afternoon")
    assert "মধ্যাহ্নের শব্দকাব্য" in formatted
    assert "📖 গ্রন্থ / উৎস: দেবী" in formatted
    assert "✍️ লেখক: হুমায়ূন আহমেদ" in formatted
    assert "🏷️ ধারা: 📖 উপন্যাসের আকর্ষক অংশ" in formatted
    assert '"মানুষের মন এক গহীন অরণ্য..."' in formatted
    assert "🌿 ভাবানুভূতি: যুক্তিবাদ ও রহস্যের দোলাচল।" in formatted

def test_format_snippet_custom_headers():
    """Verify custom headers for learn and boost."""
    sample = {
        "book": "গীতাঞ্জলি",
        "author": "রবীন্দ্রনাথ ঠাকুর",
        "category": "poetry",
        "excerpt": "আমার মাথা নত করে দাও...",
        "commentary": "সমর্পণ।"
    }
    learn_formatted = curator.format_snippet(sample, slot_name="learn")
    assert "জ্ঞান, প্রজ্ঞা ও মননশীল অনুধ্যান" in learn_formatted

    boost_formatted = curator.format_snippet(sample, slot_name="boost")
    assert "হৃদয়ে উদ্দীপনা ও কাব্যিক অনুরণন" in boost_formatted

def test_get_local_snippet_filtering():
    """Verify category filtering and slot preference."""
    romance_item = curator.get_local_snippet(category="romance")
    assert romance_item["category"] == "romance"

    morning_item = curator.get_local_snippet(slot_name="morning")
    assert morning_item["period_slot"] in ("morning", "any")

def test_get_local_snippet_author_filtering():
    """Verify author keyword filtering in local snippet selection."""
    item = curator.get_local_snippet(author_keyword="রবীন্দ্রনাথ")
    assert "রবীন্দ্রনাথ" in item["author"]

    item_humayun = curator.get_local_snippet(author_keyword="হুমায়ূন আহমেদ")
    assert "হুমায়ূন" in item_humayun["author"]

def test_get_local_snippet_exclusion():
    """Verify that seen items are excluded until exhausted."""
    all_ids = {item["id"] for item in LITERATURE_ITEMS}
    exclude_all_but_one = set(list(all_ids)[:-1])
    remaining_id = list(all_ids - exclude_all_but_one)[0]

    picked = curator.get_local_snippet(exclude_ids=exclude_all_but_one)
    assert picked["id"] == remaining_id

def test_gemini_dynamic_snippet_parsing():
    """Verify get_gemini_dynamic_snippet parses markdown-fenced json and counts words."""
    mock_payload = {
        "book": "শেষের কবিতা",
        "author": "রবীন্দ্রনাথ ঠাকুর",
        "category": "romance",
        "excerpt": " " .join(["বাংলা"] * 500),
        "commentary": "কাব্যিক ভাবানুভূতি।"
    }
    markdown_wrapped_json = f"```json\n{json.dumps(mock_payload, ensure_ascii=False)}\n```"

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = markdown_wrapped_json
    mock_client.models.generate_content.return_value = mock_response

    with patch.object(curator, "GEMINI_API_KEY", "dummy_key"):
        with patch.object(curator, "get_genai_client", return_value=mock_client):
            result = curator.get_gemini_dynamic_snippet(category="romance")
            assert result is not None
            assert result["book"] == "শেষের কবিতা"
            assert result["author"] == "রবীন্দ্রনাথ ঠাকুর"
            assert result["id"].startswith("gemini_")

# ==================== 3. DATABASE TESTS ====================

def test_add_and_retrieve_subscriber(temp_db):
    """Verify adding, updating, and querying subscribers."""
    is_new = database.add_or_update_subscriber(
        user_id=101,
        chat_id=101,
        username="user101",
        first_name="Rahim",
        db_path=temp_db
    )
    assert is_new is True

    sub = database.get_subscriber(user_id=101, db_path=temp_db)
    assert sub is not None
    assert sub["username"] == "user101"
    assert sub["is_active"] == 1
    assert sub["preferred_category"] == "all"

    # Updating existing subscriber
    is_new2 = database.add_or_update_subscriber(
        user_id=101,
        chat_id=101,
        username="user101_updated",
        first_name="Rahim Updated",
        db_path=temp_db
    )
    assert is_new2 is False
    sub2 = database.get_subscriber(user_id=101, db_path=temp_db)
    assert sub2["first_name"] == "Rahim Updated"

def test_subscriber_pause_and_resume(temp_db):
    """Verify pausing and reactivating subscription."""
    database.add_or_update_subscriber(user_id=202, chat_id=202, db_path=temp_db)
    
    # Pause
    database.set_subscriber_status(user_id=202, is_active=False, db_path=temp_db)
    sub = database.get_subscriber(202, db_path=temp_db)
    assert sub["is_active"] == 0
    assert len(database.get_active_subscribers(db_path=temp_db)) == 0

    # Resume
    database.set_subscriber_status(user_id=202, is_active=True, db_path=temp_db)
    sub = database.get_subscriber(202, db_path=temp_db)
    assert sub["is_active"] == 1
    assert len(database.get_active_subscribers(db_path=temp_db)) == 1

def test_set_subscriber_status_creates_record_if_absent(temp_db):
    """Verify set_subscriber_status creates subscriber if chat_id provided."""
    res = database.set_subscriber_status(user_id=888, is_active=True, chat_id=888, db_path=temp_db)
    assert res is True
    sub = database.get_subscriber(888, db_path=temp_db)
    assert sub is not None
    assert sub["is_active"] == 1

def test_category_preference(temp_db):
    """Verify setting category preference."""
    database.add_or_update_subscriber(user_id=303, chat_id=303, db_path=temp_db)
    database.set_preferred_category(user_id=303, category="poetry", db_path=temp_db)
    sub = database.get_subscriber(303, db_path=temp_db)
    assert sub["preferred_category"] == "poetry"

def test_set_preferred_category_creates_record_if_absent(temp_db):
    """Verify set_preferred_category creates subscriber if chat_id provided."""
    res = database.set_preferred_category(user_id=999, category="romance", chat_id=999, db_path=temp_db)
    assert res is True
    sub = database.get_subscriber(999, db_path=temp_db)
    assert sub is not None
    assert sub["preferred_category"] == "romance"

def test_delivery_history(temp_db):
    """Verify delivery recording and seen ID tracking."""
    database.record_delivery(user_id=404, snippet_id="item_01", db_path=temp_db)
    database.record_delivery(user_id=404, snippet_id="item_02", db_path=temp_db)

    seen = database.get_seen_snippet_ids(user_id=404, db_path=temp_db)
    assert seen == {"item_01", "item_02"}

# ==================== 4. BOT APPLICATION & SCHEDULE TESTS ====================

def test_bot_application_builder():
    """Verify application builds with handlers and registered scheduled jobs."""
    dummy_token = "123456789:ABCdefGhIJKlmNoPQRstUVwxyz-TestToken"
    app = bot.build_application(token=dummy_token)
    assert app is not None
    assert app.job_queue is not None

    job_names = [j.name for j in app.job_queue.jobs()]
    assert "morning_literary_post" in job_names
    assert "afternoon_literary_post" in job_names
    assert "night_literary_post" in job_names

def test_schedule_times():
    """Verify the 3 slots match 10:00, 14:00, and 22:00 in Asia/Dhaka."""
    assert SCHEDULE_SLOTS["morning"]["hour"] == 10
    assert SCHEDULE_SLOTS["morning"]["minute"] == 0

    assert SCHEDULE_SLOTS["afternoon"]["hour"] == 14
    assert SCHEDULE_SLOTS["afternoon"]["minute"] == 0

    assert SCHEDULE_SLOTS["night"]["hour"] == 22
    assert SCHEDULE_SLOTS["night"]["minute"] == 0

@pytest.mark.asyncio
async def test_scheduled_broadcast_flow(temp_db, monkeypatch):
    """Simulate broadcast to active subscribers and error handling for blocked users."""
    monkeypatch.setattr(database, "DATABASE_PATH", temp_db)
    monkeypatch.setattr(curator, "database", database)
    monkeypatch.setattr(bot, "database", database)

    database.add_or_update_subscriber(user_id=501, chat_id=501, db_path=temp_db)
    database.add_or_update_subscriber(user_id=502, chat_id=502, db_path=temp_db)
    database.set_subscriber_status(user_id=502, is_active=False, db_path=temp_db)

    mock_context = MagicMock()
    mock_bot = AsyncMock()
    mock_context.bot = mock_bot

    await bot.scheduled_broadcast(mock_context, "morning")

    assert mock_bot.send_message.call_count == 1
    call_args = mock_bot.send_message.call_args[1]
    assert call_args["chat_id"] == 501
    assert "📖 গ্রন্থ / উৎস:" in call_args["text"]
    assert "✍️ লেখক:" in call_args["text"]
    assert "🌿 ভাবানুভূতি:" in call_args["text"]

# ==================== 5. COMMAND & CALLBACK INTERACTION TESTS ====================

@pytest.mark.asyncio
async def test_start_command_registers_subscriber(temp_db, monkeypatch):
    """Verify /start enrolls user and sends warm welcome."""
    monkeypatch.setattr(database, "DATABASE_PATH", temp_db)
    monkeypatch.setattr(bot, "database", database)

    mock_update = MagicMock()
    mock_user = MagicMock()
    mock_user.id = 701
    mock_user.username = "tanzim"
    mock_user.first_name = "তানজিম"
    mock_chat = MagicMock()
    mock_chat.id = 701

    mock_update.effective_user = mock_user
    mock_update.effective_chat = mock_chat
    mock_message = AsyncMock()
    mock_update.effective_message = mock_message

    mock_context = MagicMock()

    await bot.start_command(mock_update, mock_context)

    sub = database.get_subscriber(701, db_path=temp_db)
    assert sub is not None
    assert sub["first_name"] == "তানজিম"
    assert sub["is_active"] == 1

    assert mock_message.reply_text.call_count == 1
    reply_text = mock_message.reply_text.call_args[1]["text"]
    assert "স্বাগতম, প্রিয় সুহৃদ তানজিম" in reply_text
    assert "সকাল ১০:০০" in reply_text
    assert "রাত ১০:০০" in reply_text

@pytest.mark.asyncio
async def test_now_command_delivers_excerpt(temp_db, monkeypatch):
    """Verify /now responds immediately with formatted literature."""
    monkeypatch.setattr(database, "DATABASE_PATH", temp_db)
    monkeypatch.setattr(bot, "database", database)
    monkeypatch.setattr(curator, "database", database)

    mock_update = MagicMock()
    mock_user = MagicMock()
    mock_user.id = 702
    mock_chat = MagicMock()
    mock_chat.id = 702
    mock_update.effective_user = mock_user
    mock_update.effective_chat = mock_chat
    mock_message = AsyncMock()
    mock_update.effective_message = mock_message

    mock_context = MagicMock()
    mock_context.args = []

    await bot.now_command(mock_update, mock_context)

    assert mock_message.reply_text.call_count == 1
    text = mock_message.reply_text.call_args[1]["text"]
    assert "📖 গ্রন্থ / উৎস:" in text
    assert "✍️ লেখক:" in text
    assert "🌿 ভাবানুভূতি:" in text

@pytest.mark.asyncio
async def test_now_command_with_category_and_author_args(temp_db, monkeypatch):
    """Verify /now with arguments like /now poetry or /now রবীন্দ্রনাথ."""
    monkeypatch.setattr(database, "DATABASE_PATH", temp_db)
    monkeypatch.setattr(bot, "database", database)
    monkeypatch.setattr(curator, "database", database)

    mock_update = MagicMock()
    mock_user = MagicMock()
    mock_user.id = 702
    mock_chat = MagicMock()
    mock_chat.id = 702
    mock_update.effective_user = mock_user
    mock_update.effective_chat = mock_chat
    mock_message = AsyncMock()
    mock_update.effective_message = mock_message

    mock_context = MagicMock()
    mock_context.args = ["রবীন্দ্রনাথ"]

    await bot.now_command(mock_update, mock_context)
    text = mock_message.reply_text.call_args[1]["text"]
    assert "রবীন্দ্রনাথ ঠাকুর" in text

@pytest.mark.asyncio
async def test_category_command_with_and_without_args(temp_db, monkeypatch):
    """Verify /category without args opens menu, and with args sets preference directly."""
    monkeypatch.setattr(database, "DATABASE_PATH", temp_db)
    monkeypatch.setattr(bot, "database", database)

    mock_update = MagicMock()
    mock_user = MagicMock()
    mock_user.id = 703
    mock_chat = MagicMock()
    mock_chat.id = 703
    mock_update.effective_user = mock_user
    mock_update.effective_chat = mock_chat
    mock_message = AsyncMock()
    mock_update.effective_message = mock_message

    # Without args: shows menu
    mock_context = MagicMock()
    mock_context.args = []
    await bot.category_command(mock_update, mock_context)
    menu_text = mock_message.reply_text.call_args[1]["text"]
    assert "সাহিত্যের রসধারা নির্বাচন" in menu_text

    # With arg: sets category directly
    mock_context.args = ["poetry"]
    await bot.category_command(mock_update, mock_context)
    sub = database.get_subscriber(703, db_path=temp_db)
    assert sub["preferred_category"] == "poetry"

@pytest.mark.asyncio
async def test_additional_commands(temp_db, monkeypatch):
    """Verify /plan, /browser, /learn, /boost, /subscribe, and /help commands."""
    monkeypatch.setattr(database, "DATABASE_PATH", temp_db)
    monkeypatch.setattr(bot, "database", database)
    monkeypatch.setattr(curator, "database", database)

    mock_update = MagicMock()
    mock_user = MagicMock()
    mock_user.id = 705
    mock_chat = MagicMock()
    mock_chat.id = 705
    mock_update.effective_user = mock_user
    mock_update.effective_chat = mock_chat
    mock_message = AsyncMock()
    mock_update.effective_message = mock_message
    mock_context = MagicMock()

    # /plan
    await bot.plan_command(mock_update, mock_context)
    assert "প্রাত্যহিক সাহিত্য বিতরণের সময়সূচি" in mock_message.reply_text.call_args[1]["text"]

    # /browser
    await bot.browser_command(mock_update, mock_context)
    assert "সাহিত্য ও লেখক ব্রাউজার" in mock_message.reply_text.call_args[1]["text"]

    # /learn
    await bot.learn_command(mock_update, mock_context)
    assert "জ্ঞান, প্রজ্ঞা ও মননশীল অনুধ্যান" in mock_message.reply_text.call_args[1]["text"]

    # /boost
    await bot.boost_command(mock_update, mock_context)
    assert "হৃদয়ে উদ্দীপনা ও কাব্যিক অনুরণন" in mock_message.reply_text.call_args[1]["text"]

    # /subscribe
    await bot.subscribe_command(mock_update, mock_context)
    assert "সফলভাবে সক্রিয়" in mock_message.reply_text.call_args[1]["text"]
    sub = database.get_subscriber(705, db_path=temp_db)
    assert sub["is_active"] == 1

    # /help
    await bot.help_command(mock_update, mock_context)
    assert "বাংলা সাহিত্য বট — সহায়িকা" in mock_message.reply_text.call_args[1]["text"]

@pytest.mark.asyncio
async def test_conversational_chat_message_handler(temp_db, monkeypatch):
    """Verify general text messages receive poetic Bengali author-style response."""
    monkeypatch.setattr(database, "DATABASE_PATH", temp_db)
    monkeypatch.setattr(bot, "database", database)

    mock_update = MagicMock()
    mock_user = MagicMock()
    mock_user.id = 706
    mock_user.first_name = "সৌম্য"
    mock_chat = MagicMock()
    mock_chat.id = 706
    mock_update.effective_user = mock_user
    mock_update.effective_chat = mock_chat
    mock_message = AsyncMock()
    mock_message.text = "কেমন আছেন?"
    mock_update.effective_message = mock_message
    mock_context = MagicMock()

    await bot.chat_message_handler(mock_update, mock_context)
    assert mock_message.reply_text.call_count == 1
    reply = mock_message.reply_text.call_args[1]["text"]
    assert "প্রিয় সুহৃদ সৌম্য" in reply
    assert "অনুভূতির এক একটি স্নিগ্ধ ঢেউ" in reply

@pytest.mark.asyncio
async def test_callback_category_and_author_selection(temp_db, monkeypatch):
    """Verify callback queries for categories, author browsing, and error suppression."""
    monkeypatch.setattr(database, "DATABASE_PATH", temp_db)
    monkeypatch.setattr(bot, "database", database)
    monkeypatch.setattr(curator, "database", database)

    mock_update = MagicMock()
    mock_query = AsyncMock()
    mock_user = MagicMock()
    mock_user.id = 707
    mock_chat = MagicMock()
    mock_chat.id = 707
    mock_update.effective_user = mock_user
    mock_update.effective_chat = mock_chat

    # 1. Category selection
    mock_query.data = "set_cat_poetry"
    mock_update.callback_query = mock_query
    mock_context = MagicMock()

    await bot.callback_query_handler(mock_update, mock_context)
    sub = database.get_subscriber(707, db_path=temp_db)
    assert sub["preferred_category"] == "poetry"
    assert "কালজয়ী ও হাইপ তোলা কবিতা" in mock_query.edit_message_text.call_args[1]["text"]

    # 2. Author browsing selection
    mock_query.reset_mock()
    mock_query.data = "author_tagore"
    mock_query.message = AsyncMock()
    await bot.callback_query_handler(mock_update, mock_context)
    assert mock_query.message.reply_text.call_count == 1
    author_reply = mock_query.message.reply_text.call_args[1]["text"]
    assert "রবীন্দ্রনাথ ঠাকুর" in author_reply

    # 3. Suppress BadRequest "message is not modified"
    mock_query.edit_message_text.side_effect = BadRequest("Message is not modified")
    mock_query.data = "main_menu"
    # Should not raise exception
    await bot.callback_query_handler(mock_update, mock_context)

def test_split_text_chunks():
    """Verify split_text_chunks properly breaks long texts along natural boundaries."""
    # Under limit
    short_text = "একটি ছোট বাংলা বাক্য।"
    assert curator.split_text_chunks(short_text, max_chars=100) == [short_text]

    # Paragraph boundary
    p1 = "প্রথম অনুচ্ছেদ।" * 20
    p2 = "দ্বিতীয় অনুচ্ছেদ।" * 20
    full_text = f"{p1}\n\n{p2}"
    chunks = curator.split_text_chunks(full_text, max_chars=max(len(p1), len(p2)) + 10)
    assert len(chunks) == 2
    assert chunks[0] == p1
    assert chunks[1] == p2

    # Unbroken string exceeding limit
    unbroken = "বাংলা" * 200  # 1000 chars
    chunks_unbroken = curator.split_text_chunks(unbroken, max_chars=400)
    assert len(chunks_unbroken) == 3
    assert len(chunks_unbroken[0]) <= 400
    assert len(chunks_unbroken[1]) <= 400

@pytest.mark.asyncio
async def test_all_author_browsing_callbacks(temp_db, monkeypatch):
    """Verify callback queries for every author in AUTHORS_DIRECTORY return appropriate snippets."""
    monkeypatch.setattr(database, "DATABASE_PATH", temp_db)
    monkeypatch.setattr(bot, "database", database)
    monkeypatch.setattr(curator, "database", database)

    mock_update = MagicMock()
    mock_query = AsyncMock()
    mock_user = MagicMock()
    mock_user.id = 708
    mock_chat = MagicMock()
    mock_chat.id = 708
    mock_update.effective_user = mock_user
    mock_update.effective_chat = mock_chat
    mock_context = MagicMock()

    for a_key, a_name in bot.AUTHORS_DIRECTORY.items():
        mock_query.reset_mock()
        mock_query.data = f"author_{a_key}"
        mock_query.message = AsyncMock()
        mock_update.callback_query = mock_query

        await bot.callback_query_handler(mock_update, mock_context)
        assert mock_query.message.reply_text.call_count == 1
        reply = mock_query.message.reply_text.call_args[1]["text"]
        assert "📖 গ্রন্থ / উৎস:" in reply
        assert "✍️ লেখক:" in reply
        if a_key == "trending":
            assert any(x in reply for x in ["সাদাত হোসাইন", "সমকালীন", "তারুণ্য"])
        elif a_key == "sadat":
            assert "সাদাত হোসাইন" in reply
        else:
            assert a_name in reply
