import json
import os

import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))

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

_model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=genai.GenerationConfig(
        temperature=0.2,
        max_output_tokens=1200,
        response_mime_type="application/json",
    ),
    system_instruction=_SYSTEM,
)


async def get_digest(posts: list[dict]) -> list[dict]:
    if not posts:
        return []

    link_lookup = {p["text"][:60]: p.get("link", "") for p in posts}

    # Компактный формат — без дат, текст 200 символов
    formatted = "\n---\n".join(
        f"@{p['channel']}: {p['text'][:200]}"
        for p in posts[:25]
    )

    try:
        response = await _model.generate_content_async(f"Посты:\n{formatted}")
        result = json.loads(response.text)

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
