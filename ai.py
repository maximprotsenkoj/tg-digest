import json
import os
import re

import aiohttp
from json_repair import repair_json

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

TAGS = [
    "ИИ", "Технологии", "Крипто", "Финансы", "Политика",
    "Бизнес", "Стартапы", "Наука", "Здоровье", "Образование",
    "Маркетинг", "Право", "Спорт", "Культура", "Медиа",
    "Безопасность", "Энергетика", "Климат", "Транспорт",
    "Недвижимость", "E-commerce", "Космос", "Биотех", "Игры",
    "Кино", "Карьера", "Экономика", "Регуляции", "Соцсети", "Дизайн",
]

_SYSTEM = f"""Редактор дайджеста. Выбери до 10 важных постов.

Важность (строго):
9-10 → катастрофы, войны, революционные открытия
7-8  → крупные законы, IPO, банкротства, исследования с цифрами
5-6  → полезные инсайты, значимые тренды с конкретикой
1-4  → мнения, советы, реклама, мотивация — сюда большинство постов

Не завышай. Реклама и банальщина = 1-2.
Теги: {", ".join(TAGS)}

Ответ — только JSON массив:
[{{"channel":"","text":"","link":"","summary":"2-3 предложения на русском","importance":0,"tags":[]}}]"""


async def get_digest(posts: list[dict]) -> list[dict]:
    if not posts:
        return []

    link_lookup = {p["text"][:60]: p.get("link", "") for p in posts}

    formatted = "\n---\n".join(
        f"@{p['channel']}: {p['text']}"
        for p in posts
    )

    # Rebuild URL each call so GEMINI_MODEL env var is respected
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

    payload = {
        "systemInstruction": {          # camelCase — обязательно для REST API
            "parts": [{"text": _SYSTEM}]
        },
        "contents": [{"role": "user", "parts": [{"text": f"Посты:\n{formatted}"}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
        },
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{url}?key={GEMINI_API_KEY}",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    print(f"[AI error] {resp.status} model={GEMINI_MODEL}: {err[:500]}")
                    return []

                data = await resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                result = json.loads(repair_json(text))

        if not isinstance(result, list):
            return []

        for item in result:
            if not isinstance(item, dict):
                continue
            if not item.get("link"):
                item["link"] = link_lookup.get(item.get("text", "")[:60], "")
            if not isinstance(item.get("tags"), list):
                item["tags"] = []

        return sorted(result, key=lambda x: x.get("importance", 0), reverse=True)

    except Exception as e:
        print(f"[AI error] {e}")
        return []
