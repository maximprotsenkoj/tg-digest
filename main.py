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
from db import add_channel, get_channels, init_db, remove_channel
from parser import fetch_channel_posts

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
DB_PATH = os.getenv("DB_PATH", "digest.db")

bot_app = Application.builder().token(BOT_TOKEN).build()


# ── Lifecycle ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(DB_PATH)
    await bot_app.initialize()
    await bot_app.start()
    if WEBAPP_URL:
        await bot_app.bot.set_webhook(f"{WEBAPP_URL}/webhook")
        print(f"Webhook set: {WEBAPP_URL}/webhook")
    else:
        print("WEBAPP_URL not set — running without webhook (use polling locally)")
    yield
    await bot_app.bot.delete_webhook()
    await bot_app.stop()
    await bot_app.shutdown()


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
    channels = await get_channels(DB_PATH, user["id"])
    return {"channels": channels}


@app.post("/api/channels")
async def api_add_channel(request: Request):
    user = get_user(request)
    body = await request.json()
    username = body.get("username", "").strip().lstrip("@").lower()
    if not username or len(username) > 32 or not all(c.isalnum() or c in "_-" for c in username):
        raise HTTPException(status_code=400, detail="Invalid channel username")
    existing = await get_channels(DB_PATH, user["id"])
    if len(existing) >= 20:
        raise HTTPException(status_code=400, detail="Максимум 20 каналов")
    await add_channel(DB_PATH, user["id"], username)
    return {"ok": True}


@app.delete("/api/channels/{username}")
async def api_remove_channel(username: str, request: Request):
    user = get_user(request)
    await remove_channel(DB_PATH, user["id"], username)
    return {"ok": True}


@app.post("/api/digest")
async def api_digest(request: Request):
    user = get_user(request)
    channels = await get_channels(DB_PATH, user["id"])
    if not channels:
        return {"posts": [], "hint": "no_channels"}

    all_posts: list[dict] = []
    failed: list[str] = []
    for ch in channels:
        posts = await fetch_channel_posts(ch, limit=20)
        if posts:
            for p in posts:
                p["channel"] = ch
            all_posts.extend(posts)
        else:
            failed.append(ch)

    if not all_posts:
        return {"posts": [], "hint": "no_posts", "failed": failed}

    digest = await get_digest(all_posts)
    return {"posts": digest, "failed": failed}


# ── Bot handlers ─────────────────────────────────────────────────────────────

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


# ── Frontend (последним — ловит всё остальное) ────────────────────────────────

app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
