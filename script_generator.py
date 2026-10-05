"""
script_generator.py
-------------------
Generates high-retention mythological video scripts optimised for YouTube Shorts.

Features:
  1. Master Prompter integration for 3-act Hindi mythological storytelling.
  2. Generates YouTube Shorts titles (with #Shorts), SEO descriptions, and high-impact tags.
  3. Returns scene-by-scene live-action cinematic image prompts for AI visual generation.
  4. Automatic fallback chain: Groq (openai/gpt-oss-120b -> openai/gpt-oss-20b -> groq/compound) -> Gemini -> Curated Template.

Public API:
    result = generate_script(topic="The curse of Karna")
"""

from __future__ import annotations

import json
import logging
import re
from typing import Dict, Any, Optional

import config
from prompter import generate_mythological_prompt_pack

# ── Model Priority List ───────────────────────────────────────────────────────
GROQ_MODELS = [
    "openai/gpt-oss-120b",      # 120B parameter powerhouse: flawless Hindi grammar & zero hallucinations
    "openai/gpt-oss-20b",
    config.GROQ_MODEL,
    "qwen/qwen3.8-27b",
]

logger = logging.getLogger("script_generator")


def generate_script(topic: str) -> Dict[str, Any]:
    """Generate complete script, scene prompts, and YouTube Shorts metadata."""
    logger.info("Generating YouTube Shorts script via Master Mythological Prompter: '%s'", topic)
    data = generate_mythological_prompt_pack(topic)

    # Enhance metadata specifically for YouTube Shorts
    raw_title = data.get("title", topic).strip()
    if not raw_title.endswith("#Shorts") and "#shorts" not in raw_title.lower():
        yt_title = f"{raw_title} #Shorts"
    else:
        yt_title = raw_title

    # Truncate title if longer than 90 chars (YouTube max is 100)
    if len(yt_title) > 90:
        base = raw_title[:80].rsplit(" ", 1)[0]
        yt_title = f"{base} #Shorts"

    hashtags = data.get("hashtags", [
        "#Shorts", "#Mahabharat", "#Ramayana", "#SanatanDharma",
        "#LordKrishna", "#Karma", "#LifeLessons", "#Mythology"
    ])
    if "#Shorts" not in hashtags and "#shorts" not in hashtags:
        hashtags.insert(0, "#Shorts")

    tags = [h.lstrip("#") for h in hashtags]
    for extra_tag in ["Shorts", "Mythology", "Hindu Mythology", "Life Lessons", "Sanatan Dharma"]:
        if extra_tag not in tags:
            tags.append(extra_tag)

    # Build comprehensive YouTube description
    full_script = data.get("script", "")
    description_lines = [
        raw_title,
        "",
        full_script,
        "",
        "सनातन धर्म और प्राचीन भारतीय इतिहास की अमर सीख। सब्सक्राइब ज़रूर करें!",
        "",
        " ".join(hashtags[:12]),
    ]
    yt_description = "\n".join(description_lines)

    data["youtube_title"] = yt_title
    data["youtube_description"] = yt_description
    data["youtube_tags"] = tags

    return data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = generate_script("The curse of Karna")
    print(json.dumps(res, indent=2, ensure_ascii=False))
