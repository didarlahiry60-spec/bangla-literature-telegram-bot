import json
import os

with open("literature.json", "r", encoding="utf-8") as f:
    items = json.load(f)

items_json = json.dumps(items, ensure_ascii=False, indent=2)

template = """// Cloudflare Worker for Bangla Literature Telegram Bot (24/7 Serverless)
// Backed by Cloudflare D1 (SQLite) and Cron Triggers

const LITERATURE_ITEMS = __LITERATURE_ITEMS_JSON__;

const AUTHORS_DIRECTORY = {
  tagore: "রবীন্দ্রনাথ ঠাকুর",
  nazrul: "কাজী নজরুল ইসলাম",
  humayun: "হুমায়ূন আহমেদ",
  sunil: "সুনীল গঙ্গোপাধ্যায়",
  shirshendu: "শীর্ষেন্দু মুখোপাধ্যায়",
  jibanananda: "জীবনানন্দ দাশ",
  helal: "হেলাল হাফিজ",
  rudra: "রুদ্র মুহম্মদ শহিদুল্লাহ",
  joy: "জয় গোস্বামী",
  sadat: "সাদাত হোসাইন",
  trending: "সমকালীন ও ট্রেন্ডিং"
};

const CATEGORIES = {
  romance: "💖 প্রেম ও অনুরাগের গল্প",
  novel: "📖 উপন্যাসের রোমাঞ্চকর দৃশ্য",
  poetry: "🔥 আগুন ও আবেগের কবিতা",
  philosophy: "🌌 জীবনদর্শন ও গভীর জ্ঞান",
  trending: "✨ সমকালীন সাহিত্য ও তরুণ ভাবনা"
};

const SCHEDULE_SLOTS = {
  morning: {
    header: "🌅 প্রভাতী সাহিত্যরস ও অনুভবের আলাপন",
    description: "মননশীল চিন্তা, অনুপ্রেরণা ও প্রভাতী কবিতা"
  },
  afternoon: {
    header: "☀️ মধ্যাহ্নের শব্দকাব্য ও রোমাঞ্চকর পাঠ",
    description: "জনপ্রিয় উপন্যাসের টানটান দৃশ্য ও প্রেমের উপাখ্যান"
  },
  night: {
    header: "🌙 নিশীথ প্রহর ও নির্জন ভাবনার নির্যাস",
    description: "গভীর জীবনদর্শন, বিরহ, আত্মানুসন্ধান ও শান্তিময় কবিতা"
  }
};

function countWords(text) {
  const cleaned = text.replace(/[^\\w\\s\\u0980-\\u09FF]/g, " ");
  return cleaned.trim().split(/\\s+/).filter(Boolean).length;
}

function splitTextChunks(text, maxChars = 3800) {
  if (text.length <= maxChars) return [text];
  const chunks = [];
  let remaining = text;
  while (remaining.length > 0) {
    if (remaining.length <= maxChars) {
      chunks.push(remaining);
      break;
    }
    let splitPos = remaining.lastIndexOf("\\n\\n", maxChars);
    if (splitPos === -1 || splitPos < maxChars * 0.4) {
      splitPos = remaining.lastIndexOf("\\n", maxChars);
    }
    if (splitPos === -1 || splitPos < maxChars * 0.4) {
      splitPos = remaining.lastIndexOf(" ", maxChars);
    }
    if (splitPos === -1) splitPos = maxChars;
    chunks.push(remaining.substring(0, splitPos).trim());
    remaining = remaining.substring(splitPos).trim();
  }
  return chunks;
}

function formatSnippet(snippet, slotName = null) {
  let header = "✨ একখণ্ড সাহিত্য ও হৃদয়ের শব্দকথা ✨";
  if (slotName === "learn") {
    header = "🌌 জ্ঞান, প্রজ্ঞা ও মননশীল অনুধ্যান";
  } else if (slotName === "boost") {
    header = "🔥 হৃদয়ে উদ্দীপনা ও কাব্যিক অনুরণন";
  } else if (slotName && SCHEDULE_SLOTS[slotName]) {
    header = SCHEDULE_SLOTS[slotName].header;
  }

  const book = snippet.book || "কালজয়ী সাহিত্য";
  const author = snippet.author || "অজ্ঞাত গুণী লেখক";
  const catKey = snippet.category || "all";
  const catLabel = CATEGORIES[catKey] || "সাহিত্যসুধা";
  const excerpt = (snippet.excerpt || "").trim();
  const commentary = (snippet.commentary || "").trim();

  return `${header}\\n\\n` +
    `📖 গ্রন্থ / উৎস: ${book}\\n` +
    `✍️ লেখক: ${author}\\n` +
    `🏷️ ধারা: ${catLabel}\\n` +
    `━━━━━━━━━━━━━━━━━━━━\\n` +
    `"${excerpt}"\\n` +
    `━━━━━━━━━━━━━━━━━━━━\\n` +
    `🌿 ভাবানুভূতি: ${commentary}`;
}

function getLocalSnippet(category = "all", slotName = null, authorKeyword = null, excludeIds = new Set()) {
  let candidates = LITERATURE_ITEMS;

  if (authorKeyword) {
    const kw = authorKeyword.trim().toLowerCase();
    const isTrendingKw = ["trending", "সমকালীন ও ট্রেন্ডিং", "সমকালীন", "তরুণ", "contemporary"].some(k => kw.includes(k));
    const isSadatKw = ["sadat", "সাদাত", "সাদাত হোসাইন"].some(k => kw.includes(k));

    let matched = [];
    if (isTrendingKw) {
      matched = candidates.filter(item => 
        (item.author || "").includes("সাদাত") || 
        (item.author || "").includes("সমকালীন") || 
        item.id.includes("trending") || 
        item.id.includes("sadat")
      );
    } else if (isSadatKw) {
      matched = candidates.filter(item => (item.author || "").includes("সাদাত") || item.id.includes("sadat"));
    } else {
      matched = candidates.filter(item => (item.author || "").toLowerCase().includes(kw));
    }
    if (matched.length > 0) candidates = matched;
  }

  if (category && category !== "all") {
    const catMatched = candidates.filter(item => item.category === category);
    if (catMatched.length > 0) candidates = catMatched;
  }

  if (slotName && SCHEDULE_SLOTS[slotName]) {
    const slotMatched = candidates.filter(item => item.period_slot === slotName || item.period_slot === "any");
    if (slotMatched.length > 0) candidates = slotMatched;
  }

  const unseen = candidates.filter(item => !excludeIds.has(item.id));
  if (unseen.length > 0) {
    return unseen[Math.floor(Math.random() * unseen.length)];
  }
  return candidates[Math.floor(Math.random() * candidates.length)];
}

async function sendTelegramMessage(token, chatId, text, extra = {}) {
  const chunks = splitTextChunks(text, 3800);
  for (let i = 0; i < chunks.length; i++) {
    const payload = {
      chat_id: chatId,
      text: chunks[i],
      ...((i === chunks.length - 1) ? extra : {})
    };
    await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  }
}

async function answerCallbackQuery(token, callbackQueryId, text = "") {
  await fetch(`https://api.telegram.org/bot${token}/answerCallbackQuery`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ callback_query_id: callbackQueryId, text })
  });
}

async function upsertSubscriber(db, chatId, firstName, username) {
  if (!db) return;
  try {
    await db.prepare(`
      INSERT INTO subscribers (chat_id, first_name, username, is_active, preferred_category, created_at, updated_at)
      VALUES (?, ?, ?, 1, 'all', datetime('now'), datetime('now'))
      ON CONFLICT(chat_id) DO UPDATE SET
        first_name = COALESCE(excluded.first_name, subscribers.first_name),
        username = COALESCE(excluded.username, subscribers.username),
        is_active = 1,
        updated_at = datetime('now')
    `).bind(chatId, firstName, username).run();
  } catch (err) {
    console.error("D1 upsertSubscriber error:", err);
  }
}

async function setSubscriberStatus(db, chatId, isActive) {
  if (!db) return;
  await db.prepare(`
    INSERT INTO subscribers (chat_id, is_active, updated_at)
    VALUES (?, ?, datetime('now'))
    ON CONFLICT(chat_id) DO UPDATE SET is_active = ?, updated_at = datetime('now')
  `).bind(chatId, isActive ? 1 : 0, isActive ? 1 : 0).run();
}

async function setPreferredCategory(db, chatId, category) {
  if (!db) return;
  await db.prepare(`
    INSERT INTO subscribers (chat_id, preferred_category, updated_at)
    VALUES (?, ?, datetime('now'))
    ON CONFLICT(chat_id) DO UPDATE SET preferred_category = ?, updated_at = datetime('now')
  `).bind(chatId, category, category).run();
}

async function getSubscriber(db, chatId) {
  if (!db) return null;
  const res = await db.prepare("SELECT * FROM subscribers WHERE chat_id = ?").bind(chatId).first();
  return res;
}

async function getRecentSnippetIds(db, chatId, limit = 20) {
  if (!db) return new Set();
  const res = await db.prepare("SELECT snippet_id FROM delivery_history WHERE chat_id = ? ORDER BY id DESC LIMIT ?").bind(chatId, limit).all();
  return new Set((res.results || []).map(r => r.snippet_id));
}

async function recordDelivery(db, chatId, snippetId, slotName) {
  if (!db) return;
  await db.prepare("INSERT INTO delivery_history (chat_id, snippet_id, slot_name, delivered_at) VALUES (?, ?, ?, datetime('now'))").bind(chatId, snippetId, slotName).run();
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Endpoint to configure Telegram webhook automatically
    if (url.pathname === "/set-webhook") {
      const webhookUrl = `${url.origin}/webhook`;
      const res = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/setWebhook?url=${encodeURIComponent(webhookUrl)}`);
      const data = await res.json();
      return new Response(JSON.stringify({ webhookUrl, telegramResponse: data }, null, 2), {
        headers: { "Content-Type": "application/json" }
      });
    }

    // Landing status page
    if (url.pathname === "/" || url.pathname === "") {
      return new Response(`
        <!DOCTYPE html>
        <html lang="bn">
        <head>
          <meta charset="UTF-8">
          <title>বাংলা সাহিত্য বট — Cloudflare Workers 24/7</title>
          <style>
            body { font-family: system-ui, -apple-system, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }
            .card { background: #1e293b; padding: 2.5rem; border-radius: 1rem; box-shadow: 0 10px 25px rgba(0,0,0,0.5); max-width: 540px; border: 1px solid #334155; text-align: center; }
            h1 { color: #38bdf8; font-size: 1.8rem; margin-bottom: 0.5rem; }
            p { color: #94a3b8; line-height: 1.6; }
            .badge { display: inline-block; background: #065f46; color: #34d399; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.85rem; font-weight: 600; margin-bottom: 1rem; }
            .btn { display: inline-block; margin-top: 1.5rem; background: #0284c7; color: white; text-decoration: none; padding: 0.75rem 1.5rem; border-radius: 0.5rem; font-weight: 600; transition: background 0.2s; }
            .btn:hover { background: #0369a1; }
          </style>
        </head>
        <body>
          <div class="card">
            <span class="badge">● 24/7 Serverless Active</span>
            <h1>বাংলা সাহিত্য টেলিগ্রাম বট</h1>
            <p>ক্লাউডফ্লেয়ার ওয়ার্কার্স ও D1 ডাটাবেসের মাধ্যমে পরিচালিত হচ্ছে নিরবচ্ছিন্ন বাংলা সাহিত্য সেবাদাতা টেলিগ্রাম বট।</p>
            <p>প্রতিদিন সকাল ১০টা, দুপুর ২টা ও রাত ১০টায় ৫০০+ শব্দের কালজয়ী সাহিত্য পৌঁছাবে আপনার ফোনে।</p>
            <a class="btn" href="https://t.me/didar_bangla_lekha_bot" target="_blank">টেলিগ্রামে বট ওপেন করুন</a>
          </div>
        </body>
        </html>
      `, { headers: { "Content-Type": "text/html; charset=utf-8" } });
    }

    // Telegram webhook handler
    if (url.pathname === "/webhook" && request.method === "POST") {
      try {
        const update = await request.json();
        await handleUpdate(update, env);
      } catch (err) {
        console.error("Webhook processing error:", err);
      }
      return new Response("OK", { status: 200 });
    }

    return new Response("Not Found", { status: 404 });
  },

  // Cron Trigger handler for daily deliveries
  async scheduled(event, env, ctx) {
    const date = new Date(event.scheduledTime);
    const utcHour = date.getUTCHours();
    
    // Asia/Dhaka is UTC+6
    // 10:00 AM BD = 04:00 UTC
    // 02:00 PM BD = 08:00 UTC
    // 10:00 PM BD = 16:00 UTC
    let slotName = "morning";
    if (utcHour >= 6 && utcHour < 12) {
      slotName = "afternoon";
    } else if (utcHour >= 12 || utcHour < 2) {
      slotName = "night";
    }

    console.log(`Cron triggered for UTC hour ${utcHour}, slot: ${slotName}`);

    if (!env.DB) {
      console.warn("D1 database binding missing");
      return;
    }

    const subs = await env.DB.prepare("SELECT chat_id, preferred_category FROM subscribers WHERE is_active = 1").all();
    const subscribers = subs.results || [];
    console.log(`Found ${subscribers.length} active subscribers`);

    for (const sub of subscribers) {
      try {
        const seenIds = await getRecentSnippetIds(env.DB, sub.chat_id, 20);
        const snippet = getLocalSnippet(sub.preferred_category || "all", slotName, null, seenIds);
        const text = formatSnippet(snippet, slotName);
        await sendTelegramMessage(env.TELEGRAM_BOT_TOKEN, sub.chat_id, text);
        await recordDelivery(env.DB, sub.chat_id, snippet.id, slotName);
        // Pacing delay
        await new Promise(r => setTimeout(r, 60));
      } catch (err) {
        console.error(`Failed to send broadcast to chat ${sub.chat_id}:`, err);
      }
    }
  }
};

async function handleUpdate(update, env) {
  const token = env.TELEGRAM_BOT_TOKEN;
  const db = env.DB;

  if (update.callback_query) {
    const cq = update.callback_query;
    const chatId = cq.message?.chat?.id;
    const data = cq.data || "";

    if (data.startsWith("cat_")) {
      const cat = data.replace("cat_", "");
      if (db) await setPreferredCategory(db, chatId, cat);
      const label = CATEGORIES[cat] || "সব ধারা";
      await answerCallbackQuery(token, cq.id, `ধারা নির্বাচিত: ${label}`);
      await sendTelegramMessage(token, chatId, `🌸 আপনার সাহিত্যের পছন্দের ধারা হিসেবে *${label}* সংরক্ষিত হয়েছে। এখন থেকে এই ধারার লেখা বেশি পাবেন!`);
      return;
    }

    if (data.startsWith("author_")) {
      const authorKey = data.replace("author_", "");
      const authorName = AUTHORS_DIRECTORY[authorKey] || authorKey;
      await answerCallbackQuery(token, cq.id, `লেখক: ${authorName}`);
      const snippet = getLocalSnippet("all", null, authorName);
      const text = formatSnippet(snippet);
      await sendTelegramMessage(token, chatId, text);
      return;
    }

    if (data === "toggle_pause") {
      if (db) await setSubscriberStatus(db, chatId, false);
      await answerCallbackQuery(token, cq.id, "প্রাত্যহিক বিতরণ স্থগিত");
      await sendTelegramMessage(token, chatId, "⏸️ আপনার প্রাত্যহিক সাহিত্য বিতরণ সাময়িকভাবে স্থগিত করা হলো। পুনরায় চালু করতে /subscribe বা /start পাঠান।");
      return;
    }

    if (data === "toggle_resume") {
      if (db) await setSubscriberStatus(db, chatId, true);
      await answerCallbackQuery(token, cq.id, "প্রাত্যহিক বিতরণ সক্রিয়");
      await sendTelegramMessage(token, chatId, "▶️ আপনার প্রাত্যহিক ৩ বেলার সাহিত্যসুধা পুনরায় সক্রিয় করা হয়েছে!");
      return;
    }

    await answerCallbackQuery(token, cq.id);
    return;
  }

  if (update.message && update.message.text) {
    const msg = update.message;
    const chatId = msg.chat.id;
    const firstName = msg.from?.first_name || "সুহৃদ";
    const username = msg.from?.username || null;
    const text = msg.text.trim();

    // Ensure subscriber is registered in D1
    if (db) await upsertSubscriber(db, chatId, firstName, username);

    const parts = text.split(/\\s+/);
    const command = parts[0].toLowerCase();
    const arg = parts.slice(1).join(" ").trim();

    if (command === "/start") {
      const welcome = `স্বাগতম, প্রিয় সুহৃদ ${firstName}! 🌸\\n\\n` +
        `বাংলা সাহিত্যের কালজয়ী ও হৃদস্পর্শী শব্দসম্ভারে আপনাকে অভিবাদন।\\n\\n` +
        `প্রতিদিন আপনার জীবনে সাহিত্যের সুর ও কাব্যিক আমেজ ছড়িয়ে দিতে আমরা প্রস্তুত। প্রতি প্রহরের বিশেষ মুহূর্তে আপনার কাছে পৌঁছে যাবে ৫০০+ শব্দের অনবদ্য সাহিত্য খণ্ড:\\n` +
        `• 🌅 সকাল ১০:০০ টা — প্রভাতী অনুপ্রেরণা ও কবিতা\\n` +
        `• ☀️ দুপুর ০২:০০ টা — উপন্যাসের টানটান দৃশ্য ও প্রেমের গল্প\\n` +
        `• 🌙 রাত ১০:০০ টা — নিশীথ প্রহর ও গভীর জীবনদর্শন\\n\\n` +
        `📜 গুরুত্বপূর্ণ কমান্ডসমূহ:\\n` +
        `/now — এখনই একটি সাহিত্য খণ্ড পড়ুন\\n` +
        `/category — পছন্দের ধারা নির্বাচন করুন\\n` +
        `/browser — প্রিয় লেখকদের তালিকা ব্রাউজ করুন\\n` +
        `/plan — প্রাত্যহিক সময়সূচি দেখুন\\n` +
        `/help — বিস্তারিত ব্যবহারবিধি`;
      
      const keyboard = {
        inline_keyboard: [
          [{ text: "📖 এখনই একটি লেখা পড়ুন", callback_data: "author_tagore" }],
          [{ text: "🏷️ ধারা পছন্দ করুন", callback_data: "cat_all" }]
        ]
      };
      await sendTelegramMessage(token, chatId, welcome, { reply_markup: keyboard });
      return;
    }

    if (command === "/now") {
      let cat = "all";
      let author = null;
      if (arg) {
        if (CATEGORIES[arg]) cat = arg;
        else author = arg;
      }
      const seen = await getRecentSnippetIds(db, chatId, 10);
      const snippet = getLocalSnippet(cat, null, author, seen);
      if (db) await recordDelivery(db, chatId, snippet.id, "now");
      const formatted = formatSnippet(snippet);
      await sendTelegramMessage(token, chatId, formatted);
      return;
    }

    if (command === "/category") {
      const catKeyboard = {
        inline_keyboard: [
          [{ text: "💖 প্রেম ও অনুরাগের গল্প", callback_data: "cat_romance" }],
          [{ text: "📖 উপন্যাসের রোমাঞ্চকর দৃশ্য", callback_data: "cat_novel" }],
          [{ text: "🔥 আগুন ও আবেগের কবিতা", callback_data: "cat_poetry" }],
          [{ text: "🌌 জীবনদর্শন ও গভীর জ্ঞান", callback_data: "cat_philosophy" }],
          [{ text: "✨ সমকালীন ও ট্রেন্ডিং", callback_data: "cat_trending" }],
          [{ text: "🌈 সমস্ত ধারা (সার্বজনীন)", callback_data: "cat_all" }]
        ]
      };
      await sendTelegramMessage(token, chatId, "🏷️ *আপনার পছন্দের সাহিত্যের ধারা নির্বাচন করুন:*\\n\\nনিচের যেকোনো একটি ধারায় ক্লিক করলে আপনার দৈনিক শিডিউল ও পাঠে সেই ধারা প্রাধান্য পাবে:", { parse_mode: "Markdown", reply_markup: catKeyboard });
      return;
    }

    if (command === "/browser" || command === "/browse") {
      const authorKeyboard = {
        inline_keyboard: [
          [{ text: "রবীন্দ্রনাথ ঠাকুর", callback_data: "author_tagore" }, { text: "কাজী নজরুল ইসলাম", callback_data: "author_nazrul" }],
          [{ text: "হুমায়ূন আহমেদ", callback_data: "author_humayun" }, { text: "সুনীল গঙ্গোপাধ্যায়", callback_data: "author_sunil" }],
          [{ text: "শীর্ষেন্দু মুখোপাধ্যায়", callback_data: "author_shirshendu" }, { text: "জীবনানন্দ দাশ", callback_data: "author_jibanananda" }],
          [{ text: "হেলাল হাফিজ", callback_data: "author_helal" }, { text: "রুদ্র মুহম্মদ শহিদুল্লাহ", callback_data: "author_rudra" }],
          [{ text: "জয় গোস্বামী", callback_data: "author_joy" }, { text: "সাদাত হোসাইন", callback_data: "author_sadat" }],
          [{ text: "🔥 সমকালীন ও ট্রেন্ডিং সাহিত্য", callback_data: "author_trending" }]
        ]
      };
      await sendTelegramMessage(token, chatId, "📚 *বাংলা সাহিত্যের প্রিয় লেখক ব্রাউজার:*\\n\\nযে লেখকের নাম স্পর্শ করবেন, তার একটি ৫০০+ শব্দের অনবদ্য সাহিত্য খণ্ড তাৎক্ষণিক আপনার সামনে উন্মোচিত হবে:", { parse_mode: "Markdown", reply_markup: authorKeyboard });
      return;
    }

    if (command === "/plan") {
      const planText = `📜 *প্রাত্যহিক সাহিত্য বিতরণের সময়সূচি (Asia/Dhaka):*\\n\\n` +
        `• 🌅 *সকাল ১০:০০ টা (প্রভাতী সাহিত্যরস):*\\n  নতুন দিনের উদ্দীপনা, স্নিগ্ধ অনুভূতি ও জাগরণী কবিতা।\\n\\n` +
        `• ☀️ *দুপুর ০২:০০ টা (মধ্যাহ্নের শব্দকাব্য):*\\n  টানটান রোমাঞ্চকর উপন্যাস ও গভীর অনুরাগের দৃশ্যপট।\\n\\n` +
        `• 🌙 *রাত ১০:০০ টা (নিশীথ ভাবনার নির্যাস):*\\n  নিস্তব্ধ প্রহরে জীবনদর্শন, একাকীত্ব ও আত্মানুসন্ধানের সাহিত্য।\\n\\n` +
        `নোট: প্রতিটি লেখা ৫০০+ শব্দের পূর্ণাঙ্গ দৃশ্য হিসেবে পরিবেশিত হয়।`;
      await sendTelegramMessage(token, chatId, planText, { parse_mode: "Markdown" });
      return;
    }

    if (command === "/learn") {
      const snippet = getLocalSnippet("philosophy", "night");
      const text = formatSnippet(snippet, "learn");
      await sendTelegramMessage(token, chatId, text);
      return;
    }

    if (command === "/boost") {
      const snippet = getLocalSnippet("poetry", "afternoon");
      const text = formatSnippet(snippet, "boost");
      await sendTelegramMessage(token, chatId, text);
      return;
    }

    if (command === "/schedule") {
      const sub = await getSubscriber(db, chatId);
      const statusText = sub && sub.is_active === 1 ? "✅ সক্রিয় (Active)" : "⏸️ স্থগিত (Paused)";
      const schedText = `⏰ *আপনার সাহিত্য সাবস্ক্রিপশন স্ট্যাটাস:*\\n\\n` +
        `বর্তমান অবস্থা: ${statusText}\\n` +
        `পছন্দের ধারা: ${CATEGORIES[sub?.preferred_category] || "সব ধারা"}\\n\\n` +
        `দৈনিক ৩ বার বিতরণ সময়সূচি:\\n` +
        `• সকাল ১০:০০ টা\\n• দুপুর ০২:০০ টা\\n• রাত ১০:০০ টা`;
      const kb = {
        inline_keyboard: [
          [{ text: sub?.is_active === 1 ? "⏸️ প্রাত্যহিক বিতরণ স্থগিত করুন" : "▶️ প্রাত্যহিক বিতরণ পুনরায় চালু করুন", callback_data: sub?.is_active === 1 ? "toggle_pause" : "toggle_resume" }]
        ]
      };
      await sendTelegramMessage(token, chatId, schedText, { parse_mode: "Markdown", reply_markup: kb });
      return;
    }

    if (command === "/subscribe") {
      if (db) await setSubscriberStatus(db, chatId, true);
      await sendTelegramMessage(token, chatId, "🌸 আপনার প্রাত্যহিক ৩ বেলার সাহিত্য বিতরণ সফলভাবে সক্রিয় করা হয়েছে। সকাল ১০টা, দুপুর ২টা ও রাত ১০টায় নতুন লেখা পৌঁছাবে।");
      return;
    }

    if (command === "/unsubscribe") {
      if (db) await setSubscriberStatus(db, chatId, false);
      await sendTelegramMessage(token, chatId, "🌿 আপনার অনুরোধে প্রাত্যহিক শিডিউল বন্ধ করা হলো। তবে যখনই মন চাইবে /now লিখে তাৎক্ষণিক সাহিত্য পড়তে পারবেন।");
      return;
    }

    if (command === "/help") {
      const helpMsg = `📖 *বাংলা সাহিত্য বট — সহায়িকা:*\\n\\n` +
        `/start — কাব্যিক স্বাগতম ও শিডিউলে যুক্ত হওয়া\\n` +
        `/now — এখনই একটি ৫০০+ শব্দের সাহিত্য খণ্ড পড়া\\n` +
        `/now <লেখক> — যেমন: /now রবীন্দ্রনাথ বা /now humayun\\n` +
        `/category — পছন্দের ধারা বেছে নেওয়া\\n` +
        `/browser — প্রিয় লেখকদের তালিকা ব্রাউজ করা\\n` +
        `/plan — ৩ প্রহরের সময়সূচি দেখা\\n` +
        `/learn — জ্ঞান ও দর্শনের নির্যাস পাঠ\\n` +
        `/boost — উদ্দীপনা ও হাইপ তোলা কবিতা\\n` +
        `/schedule — সাবস্ক্রিপশন স্ট্যাটাস ম্যানেজ করা\\n` +
        `/subscribe — পুনরায় বিতরণ চালু করা\\n` +
        `/unsubscribe — দৈনিক বিতরণ বন্ধ রাখা\\n\\n` +
        `এছাড়া সাধারণ চ্যাটে বাংলায় কথা বললে বট কাব্যিক ভঙ্গিতে উত্তর দেবে।`;
      await sendTelegramMessage(token, chatId, helpMsg, { parse_mode: "Markdown" });
      return;
    }

    // Conversational replies for non-command messages
    const replies = [
      `প্রিয় সুহৃদ ${firstName}, আপনার এই শব্দগুলো যেন নিঃশব্দ রাতের গহীনে অনুভূতির এক একটি স্নিগ্ধ ঢেউ। সাহিত্যিকের মন সর্বদা নীরব চিন্তার মাঝে সৌন্দর্য খুঁজে নেয়।`,
      `আপনার বার্তাটি পড়ে মনে হলো এক পশলা বৃষ্টি এসে ছুঁয়ে গেল হৃদয়। জীবন তো আসলে কিছু অকথিত গল্প আর আবেগের সংমিশ্রণ। একটি চমৎকার খণ্ড পড়তে /now পাঠান।`,
      `শব্দের ভেতর যে মায়া লুকিয়ে থাকে, তা কেবল সংবেদনশীল হৃদয়ই অনুভব করতে পারে। আপনার সাথে এই আলাপচারিতা এক অপূর্ব কাব্যিক দোলা তৈরি করছে।`,
      `নীরবতারও একটি নিজস্ব ভাষা আছে, যা আমরা অনেক সময় শব্দের চেয়ে বেশি অনুভব করি। আপনার কুশল কামনায় সর্বদা সাহিত্যের ছায়াতলে আছি।`
    ];
    const reply = replies[Math.floor(Math.random() * replies.length)];
    await sendTelegramMessage(token, chatId, reply);
  }
}
"""

final_worker_code = template.replace("__LITERATURE_ITEMS_JSON__", items_json)

os.makedirs("cloudflare_worker", exist_ok=True)
with open("cloudflare_worker/worker.js", "w", encoding="utf-8") as f:
    f.write(final_worker_code)

print("Created cloudflare_worker/worker.js successfully. Length:", len(final_worker_code))
