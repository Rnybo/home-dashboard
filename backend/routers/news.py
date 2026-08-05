"""
routers/news.py - Nyheder proxy (DR RSS) + artikel-udtræk
"""
import urllib.parse
import xml.etree.ElementTree as ET

import requests as req
from bs4 import BeautifulSoup
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


@router.get("/api/article-extract")
def article_extract(url: str = ""):
    """
    Henter en DR-artikel server-side og udtrækker den læsbare tekst, så
    frontend kan vise den direkte i en modal — uden iframe (DR sender
    X-Frame-Options der blokerer indlejring) og uden window.open (Fully
    Kiosk Browser understøtter ikke nye faner).
    """
    if not url:
        raise HTTPException(400, "url required")
    parsed = urllib.parse.urlparse(url)
    if not parsed.netloc.endswith("dr.dk"):
        raise HTTPException(403, "Kun dr.dk-URLs er tilladt")
    try:
        r = req.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as e:
        raise HTTPException(502, f"Kunne ikke hente artikel: {e}")

    soup = BeautifulSoup(r.content, "html.parser")

    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else (soup.title.get_text(strip=True) if soup.title else "")

    # DR markerer selve brødteksten med schema.org's articleBody — mere
    # pålideligt end at gætte på CSS-klassenavne, som ændrer sig ved redesign.
    content = soup.find(attrs={"itemprop": "articleBody"})
    if not content and h1:
        content = h1.find_parent("article")
    if not content:
        content = soup.find("main") or soup.find("article") or soup.body
    if not content:
        raise HTTPException(502, "Kunne ikke finde artikelindhold")

    # Fjern scripts/navigation/reklamer/formularer — vi vil kun have læsbar
    # tekst, og vil undgå at DR's JS kan forsøge at "frame-buste" ud af vores
    # visning eller indlæse tracking/reklamer.
    for tag in content.find_all(["script", "style", "nav", "header", "footer", "form", "iframe", "button", "aside"]):
        tag.decompose()

    # Absolute URLs for billeder og links, og fjern inline event-handlers
    for img in content.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if src:
            img["src"] = urllib.parse.urljoin(url, src)
        for attr in ("srcset", "data-srcset", "sizes"):
            if img.has_attr(attr):
                del img[attr]
    for a in content.find_all("a"):
        href = a.get("href")
        if href:
            a["href"] = urllib.parse.urljoin(url, href)
    for tag in content.find_all(True):
        for attr in list(tag.attrs):
            if attr.lower().startswith("on"):
                del tag[attr]

    return {"title": title, "html": str(content), "source_url": url}
