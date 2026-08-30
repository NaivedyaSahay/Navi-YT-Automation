"""
script_generator.py
-------------------
Generates structured video scripts for YouTube Shorts (v2 — Quote/Motivational edition).

Model priority chain (automatic fallback):
  1. Groq: groq/compound
  2. Groq: llama-3.1-8b-instant  (reliable free-tier fallback)
  3. Groq: openai/gpt-oss-120b
  4. Gemini: gemini-2.0-flash  (if GEMINI_API_KEY is set)
  5. Curated offline script

Returns a dict with keys:
    script      - voiceover text (150-250 words, 45-60 second Short)
    title       - YouTube video title (<= 100 chars)
    description - YouTube video description (<= 500 chars)
    tags        - list[str] of relevant tags (up to 15)
    keywords    - list[str] of stock-footage search terms
"""

import json
import logging
import os
import re
import textwrap

from groq import Groq
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("script_generator")

# ── Model Priority List ───────────────────────────────────────────────────────
GROQ_MODELS = [
    os.getenv("GROQ_MODEL", "groq/compound"),
    "llama-3.1-8b-instant",   # reliable free-tier fallback
    "openai/gpt-oss-120b",
]
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# ── High-Performance Viral Prompt ─────────────────────────────────────────────

SYSTEM_PROMPT = textwrap.dedent("""\
    You are an elite YouTube Shorts scriptwriter specialising in motivational, quote-based,
    and deep-insight content for channels like @learnwithnavi.

    When given a topic, respond ONLY with a valid JSON object — no markdown fences, no extra text.

    Schema:
    {
      "script":      "<voiceover, 150-250 words exactly. Rich, immersive, inspirational.>",
      "title":       "<YouTube title under 90 chars. Emotionally powerful. Curiosity-gap.>",
      "description": "<YouTube description under 480 chars. Hook + 3 bullet points + CTA + #Shorts>",
      "tags":        ["<up to 15 relevant discovery tags>"],
      "keywords":    ["<4-6 SPECIFIC visual stock-footage search terms>"]
    }

    SCRIPT RULES (strictly follow):
    - HOOK (words 1-30): Bold opening fact, provocative question, or powerful quote.
      This sentence must stop the viewer from scrolling. Make it visceral.
    - CORE (words 31-200): Deep dive — 3 to 5 connected insights, build momentum.
      Use storytelling, vivid analogies, and surprising specifics. Short sentences.
      Each idea must be surprising, verifiable, and thought-provoking.
    - CLOSE (words 201-250): Powerful reflective line + strong CTA.
      Example: "The hardest battles are fought in silence. Follow for daily wisdom."
    - NO stage directions, NO [music], NO (pause). Pure spoken text only.
    - Tone: Calm authority meets genuine curiosity. Like a wise mentor speaking directly to you.

    KEYWORDS RULES (critical for stock footage quality):
    - SPECIFIC, VISUAL, CINEMATIC. Think: what would be playing on screen?
    - BAD: "motivation", "success", "people"
    - GOOD: "lone climber mountain summit", "sunrise timelapse city", "stoic philosopher rome"

    TAGS RULES:
    - Mix broad (#Shorts #Motivation) with niche (#StoicPhilosophy #MindsetShift)
    - Always include: "Shorts", "YouTubeShorts", "Motivation", "Mindset"

    Do NOT output anything outside the JSON object.
""")


def _clean_json(raw: str) -> str:
    """Strip markdown fences and thinking blocks from model response."""
    raw = raw.strip()
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"```$", "", raw)
    return raw.strip()


def _parse_response(raw: str) -> dict:
    """Try JSON parse; fall back to regex extraction."""
    cleaned = _clean_json(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Primary JSON parse failed — attempting regex extraction.")

    def _extract(pattern: str, text: str, default):
        m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else default

    script = _extract(r'"script"\s*:\s*"(.*?)"', cleaned, "Wisdom is the art of knowing what to overlook.")
    title = _extract(r'"title"\s*:\s*"(.*?)"', cleaned, "Words That Hit Different #Shorts")
    description = _extract(r'"description"\s*:\s*"(.*?)"', cleaned, "Daily wisdom. #Shorts")

    tags_raw = _extract(r'"tags"\s*:\s*\[(.*?)\]', cleaned, "")
    tags = [t.strip().strip('"') for t in tags_raw.split(",") if t.strip()] if tags_raw else ["Shorts", "Motivation"]

    kw_raw = _extract(r'"keywords"\s*:\s*\[(.*?)\]', cleaned, "")
    keywords = [k.strip().strip('"') for k in kw_raw.split(",") if k.strip()] if kw_raw else ["mountain sunrise", "philosophy"]

    return {
        "script": script, "title": title, "description": description,
        "tags": tags, "keywords": keywords,
    }


def _generate_with_groq(topic: str, groq_api_key: str) -> str | None:
    """Try each Groq model in priority order, return raw text or None."""
    client = Groq(api_key=groq_api_key)
    user_prompt = f'Create a YouTube Shorts motivational/insight script about: "{topic}"'

    for model_name in GROQ_MODELS:
        try:
            logger.info("Calling Groq (%s) for topic: %s", model_name, topic)
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.85,
                max_tokens=2048,
            )
            raw = response.choices[0].message.content
            if raw and raw.strip():
                logger.info("Groq model %s succeeded.", model_name)
                return raw
        except Exception as exc:
            logger.warning("Groq model %s failed: %s", model_name, exc)

    return None


