"""Maya destination adapter stub.

Full implementation requires Maya Python API (maya.cmds / maya.OpenMaya).
Install the humanforge Maya plugin from the companion package or run this
adapter from within a Maya session.

Usage inside Maya:
    from humanforge.adapters.destination.maya import MayaDestinationAdapter
    MayaDestinationAdapter().export(pkg, "scene.ma")
"""
from __future__ import annotations

from pathlib import Path

from humanforge.adapters.base import AdapterError, DestinationAdapter, ExportValidationReport
from humanforge.adapters.registry import register_destination
from humanforge.spf.schema import SemanticPerformancePackage


class MayaDestinationAdapter(DestinationAdapter):
    ADAPTER_ID = "hf.destination.maya.v1"
    ADAPTER_VERSION = "1.0.0"
    DESTINATION_TYPE = "maya"

    def can_export(self, pkg: SemanticPerformancePackage) -> bool:
        try:
            import maya.cmds  # noqa: F401
            return True
        except ImportError:
            return False

    def export(
        self,
        pkg: SemanticPerformancePackage,
        output_path: str | Path,
        **kwargs,
    ) -> Path:
        try:
            import maya.cmds as cmds  # noqa: F401
        except ImportError as exc:
            raise AdapterError(
                "Maya Python API not available. Run this adapter from within a Maya session "
                "or install the humanforge Maya plugin."
            ) from exc

        raise AdapterError(
            "Maya export is not yet implemented. "
            "Contribute at https://github.com/zowskyy/sinua"
        )

    def validate_export(
        self,
        pkg: SemanticPerformancePackage,
        exported_path: str | Path,
    ) -> ExportValidationReport:
        from humanforge.adapters.base import ExportCheckResult
        path = Path(exported_path)
        return ExportValidationReport(
            self.ADAPTER_ID,
            path,
            [ExportCheckResult(
                name="file_exists",
                passed=path.exists(),
                severity="error",
                message=f"Maya output not found: {path}",
            )],
        )


register_destination(MayaDestinationAdapter())
