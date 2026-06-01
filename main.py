import asyncio
import hashlib
import hmac
import json
import os
from contextlib import asynccontextmanager
from urllib.parse import parse_qsl

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

from ai import get_digest
from db import add_channel, close_db, get_channels, init_db, remove_channel, upsert_user
from parser import fetch_channel_info, fetch_channel_posts

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")

bot_app = Application.builder().token(BOT_TOKEN).build()


# ── Lifecycle ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await bot_app.initialize()
    await bot_app.start()
    if WEBAPP_URL:
        await bot_app.bot.set_webhook(f"{WEBAPP_URL}/webhook")
        print(f"Webhook set: {WEBAPP_URL}/webhook")
    else:
        print("WEBAPP_URL not set — running without webhook")
    yield
    await bot_app.bot.delete_webhook()
    await bot_app.stop()
    await bot_app.shutdown()
    await close_db()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth ─────────────────────────────────────────────────────────────────────

def verify_init_data(init_data: str) -> dict | None:
    if not init_data:
        return None
    params = dict(parse_qsl(init_data, keep_blank_values=True))
    hash_value = params.pop("hash", None)
    if not hash_value:
        return None
    data_check = "\n".join(f"{k}={params[k]}" for k in sorted(params.keys()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
    if hmac.compare_digest(computed, hash_value):
        return json.loads(params.get("user", "{}"))
    return None


def get_user(request: Request) -> dict:
    init_data = request.headers.get("X-Init-Data", "")
    user = verify_init_data(init_data)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user


# ── API ──────────────────────────────────────────────────────────────────────

@app.get("/api/channels")
async def api_get_channels(request: Request):
    user = get_user(request)
    channels = await get_channels(user["id"])
    return {"channels": channels}


@app.post("/api/channels")
async def api_add_channel(request: Request):
    user = get_user(request)
    body = await request.json()
    username = body.get("username", "").strip().lstrip("@").lower()
    if not username or len(username) > 32 or not all(c.isalnum() or c in "_-" for c in username):
        raise HTTPException(status_code=400, detail="Invalid channel username")
    existing = await get_channels(user["id"])
    if len(existing) >= 20:
        raise HTTPException(status_code=400, detail="Максимум 20 каналов")
    await upsert_user(user["id"], user.get("username"), user.get("first_name"))
    await add_channel(user["id"], username)
    return {"ok": True}


@app.delete("/api/channels/{username}")
async def api_remove_channel(username: str, request: Request):
    user = get_user(request)
    await remove_channel(user["id"], username)
    return {"ok": True}


@app.get("/api/channel-info/{username}")
async def api_channel_info(username: str):
    info = await fetch_channel_info(username)
    return info


@app.get("/api/gemini-models")
async def api_gemini_models():
    import aiohttp, os
    key = os.getenv("GEMINI_API_KEY", "")
    async with aiohttp.ClientSession() as s:
        async with s.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        ) as r:
            data = await r.json()
    models = [m["name"] for m in data.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
    return {"models": models}


@app.post("/api/digest")
async def api_digest(request: Request):
    import traceback
    user = get_user(request)

    try:
        body = await request.json()
        hours = max(1, min(int(body.get("hours", 24)), 168))
    except Exception:
        hours = 24

    try:
        channels = await get_channels(user["id"])
        if not channels:
            return {"posts": [], "hint": "no_channels"}

        tasks = [fetch_channel_posts(ch, limit=20, hours=hours) for ch in channels]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_posts: list[dict] = []
        failed: list[str] = []
        for ch, result in zip(channels, results):
            if isinstance(result, Exception) or not result:
                print(f"[fetch failed] {ch}: {result}")
                failed.append(ch)
            else:
                for p in result:
                    p["channel"] = ch
                all_posts.extend(result)

        print(f"[digest] user={user['id']} channels={channels} posts={len(all_posts)} failed={failed}")

        if not all_posts:
            return {"posts": [], "hint": "no_posts", "failed": failed}

        # Build media lookup before passing to AI (AI doesn't handle media)
        media_lookup: dict[tuple, dict] = {}
        for p in all_posts:
            if p.get("media"):
                key = (p["channel"], p["text"][:60])
                media_lookup[key] = p["media"]

        digest = await get_digest(all_posts)

        # Merge media back into digest items
        for item in digest:
            key = (item.get("channel", ""), item.get("text", "")[:60])
            if key in media_lookup:
                item["media"] = media_lookup[key]

        return {"posts": digest, "failed": failed}
    except Exception as e:
        print(f"[digest error] {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Bot ──────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📰 Открыть дайджест", web_app=WebAppInfo(url=WEBAPP_URL))
    ]])
    await update.message.reply_text(
        "👋 Привет! Я собираю AI-дайджест из Telegram каналов.\n\n"
        "Добавь каналы → получай только важные новости, отфильтрованные ИИ.",
        reply_markup=kb,
    )

bot_app.add_handler(CommandHandler("start", cmd_start))


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return {"ok": True}


# ── Frontend ─────────────────────────────────────────────────────────────────

app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
