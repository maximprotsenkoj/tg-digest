import json
import os
import re

from groq import AsyncGroq

client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY", ""))
MODEL = "llama-3.1-8b-instant"

TAGS = [
    "ИИ", "Технологии", "Крипто", "Финансы", "Политика",
    "Бизнес", "Стартапы", "Наука", "Здоровье", "Образование",
    "Маркетинг", "Право", "Спорт", "Культура", "Медиа",
    "Безопасность", "Энергетика", "Климат", "Транспорт",
    "Недвижимость", "E-commerce", "Космос", "Биотех", "Игры",
    "Кино", "Карьера", "Экономика", "Регуляции", "Соцсети", "Дизайн",
]

SYSTEM = f"""Ты редактор новостного дайджеста. Оцени важность каждого поста строго по шкале.

ШКАЛА ВАЖНОСТИ — соблюдай точно:
9-10 → Катастрофы, войны, гибель людей, глобальный финансовый кризис, революционные открытия
7-8  → Крупные законы/санкции, IPO >$500M, банкротства известных компаний, важные исследования с цифрами
5-6  → Значимые корпоративные события, полезные инсайты с конкретикой, интересные тренды
3-4  → Общая информация, комментарии, несрочно
1-2  → Реклама, мотивация, банальные советы, опросы, репосты без смысла

СТРОГО: не давай 6+ за мнения без фактов, советы, цитаты, рекламу. Большинство постов должны получать 3-5.

Доступные теги: {", ".join(TAGS)}
Выбирай 1-2 наиболее точных тега.

Верни ТОЛЬКО JSON массив (никакого текста вокруг), до 15 лучших постов:
[
  {{
    "channel": "username канала",
    "text": "первые 200 символов оригинала",
    "link": "ссылка на пост",
    "summary": "краткое резюме на русском, 2-3 предложения с фактами",
    "importance": число 1-10,
    "tags": ["тег1", "тег2"]
  }}
]"""


def _extract_json(text: str) -> list:
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return []


async def get_digest(posts: list[dict]) -> list[dict]:
    if not posts:
        return []

    posts_to_process = posts[:40]

    # Build link lookup from original posts by text prefix
    link_lookup: dict[str, str] = {}
    for p in posts_to_process:
        key = p["text"][:60]
        link_lookup[key] = p.get("link", "")

    formatted = "\n\n---\n\n".join(
        f"Канал: @{p['channel']}\nДата: {p.get('date', '—')}\nТекст: {p['text'][:400]}"
        for p in posts_to_process
    )

    try:
        resp = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Посты для анализа:\n\n{formatted}"},
            ],
            temperature=0.2,
            max_tokens=3000,
        )
        raw = resp.choices[0].message.content.strip()
        result = _extract_json(raw)

        for item in result:
            if not item.get("link"):
                key = item.get("text", "")[:60]
                item["link"] = link_lookup.get(key, "")
            if not isinstance(item.get("tags"), list):
                item["tags"] = []

        return sorted(result, key=lambda x: x.get("importance", 0), reverse=True)
    except Exception as e:
        print(f"[AI error] {e}")
        return []
