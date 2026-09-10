"""
uploaders/base.py
-----------------
Abstract base class and data structures for all platform uploaders.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class UploadResult:
    """Consolidated status returned by any platform uploader."""

    platform: str
    success: bool
    post_id: Optional[str] = None
    post_url: Optional[str] = None
    error_message: Optional[str] = None

    def __str__(self) -> str:
        if self.success:
            return f"✅ [{self.platform.upper()}] Success | Post ID: {self.post_id} | URL: {self.post_url or 'N/A'}"
        return f"❌ [{self.platform.upper()}] Failed | Error: {self.error_message}"


class BaseUploader(ABC):
    """Abstract strategy for platform uploading."""

    def __init__(self, platform_name: str):
        self.platform_name = platform_name

    @abstractmethod
    def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        **kwargs: Any,
    ) -> UploadResult:
        """Upload vertical video asset (YouTube, Pinterest, FB, Instagram)."""
        pass

    @abstractmethod
    def upload_quote(self, quote_data: Dict[str, Any], **kwargs: Any) -> UploadResult:
        """Upload pure text quote (X, Threads)."""
        pass
