import aiohttp
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TGDigestBot/1.0)"}
TIMEOUT = aiohttp.ClientTimeout(total=12)


async def fetch_channel_posts(channel: str, limit: int = 20) -> list[dict]:
    url = f"https://t.me/s/{channel}"
    try:
        async with aiohttp.ClientSession(headers=HEADERS, timeout=TIMEOUT) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()
    except Exception:
        return []

    soup = BeautifulSoup(html, "html.parser")
    bubbles = soup.find_all("div", class_="tgme_widget_message_bubble")

    posts = []
    for bubble in bubbles[-limit:]:
        text_el = bubble.find("div", class_="tgme_widget_message_text")
        time_el = bubble.find("time")

        if not text_el:
            continue

        text = text_el.get_text(separator=" ", strip=True)
        if len(text) < 40:
            continue

        posts.append({
            "text": text[:700],
            "date": time_el.get("datetime", "") if time_el else "",
        })

    return posts
