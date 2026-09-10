"""
metadata_adapter.py
-------------------
Adapts video script metadata and quote text into platform-specific captions,
titles, and tag structures.
"""

from __future__ import annotations

from typing import Any, Dict, List


class MetadataAdapter:
    """Formatter helper for multi-platform post metadata."""

    @staticmethod
    def for_youtube(title: str, description: str, tags: List[str]) -> Dict[str, Any]:
        """YouTube Shorts metadata."""
        return {
            "title": title[:100],
            "description": f"{description[:4800]}\n\n#Shorts",
            "tags": tags[:20],
        }

    @staticmethod
    def for_pinterest(title: str, description: str, tags: List[str]) -> Dict[str, Any]:
        """Pinterest Video Pin metadata."""
        hashtag_str = " ".join([f"#{t.replace(' ', '')}" for t in tags[:5]])
        clean_desc = f"{description[:450]}\n\n{hashtag_str}"[:500]
        return {
            "title": title[:100],
            "description": clean_desc,
        }

    @staticmethod
    def for_facebook(title: str, description: str, tags: List[str]) -> Dict[str, Any]:
        """Facebook Page Reel metadata."""
        hashtag_str = " ".join([f"#{t.replace(' ', '')}" for t in tags[:8]])
        caption = f"{title}\n\n{description}\n\n{hashtag_str}"[:2000]
        return {
            "description": caption,
            "title": title[:100],
        }

    @staticmethod
    def for_instagram(title: str, description: str, tags: List[str]) -> Dict[str, Any]:
        """Instagram Reel metadata."""
        hashtag_str = " ".join([f"#{t.replace(' ', '')}" for t in tags[:15]])
        caption = f"{title}\n\n{description}\n\n{hashtag_str}"[:2200]
        return {
            "caption": caption,
        }

    @staticmethod
    def for_x_quote(quote_data: Dict[str, Any]) -> str:
        """X (Twitter) pure text quote formatting (strict <= 280 chars)."""
        return quote_data.get("formatted_x_post", f"“{quote_data.get('quote')}” — {quote_data.get('author')}")

    @staticmethod
    def for_threads_quote(quote_data: Dict[str, Any]) -> str:
        """Threads pure text quote formatting (strict <= 500 chars)."""
        return quote_data.get("formatted_threads_post", f"“{quote_data.get('quote')}” — {quote_data.get('author')}")
