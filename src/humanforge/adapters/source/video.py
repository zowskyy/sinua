"""Level 1 — video/webcam source adapter (interface stub).

A full implementation requires a facial solver (e.g. MediaPipe, OpenCV,
or Human Forge's own solver). This stub defines the contract, registers
the adapter, and raises AdapterError with an actionable message if called
without the optional dependency installed.

Install extras:  pip install humanforge[video]
"""
from __future__ import annotations

from pathlib import Path

from humanforge.adapters.base import AdapterError, SourceAdapter
from humanforge.adapters.registry import register_source
from humanforge.spf.schema import SemanticPerformancePackage

_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".mts", ".m4v"}


class VideoSourceAdapter(SourceAdapter):
    ADAPTER_ID = "hf.source.video.v1"
    ADAPTER_VERSION = "1.0.0"
    SOURCE_TYPE = "video"
    SUPPORT_LEVEL = 1  # Native

    def can_handle(self, source: str | Path) -> bool:
        return False  # stub — not yet implemented; install humanforge[video]

    def ingest(
        self,
        source: str | Path,
        *,
        frame_rate: float | None = None,
        metadata: dict | None = None,
    ) -> SemanticPerformancePackage:
        _require_solver()
        raise NotImplementedError  # reached only when solver is present


class WebcamSourceAdapter(SourceAdapter):
    ADAPTER_ID = "hf.source.webcam.v1"
    ADAPTER_VERSION = "1.0.0"
    SOURCE_TYPE = "webcam"
    SUPPORT_LEVEL = 1  # Native

    def can_handle(self, source: str | Path) -> bool:
        return False  # stub — not yet implemented; install humanforge[video]

    def ingest(
        self,
        source: str | Path,
        *,
        frame_rate: float | None = None,
        metadata: dict | None = None,
    ) -> SemanticPerformancePackage:
        _require_solver()
        raise NotImplementedError


def _require_solver() -> None:
    try:
        import humanforge_solver  # noqa: F401
    except ImportError as exc:
        raise AdapterError(
            "The video/webcam source adapter requires the humanforge-solver "
            "package. Install it with: pip install humanforge[video]"
        ) from exc


register_source(VideoSourceAdapter())
register_source(WebcamSourceAdapter())
