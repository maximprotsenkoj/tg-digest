import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TGDigestBot/1.0)"}
TIMEOUT = aiohttp.ClientTimeout(total=12)


async def fetch_channel_info(channel: str) -> dict:
    url = f"https://t.me/s/{channel}"
    try:
        async with aiohttp.ClientSession(headers=HEADERS, timeout=TIMEOUT) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return {"title": channel, "avatar": ""}
                html = await resp.text()
    except Exception:
        return {"title": channel, "avatar": ""}

    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.find("meta", property="og:title")
    image_el = soup.find("meta", property="og:image")

    return {
        "title": title_el.get("content", channel) if title_el else channel,
        "avatar": image_el.get("content", "") if image_el else "",
    }


async def fetch_channel_posts(channel: str, limit: int = 20, hours: int = 24) -> list[dict]:
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

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    posts = []

    for bubble in bubbles[-limit:]:
        text_el = bubble.find("div", class_="tgme_widget_message_text")
        date_link = bubble.find("a", class_="tgme_widget_message_date")
        time_el = date_link.find("time") if date_link else None

        if not text_el:
            continue

        text = text_el.get_text(separator=" ", strip=True)
        if len(text) < 40:
            continue

        date_str = time_el.get("datetime", "") if time_el else ""
        post_link = date_link.get("href", "") if date_link else ""

        if date_str:
            try:
                dt = datetime.fromisoformat(date_str)
                if dt < cutoff:
                    continue
            except Exception:
                pass

        posts.append({
            "text": text[:500],
            "date": date_str,
            "link": post_link,
        })

    return posts
