"""
routers/news.py - Nyheder proxy (DR RSS)
"""
import xml.etree.ElementTree as ET

import requests as req
from fastapi import APIRouter, HTTPException

router = APIRouter()

DR_FEEDS = {
    "dr":    "https://www.dr.dk/nyheder/service/feeds/allenyheder",
    "sport": "https://www.dr.dk/nyheder/service/feeds/sporten",
}

NS = {"media": "http://search.yahoo.com/mrss/"}


@router.get("/api/news/{feed}")
def get_news(feed: str, limit: int = 15):
    url = DR_FEEDS.get(feed)
    if not url:
        raise HTTPException(status_code=404, detail="Ukendt feed")
    try:
        r = req.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    root = ET.fromstring(r.content)
    items = []
    for item in root.findall(".//item")[:limit]:
        title = item.findtext("title", "")
        link  = item.findtext("link", "")
        pub   = item.findtext("pubDate", "")
        img = ""
        # DR bruger media:content (ikke media:thumbnail)
        for tag in ("media:content", "media:thumbnail"):
            el = item.find(tag, NS)
            if el is not None:
                img = el.get("url", "")
                if img:
                    break
        if not img:
            enc = item.find("enclosure")
            if enc is not None:
                u = enc.get("url", "")
                if enc.get("type", "").startswith("image") or u.endswith((".jpg", ".png", ".webp")):
                    img = u
        items.append({"title": title, "link": link, "date": pub, "img": img})

    return items
