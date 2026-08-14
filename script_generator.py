"""
script_generator.py
-------------------
Generates a structured video script (JSON) using the Groq API (Llama 3.3 70B).

Returns a dict with keys:
    script      - voiceover text (<= 60 words, optimised for YouTube Shorts)
    title       - YouTube video title (<= 100 chars)
    description - YouTube video description (<= 500 chars)
    tags        - list[str] of relevant tags
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

GROQ_MODEL = "llama-3.3-70b-versatile"

# ── Prompt template ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = textwrap.dedent("""\
    You are a YouTube Shorts scriptwriter specializing in engaging, punchy content.
    When given a topic, respond ONLY with a valid JSON object — no markdown fences,
    no extra text — that matches this exact schema:

    {
      "script":      "<voiceover text, between 100 and 130 words, designed for a 40-50 second Short>",
      "title":       "<YouTube video title, strictly under 90 characters>",
      "description": "<YouTube description, under 500 characters, include a call-to-action>",
      "tags":        ["<tag1>", "<tag2>", "...", "<up to 15 tags>"],
      "keywords":    ["<2-4 single-word stock-footage search terms related to the topic>"]
    }

    Rules:
    - The script MUST be between 100 and 130 words. This is critical — do NOT exceed 135 words so the video stays strictly under 50 seconds.
    - Structure the script with: a hook (first sentence), 2-3 concise key points, and a fast call-to-action ending.
    - Write in a conversational, energetic tone suitable for fast voiceover.
    - Tags must be relevant and improve discoverability.
    - keywords are used to fetch background footage - keep them concrete and visual
      (e.g. "ocean", "city", "forest", "technology").
    - Do NOT include any text outside the JSON object.
""")


def _clean_json(raw: str) -> str:
    """Strip markdown code fences if the model wraps its response in them."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"```$", "", raw)
    return raw.strip()


def _parse_response(raw: str) -> dict:
    """Try JSON parse; fall back to regex extraction for partial responses."""
    cleaned = _clean_json(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Primary JSON parse failed - attempting regex extraction.")

    def _extract(pattern: str, text: str, default):
        m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else default

    script = _extract(r'"script"\s*:\s*"(.*?)"', cleaned, "An amazing fact you didn't know!")
    title = _extract(r'"title"\s*:\s*"(.*?)"', cleaned, "Amazing Fact #Shorts")
    description = _extract(r'"description"\s*:\s*"(.*?)"', cleaned, "Watch till the end! #Shorts")

    tags_raw = _extract(r'"tags"\s*:\s*\[(.*?)\]', cleaned, "")
    tags = [t.strip().strip('"') for t in tags_raw.split(",") if t.strip()] if tags_raw else ["shorts", "facts"]

    kw_raw = _extract(r'"keywords"\s*:\s*\[(.*?)\]', cleaned, "")
    keywords = [k.strip().strip('"') for k in kw_raw.split(",") if k.strip()] if kw_raw else ["nature"]

    return {
        "script": script,
        "title": title,
        "description": description,
        "tags": tags,
        "keywords": keywords,
    }


def generate_script(topic: str) -> dict:
    """
    Call the Groq API (Llama 3.3 70B) and return a structured script dict.

    Args:
        topic: The video topic (e.g. "3 mind-blowing space facts").

    Returns:
        dict with keys: script, title, description, tags, keywords

    Raises:
        RuntimeError: If the API call fails.
    """
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise EnvironmentError("GROQ_API_KEY is not set in .env")

    client = Groq(api_key=groq_api_key)
    user_prompt = f'Create a YouTube Shorts video script about: "{topic}"'

    logger.info("Calling Groq (%s) for topic: %s", GROQ_MODEL, topic)

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
            max_tokens=2048,
        )
        raw_text: str = response.choices[0].message.content
        logger.debug("Raw Groq response:\n%s", raw_text)
    except Exception as exc:
        logger.error("Groq API call failed: %s", exc)
        raise RuntimeError(f"Groq API error: {exc}") from exc

    result = _parse_response(raw_text)

    # Enforce strict length limits for YouTube Shorts (under 50 seconds)
    words = result["script"].split()
    if len(words) > 135:
        result["script"] = " ".join(words[:135])

    # Ensure #Shorts tag in title and description
    title = result["title"].strip()
    if "#shorts" not in title.lower():
        title = f"{title[:90].strip()} #Shorts"
    result["title"] = title[:100]

    desc = result["description"].strip()
    if "#shorts" not in desc.lower():
        desc = f"{desc[:480].strip()} #Shorts"
    result["description"] = desc[:500]

    result["tags"] = result.get("tags", [])[:15]
    if "Shorts" not in result["tags"] and "shorts" not in result["tags"]:
        result["tags"].insert(0, "Shorts")

    result.setdefault("keywords", ["nature"])

    logger.info("Script generated: '%s'", result["title"])
    return result
