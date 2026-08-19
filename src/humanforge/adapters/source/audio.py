"""Level 1 — audio source adapter (interface stub).

Extracts phoneme, viseme, and word timing from an audio file.
Requires the optional humanforge-audio package.

Install extras:  pip install humanforge[audio]
"""
from __future__ import annotations

from pathlib import Path

from humanforge.adapters.base import AdapterError, SourceAdapter
from humanforge.adapters.registry import register_source
from humanforge.spf.schema import SemanticPerformancePackage

_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".aac", ".ogg", ".m4a", ".aiff"}


class AudioSourceAdapter(SourceAdapter):
    ADAPTER_ID = "hf.source.audio.v1"
    ADAPTER_VERSION = "1.0.0"
    SOURCE_TYPE = "audio"
    SUPPORT_LEVEL = 1  # Native

    def can_handle(self, source: str | Path) -> bool:
        return False  # stub — not yet implemented; install humanforge[audio]

    def ingest(
        self,
        source: str | Path,
        *,
        frame_rate: float | None = None,
        metadata: dict | None = None,
    ) -> SemanticPerformancePackage:
        _require_audio()
        raise NotImplementedError


def _require_audio() -> None:
    try:
        import humanforge_audio  # noqa: F401
    except ImportError as exc:
        raise AdapterError(
            "The audio source adapter requires the humanforge-audio package. "
            "Install it with: pip install humanforge[audio]"
        ) from exc


register_source(AudioSourceAdapter())
