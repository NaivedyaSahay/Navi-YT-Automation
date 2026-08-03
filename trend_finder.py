"""
trend_finder.py
---------------
Discovers trending topics from multiple free sources:
  1. Google Trends RSS feed   (no API key, no library quirks)
  2. Google News RSS feed     (always-fresh headlines)
  3. Reddit public JSON       (no API key needed)
  4. Evergreen fallback list  (if all sources fail)

Public API:
    topics = get_trending_topics(n=5, region="IN")
    # Returns list of {"topic": str, "source": str, "score": float}
"""

from __future__ import annotations

import logging
import re
import time
import xml.etree.ElementTree as ET
from typing import Optional

import requests

logger = logging.getLogger("trend_finder")

# ── Configuration ─────────────────────────────────────────────────────────────

REDDIT_SUBS = [
    "india", "IndiaTech", "technology", "science", "philosophy",
    "Futurology", "space", "psychology", "history",
    "explainlikeimfive", "todayilearned", "interestingasfuck",
]

BAD_KEYWORDS = [
    "porn", "nsfw", "sex", "nude", "leaked", "xxx",
    "killed", "murder", "shooting", "arrested",
]

POLITICAL_KEYWORDS = [
    "bjp", "congress", "aap", "tmc", "dmk", "admk", "bsp", "sp", "cpi", "ncp",
    "modi", "narendra modi", "rahul gandhi", "kejriwal", "shah", "amit shah",
    "yogi", "mamata", "stalin", "pawar", "sitharaman", "jaishankar", "kharge",
    "minister", "prime minister", "chief minister", "pm", "cm", "parliament",
    "lok sabha", "rajya sabha", "assembly", "governor", "president", "mp", "mla",
    "election", "elections", "poll", "polls", "voting", "voter", "campaign",
    "party", "government", "govt", "cabinet", "bypoll", "nomination", "politician",
    "politics", "political", "protest", "rally", "strike", "scam", "corruption",
    "bribe", "bill", "supreme court", "high court", "verdict", "petition", "fir",
    "cbi", "ed", "income tax", "sanction", "war", "military", "border", "ceasefire",
    "jem", "isi", "terrorist", "terrorism", "terror", "spy", "spying", "execute",
    "executes", "execution", "defense", "missile", "airstrike", "conflict", "geopolitics",
]

# Topic patterns that make bad YouTube Shorts
BAD_PATTERNS = [
    r"^\d+\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",  # dates
    r"\b\d{1,2}\s+\w+\s+\d{4}\b",   # "3 august 2026"
    r"\bvs\.?\b",                    # sports matches: "liverpool vs leeds"
    r"^\w+\s+\d{3,}",               # product model: "ktm 390"
    r"\b(ebony|black|white|red|blue)\b.{0,20}(edition|color|colour)\b",  # product colors
    r"^[A-Z][a-z]+\s+[A-Z][a-z]+$",  # Just two capitalised words = person name
]

GOOD_PATTERNS = [
    r"\b(why|how|what|when|the|science|world|life|mind|ai|space|history|future|truth|secret|power|success|health|psychology|facts|mystery|hidden|proven|reason|surprising)\b",
]

# Fallback topics if all sources fail — always good for Shorts
EVERGREEN_TOPICS = [
    "The most mind-blowing facts about the universe",
    "Why your brain lies to you every day",
    "The psychology of success nobody talks about",
    "Ancient secrets that changed the world",
    "How artificial intelligence will change your life",
    "The science behind why we dream",
    "Habits of the world's most successful people",
    "The hidden power of stoicism",
    "Why most people never achieve their goals",
    "The most fascinating unsolved mysteries in science",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)              # strip HTML tags
    text = re.sub(r"\[.*?\]|\(.*?\)", "", text)       # strip [tags] (notes)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:120]


def _is_suitable(title: str) -> bool:
    if not title or len(title) < 12:
        return False
    t = title.lower()

    # Reject adult / NSFW / violence
    if any(b in t for b in BAD_KEYWORDS):
        return False

    # Reject all political terms, figures, parties, elections, and government news
    words = set(re.findall(r"\w+", t))
    for pol in POLITICAL_KEYWORDS:
        if " " in pol:
            if pol in t:
                return False
        else:
            if pol in words:
                return False

    if len(title.split()) < 4:   # need at least 4 words
        return False
    for pat in BAD_PATTERNS:
        if re.search(pat, title, re.IGNORECASE):
            return False
    return True


def _has_educational_value(title: str) -> bool:
    """Bonus: does this topic have strong educational/viral potential?"""
    t = title.lower()
    return any(re.search(p, t) for p in GOOD_PATTERNS)


def _dedupe(topics: list[dict], max_n: int) -> list[dict]:
    seen, out = set(), []
    for t in topics:
        key = t["topic"][:35].lower()
        if key not in seen:
            seen.add(key)
            out.append(t)
        if len(out) >= max_n:
            break
    return out


# ── Source 1: Google Trends via RSS ──────────────────────────────────────────

