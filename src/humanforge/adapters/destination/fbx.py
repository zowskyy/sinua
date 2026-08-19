"""FBX destination adapter (Level 2 — standard import, interface stub).

FBX is a proprietary format. Full export requires either the Autodesk FBX SDK
(via fbx-python) or a DCC application. This stub defines the contract so the
pipeline can route to FBX and report a clear error if the dependency is absent.

Install extras:  pip install humanforge[fbx]
"""
from __future__ import annotations

from pathlib import Path

from humanforge.adapters.base import AdapterError, DestinationAdapter, ExportValidationReport
from humanforge.adapters.registry import register_destination
from humanforge.spf.schema import SemanticPerformancePackage


class FbxDestinationAdapter(DestinationAdapter):
    ADAPTER_ID = "hf.destination.fbx.v1"
    ADAPTER_VERSION = "1.0.0"
    DESTINATION_TYPE = "fbx"

    def can_export(self, pkg: SemanticPerformancePackage) -> bool:
        return False  # stub — not yet implemented; install humanforge[fbx]

    def export(
        self,
        pkg: SemanticPerformancePackage,
        output_path: str | Path,
        **kwargs,
    ) -> Path:
        _require_fbx()
        raise NotImplementedError

    def validate_export(
        self,
        pkg: SemanticPerformancePackage,
        exported_path: str | Path,
    ) -> ExportValidationReport:
        _require_fbx()
        raise NotImplementedError


def _require_fbx() -> None:
    try:
        import fbx  # noqa: F401
    except ImportError as exc:
        raise AdapterError(
            "The FBX destination adapter requires the fbx-python package "
            "(Autodesk FBX SDK binding). "
            "Install it with: pip install humanforge[fbx]"
        ) from exc


register_destination(FbxDestinationAdapter())
