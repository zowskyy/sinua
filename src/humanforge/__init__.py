"""Human Forge Studio — source-agnostic performance-animation platform.

The public API surface is small by design. Import from sub-packages for
lower-level access (adapters, character, inspector, spf).
"""
from __future__ import annotations

__version__ = "0.1.0"

from humanforge.pipeline import Pipeline, PipelineResult
from humanforge.spf.schema import (
    SCHEMA_VERSION,
    SemanticPerformancePackage,
    SourceInfo,
    PerformanceFrame,
    FaceChannel,
    FaceChannels,
    HeadPose,
    EyeGaze,
    BodyJoint,
    AudioAlignment,
    Confidence,
)
from humanforge.spf.serialization import load_package, save_package
from humanforge.spf.validation import validate_package

__all__ = [
    "__version__",
    "Pipeline",
    "PipelineResult",
    "SCHEMA_VERSION",
    "SemanticPerformancePackage",
    "SourceInfo",
    "PerformanceFrame",
    "FaceChannel",
    "FaceChannels",
    "HeadPose",
    "EyeGaze",
    "BodyJoint",
    "AudioAlignment",
    "Confidence",
    "load_package",
    "save_package",
    "validate_package",
]
