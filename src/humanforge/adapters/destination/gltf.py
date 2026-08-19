"""glTF destination adapter (Level 2 — standard import, interface stub).

Full implementation requires the pygltflib package.
Install extras:  pip install humanforge[gltf]
"""
from __future__ import annotations

from pathlib import Path

from humanforge.adapters.base import AdapterError, DestinationAdapter, ExportValidationReport
from humanforge.adapters.registry import register_destination
from humanforge.spf.schema import SemanticPerformancePackage


class GltfDestinationAdapter(DestinationAdapter):
    ADAPTER_ID = "hf.destination.gltf.v1"
    ADAPTER_VERSION = "1.0.0"
    DESTINATION_TYPE = "gltf"

    def can_export(self, pkg: SemanticPerformancePackage) -> bool:
        return False  # stub — not yet implemented; install humanforge[gltf]

    def export(
        self,
        pkg: SemanticPerformancePackage,
        output_path: str | Path,
        **kwargs,
    ) -> Path:
        _require_gltf()
        raise NotImplementedError

    def validate_export(
        self,
        pkg: SemanticPerformancePackage,
        exported_path: str | Path,
    ) -> ExportValidationReport:
        _require_gltf()
        raise NotImplementedError


def _require_gltf() -> None:
    try:
        import pygltflib  # noqa: F401
    except ImportError as exc:
        raise AdapterError(
            "The glTF destination adapter requires pygltflib. "
            "Install it with: pip install humanforge[gltf]"
        ) from exc


register_destination(GltfDestinationAdapter())
