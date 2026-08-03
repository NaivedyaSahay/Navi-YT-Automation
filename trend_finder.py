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
    # Facts & Curiosity
    "todayilearned", "interestingasfuck", "explainlikeimfive", "Showerthoughts",
    # Tech & Space
    "technology", "space", "Futurology", "IndiaTech",
    # Oceans & Biology / Human Body
    "ocean", "biology",
    # Movies & Cinema
    "MovieDetails", "CinemaDetails", "history",
    # Psychology & Motivation
    "psychology", "decidingtobetter", "getdisciplined", "motivation",
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
    r"\b(why|how|what|when|facts|fact|tech|technology|space|ocean|oceans|movie|movies|film|cinema|body|brain|human|psychology|mind|mindset|motivation|story|stories|history|secret|secrets|mystery|mysteries|science|future|truth|proven|lesson|lessons|success)\b",
]

# Fallback topics across Tech, Space, Oceans, Movies, Human Body, Psychology, Motivation & Stories
EVERGREEN_TOPICS = [
    # Tech & AI
    "Mind-blowing artificial intelligence facts that sound like sci-fi",
    "How quantum computers will completely change the future of technology",
    # Space & Universe
    "Unbelievable space facts that will expand your mind",
    "The terrifying mystery of supermassive black holes in deep space",
    # Oceans & Deep Sea
    "Mysterious deep ocean creatures humans barely know exist",
    "What lies at the bottom of the Mariana Trench?",
    # Movies & Cinema
    "Hidden movie details and secret facts you completely missed",
    "Crazy behind-the-scenes cinema facts that changed movie history",
    # Human Body & Health
    "Crazy facts about the human body you were never taught in school",
    "How your brain processes memories while you sleep",
    # Psychology & Mindset
    "Powerful psychological tricks that explain human behavior",
    "Why your brain falls for cognitive illusions every single day",
    # Motivation & Personal Growth
    "The 1% mindset rule that transforms your discipline and life",
    "Lessons from stoicism that help you master emotional control",
    # Incredible Stories & Mysteries
    "Ancient historical secrets and unsolved mysteries science cannot explain",
    "Unbelievable true stories of survival against all odds",
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


# ── Categorized Curiosity & Facts Library ────────────────────────────────────

CATEGORIZED_TOPICS = {
    "Space & Universe": [
        "What happens if you step inside a supermassive black hole?",
        "Mind-blowing space facts about neutron stars that defy physics",
        "The mysterious discoveries rewriting our understanding of space",
        "How big is the observable universe compared to planet Earth?",
        "Why space is completely silent and freezing cold",
        "The terrifying concept of a rogue planet drifting through deep space",
    ],
    "Oceans & Deep Sea": [
        "Creepy deep ocean creatures humans barely know exist",
        "What lies at the bottom of the Mariana Trench 36,000 feet down?",
        "Why 80% of the Earth's oceans remain completely unexplored",
        "The bizarre bioluminescent creatures living in total ocean darkness",
        "Fascinating facts about the immortal jellyfish that never dies",
    ],
    "Tech & Artificial Intelligence": [
        "Mind-blowing AI advancements coming in the next 5 years",
        "How quantum computers will completely change the future of tech",
        "Crazy future technology concepts that already exist today",
        "How microchips are manufactured at the sub-nanometer scale",
        "The terrifying evolution of humanoid robotics",
    ],
    "Movies & Cinema Details": [
        "Hidden movie details and secret Easter eggs you completely missed",
        "Crazy behind-the-scenes cinema facts that changed movie history",
        "How movie sound designers create terrifying alien and monster sounds",
        "Mind-blowing movie props that were actually real objects",
    ],
    "Human Body & Brain": [
        "Crazy human body facts you were never taught in biology class",
        "How your brain rewires itself every single night while you sleep",
        "Why your brain creates fake memories without you knowing",
        "Fascinating biological superpowers of the human immune system",
        "The science behind why goosebumps happen when listening to music",
    ],
    "Psychology & Human Behavior": [
        "Powerful psychological tricks that explain human behavior",
        "Why your brain falls for cognitive bias illusions every single day",
        "The psychological reason why people procrastinate on important goals",
        "How body language reveals what someone is secretly thinking",
        "The Spotlight Effect: Why nobody is actually watching your mistakes",
    ],
    "Motivation & Mindset": [
        "The 1% mindset rule that transforms your discipline and life",
        "Lessons from ancient stoicism that build mental toughness",
        "Why motivation is temporary but daily habits create success",
        "How high performers train their focus and eliminate distractions",
        "The psychological power of adopting a growth mindset",
    ],
    "Incredible Stories & Mysteries": [
        "Ancient historical secrets and unsolved mysteries science cannot explain",
        "Unbelievable true stories of human survival against impossible odds",
        "The mysterious lost civilizations that vanished without a trace",
        "Fascinating historical coincidences that sound completely fake",
    ],
}


def _get_curated_topics(n: int = 10) -> list[dict]:
    """Pick diverse topics across all requested categories."""
    import random
    selected = []
    categories = list(CATEGORIZED_TOPICS.keys())
    random.shuffle(categories)

    for cat in categories:
        topics_list = CATEGORIZED_TOPICS[cat]
        topic_text = random.choice(topics_list)
        selected.append({
            "topic": topic_text,
            "source": f"Facts & Curiosity ({cat})",
            "score": 1.8,
        })
        if len(selected) >= n:
            break
    return selected


# ── Source: Reddit Curiosity & Facts ──────────────────────────────────────────

def _get_reddit_trending(n: int = 15) -> list[dict]:
    """
    Pull hot posts from educational and curiosity subreddits via public JSON API.
    No news, no politics.
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

            time.sleep(0.3)
        except Exception as exc:
            logger.debug("Reddit r/%s failed: %s", sub, exc)

    topics.sort(key=lambda x: x["score"], reverse=True)
    logger.info("Reddit: found %d curiosity topics", len(topics))
    return topics[:n]


# ── Public API ────────────────────────────────────────────────────────────────

def get_trending_topics(n: int = 5, region: str = "IN") -> list[dict]:
    """
    Fetch curiosity, facts, psychology, space, oceans, movies, motivation,
    and story topics. Zero news channels or political content.

    Returns list of up to *n* dicts: {"topic", "source", "score"}
    """
    logger.info("Discovering facts, curiosity & educational topics…")

    reddit = _get_reddit_trending(n=10)
    curated = _get_curated_topics(n=10)

    combined = reddit + curated
    combined.sort(key=lambda x: x["score"], reverse=True)
    result = _dedupe(combined, n)

    if not result:
        result = _get_curated_topics(n)

    logger.info("Top %d curiosity topics selected:", len(result))
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