def _generate_with_gemini(topic: str) -> str | None:
    """Fallback: call Gemini REST API directly."""
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_key:
        logger.debug("GEMINI_API_KEY not set, skipping Gemini fallback.")
        return None

    import urllib.request

    user_prompt = f'{SYSTEM_PROMPT}\n\nCreate a YouTube Shorts motivational/insight script about: "{topic}"'
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={gemini_key}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.85, "maxOutputTokens": 2048},
    }).encode()

    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            logger.info("Gemini fallback succeeded.")
            return text
    except Exception as exc:
        logger.warning("Gemini fallback failed: %s", exc)
        return None


def generate_script(topic: str) -> dict:
    """
    Generate a structured viral script dict using Groq → Gemini → curated offline fallback.

    Args:
        topic: The video topic (e.g. "stoic philosophy life lessons").

    Returns:
        dict with keys: script, title, description, tags, keywords
    """
    groq_api_key = os.getenv("GROQ_API_KEY", "")
    raw_text = None

    # 1. Try Groq (priority model chain)
    if groq_api_key:
        raw_text = _generate_with_groq(topic, groq_api_key)

    # 2. Try Gemini if Groq failed
    if not raw_text:
        logger.info("Groq unavailable/failed. Trying Gemini fallback...")
        raw_text = _generate_with_gemini(topic)

    # 3. High-quality curated offline script if all APIs fail
    if not raw_text:
        logger.warning("All APIs failed. Using curated offline script for: %s", topic)
        raw_text = json.dumps({
            "script": (
                f"Most people spend their entire lives chasing success without ever defining what it means to them. "
                f"Today we're exploring the deep truth hidden inside {topic}. "
                "The Stoics believed that you cannot control what happens to you — only how you respond. "
                "Modern neuroscience agrees: your reaction to adversity literally reshapes your brain. "
                "People who consistently choose growth over comfort develop what psychologists call "
                "post-traumatic growth — they don't just recover, they evolve. "
                "The difference between those who rise and those who stay stuck is not talent. "
                "It's the decision to act before they feel ready. "
                "Start before you're confident. Grow through what you go through. "
                "Follow for daily wisdom that rewires how you think."
            ),
            "title": f"The Hidden Truth About {topic[:45]} #Shorts",
            "description": (
                f"Daily wisdom on {topic}.\n"
                "• Backed by science & philosophy\n"
                "• Change how you think in 60 seconds\n"
                "• Share with someone who needs this\n"
                "Follow for daily mindset content. #Shorts #Motivation #Mindset"
            ),
            "tags": ["Shorts", "Motivation", "YouTubeShorts", "Mindset", "Wisdom",
                     "SelfImprovement", "Philosophy", "Stoicism", "Growth", "DailyMotivation"],
            "keywords": ["mountain sunrise timelapse", "lone climber summit",
                         "stoic philosopher stone", "city lights dawn"],
        })

    result = _parse_response(raw_text)

    # ── Post-process & enforce limits ────────────────────────────────────────
    words = result["script"].split()
    if len(words) > 260:
        result["script"] = " ".join(words[:260])

    title = result["title"].strip()
    if "#shorts" not in title.lower():
        title = f"{title[:87].rstrip()} #Shorts"
    result["title"] = title[:100]

    desc = result["description"].strip()
    if "#shorts" not in desc.lower():
        desc = f"{desc[:477].rstrip()} #Shorts"
    result["description"] = desc[:500]

    result["tags"] = result.get("tags", [])[:15]
    if not any(t.lower() in ("shorts", "youtubeshorts") for t in result["tags"]):
        result["tags"].insert(0, "Shorts")

    result.setdefault("keywords", ["mountain sunrise", "philosophy wisdom", "city morning"])

    logger.info("Script ready: '%s' (%d words)", result["title"], len(result["script"].split()))
    return result
