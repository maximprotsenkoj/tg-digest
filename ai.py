import json
import os
import re

from groq import AsyncGroq

client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY", ""))
MODEL = "llama-3.1-8b-instant"

SYSTEM = """Ты редактор новостного дайджеста. Анализируй посты из Telegram каналов и отбирай самые важные.

Критерии важности (высокий приоритет):
- Конкретные события, анонсы, релизы
- Числовые данные, факты, исследования
- Инсайты, нестандартные идеи
- Практически полезная информация

Игнорируй: рекламу, банальные советы, мотивационные цитаты, репосты без смысла.

Верни ТОЛЬКО JSON массив (без текста до и после), максимум 8 постов:
[
  {
    "channel": "username канала",
    "text": "первые 200 символов оригинального текста",
    "summary": "краткое резюме на русском, 2-3 предложения",
    "importance": число от 1 до 10
  }
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

    formatted = "\n\n---\n\n".join(
        f"Канал: @{p['channel']}\nДата: {p.get('date', '—')}\nТекст: {p['text']}"
        for p in posts[:60]
    )

    try:
        resp = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Посты:\n\n{formatted}"},
            ],
            temperature=0.2,
            max_tokens=2500,
        )
        raw = resp.choices[0].message.content.strip()
        result = _extract_json(raw)
        return sorted(result, key=lambda x: x.get("importance", 0), reverse=True)
    except Exception as e:
        print(f"[AI error] {e}")
        return []