def _get_google_trends_rss(region: str = "IN", n: int = 15) -> list[dict]:
    """
    Fetch daily trending searches from Google Trends RSS feed.
    No API key, no pytrends — just a plain RSS request.
    """
    url = f"https://trends.google.com/trending/rss?geo={region.upper()}"
    headers = {"User-Agent": "NaviBot/1.0 (YouTube Shorts Automation)"}
    topics = []
    try:
        resp = requests.get(url, headers=headers, timeout=12)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns   = {"ht": "https://trends.google.com/trending/rss"}
        items = root.findall(".//item")
        for item in items[:n]:
            title_el = item.find("title")
            title    = _clean(title_el.text or "") if title_el is not None else ""
            if _is_suitable(title):
                bonus = 0.3 if _has_educational_value(title) else 0.0
                topics.append({
                    "topic":  title,
                    "source": "Google Trends",
                    "score":  1.0 + bonus,
                })
        logger.info("Google Trends RSS: found %d topics", len(topics))
    except Exception as exc:
        logger.warning("Google Trends RSS failed: %s", exc)
    return topics


# ── Source 2: Google News RSS ─────────────────────────────────────────────────

def _get_google_news_rss(n: int = 10) -> list[dict]:
    """
    Pull trending headlines from Google News RSS feed.
    Great for factual / educational Shorts topics.
    """
    url     = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
    headers = {"User-Agent": "NaviBot/1.0 (YouTube Shorts Automation)"}
    topics  = []
    try:
        resp = requests.get(url, headers=headers, timeout=12)
        resp.raise_for_status()
        root  = ET.fromstring(resp.content)
        items = root.findall(".//item")
        for item in items[:n * 2]:   # fetch extra, we'll filter
            title_el = item.find("title")
            title    = _clean(title_el.text or "") if title_el is not None else ""
            # Strip publisher suffix " - CNN" etc.
            title = re.sub(r"\s+-\s+\S+.*$", "", title).strip()
            if _is_suitable(title):
                bonus = 0.4 if _has_educational_value(title) else 0.0
                topics.append({
                    "topic":  title,
                    "source": "Google News",
                    "score":  1.4 + bonus,   # News gets high priority
                })
        logger.info("Google News RSS: found %d topics", len(topics))
    except Exception as exc:
        logger.warning("Google News RSS failed: %s", exc)
    return topics[:n]


# ── Source 3: Reddit public JSON ──────────────────────────────────────────────

def _get_reddit_trending(n: int = 15) -> list[dict]:
    """
    Pull hot posts from educational subreddits via public JSON API.
    No API key required.
    """
    headers = {"User-Agent": "NaviBot/1.0 (YouTube Shorts Automation)"}
    topics  = []

    for sub in REDDIT_SUBS:
        try:
            url  = f"https://www.reddit.com/r/{sub}/hot.json?limit=8"
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            posts = resp.json()["data"]["children"]

            for post in posts:
                d     = post["data"]
                if d.get("stickied"):
                    continue
                title = _clean(d.get("title", ""))
                score = d.get("score", 0)
                if _is_suitable(title) and score > 50:
                    bonus = 0.3 if _has_educational_value(title) else 0.0
                    topics.append({
                        "topic":  title,
                        "source": f"Reddit r/{sub}",
                        "score":  min(score / 10000, 1.0) + bonus,
                    })

            time.sleep(0.4)   # be polite
        except Exception as exc:
            logger.debug("Reddit r/%s failed: %s", sub, exc)

    topics.sort(key=lambda x: x["score"], reverse=True)
    logger.info("Reddit: found %d topics (before dedup)", len(topics))
    return topics[:n]


# ── Fallback: evergreen topics ────────────────────────────────────────────────

def _get_evergreen(n: int = 5) -> list[dict]:
    import random
    chosen = random.sample(EVERGREEN_TOPICS, min(n, len(EVERGREEN_TOPICS)))
    return [{"topic": t, "source": "Evergreen", "score": 0.5} for t in chosen]


# ── Public API ────────────────────────────────────────────────────────────────

def get_trending_topics(n: int = 5, region: str = "IN") -> list[dict]:
    """
    Fetch and rank trending topics from Google Trends + Google News + Reddit.
    Falls back to evergreen topics if all live sources fail.

    Returns list of up to *n* dicts: {"topic", "source", "score"}
    """
    logger.info("Fetching trends (region=%s)…", region)

    trends = _get_google_trends_rss(region=region, n=15)
    news   = _get_google_news_rss(n=10)
    reddit = _get_reddit_trending(n=20)

    combined = trends + news + reddit
    combined.sort(key=lambda x: x["score"], reverse=True)
    result = _dedupe(combined, n)

    if not result:
        logger.warning("All live sources failed — using evergreen fallback topics.")
        result = _get_evergreen(n)

    logger.info("Top %d topics selected:", len(result))
    for i, t in enumerate(result, 1):
        logger.info("  %d. [%s] %s", i, t["source"], t["topic"])

    return result


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    # Force UTF-8 for Windows terminal
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    region = sys.argv[1] if len(sys.argv) > 1 else "IN"
    topics = get_trending_topics(n=5, region=region)
    print("\nTop Trending Topics:")
    for i, t in enumerate(topics, 1):
        print(f"  {i}. {t['topic']}")
        print(f"     Source: {t['source']} (score={t['score']:.2f})")
