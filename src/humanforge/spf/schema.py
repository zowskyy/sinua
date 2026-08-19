"""Semantic Performance Format — engine-neutral animation data model.

Missing data is represented as None (unknown), never as zero or inferred
certainty. Confidence=None means the source did not provide a quality
estimate. Confidence(value=0.0) means we have an estimate and it is zero.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SCHEMA_VERSION = "1.0"

SourceType = Literal[
    "video",
    "webcam",
    "depth",
    "head_mounted_camera",
    "optical_mocap",
    "inertial_mocap",
    "curves",
    "body_pose",
    "audio",
    "live_stream",
    "hand_authored",
]

SupportLevel = Literal[1, 2, 3]


@dataclass
class Confidence:
    """Quality estimate for a single datum.

    value=None is disallowed; use confidence=None on the parent field to
    express that no quality information is available at all.
    """

    value: float  # 0.0 (no confidence) – 1.0 (full confidence)
    reason: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"Confidence.value must be in [0, 1], got {self.value!r}")

    @classmethod
    def certain(cls) -> "Confidence":
        return cls(value=1.0)

    @classmethod
    def unknown(cls) -> "Confidence":
        return cls(value=0.0, reason="unknown")


@dataclass
class FrameTimecode:
    frame_index: int        # zero-based
    time_seconds: float     # elapsed from clip start
    smpte: str | None = None  # "HH:MM:SS:FF" when available


@dataclass
class HeadPose:
    """6-DOF head pose in Y-up, right-handed coordinates."""

    translation: tuple[float, float, float]                   # metres
    rotation_quaternion: tuple[float, float, float, float]    # (w, x, y, z)
    confidence: Confidence | None = None


@dataclass
class FaceChannel:
    """Single facial control — name is ARKit-compatible but not restricted."""

    name: str
    value: float  # 0.0–1.0 for blendshapes; may exceed range for correctives
    confidence: Confidence | None = None


@dataclass
class EyeGaze:
    left_direction: tuple[float, float, float]   # unit vector
    right_direction: tuple[float, float, float]  # unit vector
    left_blink: float   # 0.0–1.0
    right_blink: float  # 0.0–1.0
    confidence: Confidence | None = None


@dataclass
class BodyJoint:
    """Single skeleton joint.  position/rotation may be None if not captured."""

    name: str
    position: tuple[float, float, float] | None = None                   # metres, Y-up
    rotation_quaternion: tuple[float, float, float, float] | None = None  # (w, x, y, z)
    confidence: Confidence | None = None


@dataclass
class AudioAlignment:
    time_seconds: float
    phoneme: str | None = None   # IPA or ARPABET
    viseme: str | None = None    # e.g. "PP", "FF", "TH", "SIL"
    word: str | None = None
    confidence: Confidence | None = None


@dataclass
class PerformanceFrame:
    timecode: FrameTimecode
    head_pose: HeadPose | None = None
    face_channels: list[FaceChannel] = field(default_factory=list)
    eye_gaze: EyeGaze | None = None
    body_joints: list[BodyJoint] = field(default_factory=list)
    audio_alignments: list[AudioAlignment] = field(default_factory=list)

    def face_channel(self, name: str) -> FaceChannel | None:
        for ch in self.face_channels:
            if ch.name == name:
                return ch
        return None

    def body_joint(self, name: str) -> BodyJoint | None:
        for j in self.body_joints:
            if j.name == name:
                return j
        return None


@dataclass
class SourceInfo:
    type: str  # SourceType or custom string
    support_level: int  # 1 = native, 2 = standard import, 3 = partner/custom
    adapter_id: str
    adapter_version: str
    file_hash: str | None = None      # "sha256:<hex>"
    timecode_start: str | None = None  # SMPTE
    frame_rate: float | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class ChannelOverride:
    """Per-channel retargeting correction added at the project level."""

    source_name: str
    target_name: str
    scale: float = 1.0
    offset: float = 0.0
    invert: bool = False


@dataclass
class CharacterMapping:
    character_id: str
    rig_profile_id: str
    retarget_profile_id: str
    channel_overrides: list[ChannelOverride] = field(default_factory=list)


@dataclass
class RepairLayer:
    """A named edit applied on top of solver output.

    Animator edits and automatic repair remain independently addressable so
    either can be removed or re-applied without touching the other.
    """

    layer_id: str
    type: str  # "manual_override" | "interpolation_fill" | "smooth" | "clamp" | ...
    channels: list[str]
    frame_range: tuple[int, int] | None = None  # inclusive [start, end]
    author: str | None = None
    timestamp: str | None = None   # ISO 8601
    parameters: dict[str, object] = field(default_factory=dict)


@dataclass
class Provenance:
    solver: str
    solver_version: str
    compute_recipe: str
    source_adapters: list[str]
    created_at: str   # ISO 8601
    modified_at: str  # ISO 8601
    user_edits: list[str] = field(default_factory=list)


@dataclass
class SemanticPerformancePackage:
    """Root container — the portable unit that moves between tools.

    All source, retargeting, and edit information lives here, so the same
    package can be re-exported to a different destination without needing the
    original capture data.
    """

    schema_version: str
    source: SourceInfo
    frames: list[PerformanceFrame]
    character_mapping: CharacterMapping | None = None
    repair_layers: list[RepairLayer] = field(default_factory=list)
    provenance: Provenance | None = None

    @property
    def frame_count(self) -> int:
        return len(self.frames)

    @property
    def duration_seconds(self) -> float:
        if not self.frames:
            return 0.0
        return self.frames[-1].timecode.time_seconds - self.frames[0].timecode.time_seconds

    @property
    def frame_rate(self) -> float | None:
        return self.source.frame_rate

    def face_channel_names(self) -> set[str]:
        return {ch.name for f in self.frames for ch in f.face_channels}

    def body_joint_names(self) -> set[str]:
        return {j.name for f in self.frames for j in f.body_joints}


# ---------------------------------------------------------------------------
# Well-known face-channel name constants (ARKit-compatible subset)
# ---------------------------------------------------------------------------
class FaceChannels:
    EYE_BLINK_LEFT = "eyeBlinkLeft"
    EYE_BLINK_RIGHT = "eyeBlinkRight"
    EYE_LOOK_UP_LEFT = "eyeLookUpLeft"
    EYE_LOOK_UP_RIGHT = "eyeLookUpRight"
    EYE_LOOK_DOWN_LEFT = "eyeLookDownLeft"
    EYE_LOOK_DOWN_RIGHT = "eyeLookDownRight"
    EYE_LOOK_IN_LEFT = "eyeLookInLeft"
    EYE_LOOK_IN_RIGHT = "eyeLookInRight"
    EYE_LOOK_OUT_LEFT = "eyeLookOutLeft"
    EYE_LOOK_OUT_RIGHT = "eyeLookOutRight"
    EYE_WIDE_LEFT = "eyeWideLeft"
    EYE_WIDE_RIGHT = "eyeWideRight"
    EYE_SQUINT_LEFT = "eyeSquintLeft"
    EYE_SQUINT_RIGHT = "eyeSquintRight"
    BROW_DOWN_LEFT = "browDownLeft"
    BROW_DOWN_RIGHT = "browDownRight"
    BROW_INNER_UP = "browInnerUp"
    BROW_OUTER_UP_LEFT = "browOuterUpLeft"
    BROW_OUTER_UP_RIGHT = "browOuterUpRight"
    NOSE_SNEER_LEFT = "noseSneerLeft"
    NOSE_SNEER_RIGHT = "noseSneerRight"
    CHEEK_PUFF = "cheekPuff"
    CHEEK_SQUINT_LEFT = "cheekSquintLeft"
    CHEEK_SQUINT_RIGHT = "cheekSquintRight"
    JAW_FORWARD = "jawForward"
    JAW_LEFT = "jawLeft"
    JAW_RIGHT = "jawRight"
    JAW_OPEN = "jawOpen"
    MOUTH_CLOSE = "mouthClose"
    MOUTH_FUNNEL = "mouthFunnel"
    MOUTH_PUCKER = "mouthPucker"
    MOUTH_LEFT = "mouthLeft"
    MOUTH_RIGHT = "mouthRight"
    MOUTH_SMILE_LEFT = "mouthSmileLeft"
    MOUTH_SMILE_RIGHT = "mouthSmileRight"
    MOUTH_FROWN_LEFT = "mouthFrownLeft"
    MOUTH_FROWN_RIGHT = "mouthFrownRight"
    MOUTH_DIMPLE_LEFT = "mouthDimpleLeft"
    MOUTH_DIMPLE_RIGHT = "mouthDimpleRight"
    MOUTH_STRETCH_LEFT = "mouthStretchLeft"
    MOUTH_STRETCH_RIGHT = "mouthStretchRight"
    MOUTH_ROLL_LOWER = "mouthRollLower"
    MOUTH_ROLL_UPPER = "mouthRollUpper"
    MOUTH_SHRUG_LOWER = "mouthShrugLower"
    MOUTH_SHRUG_UPPER = "mouthShrugUpper"
    MOUTH_PRESS_LEFT = "mouthPressLeft"
    MOUTH_PRESS_RIGHT = "mouthPressRight"
    MOUTH_LOWER_DOWN_LEFT = "mouthLowerDownLeft"
    MOUTH_LOWER_DOWN_RIGHT = "mouthLowerDownRight"
    MOUTH_UPPER_UP_LEFT = "mouthUpperUpLeft"
    MOUTH_UPPER_UP_RIGHT = "mouthUpperUpRight"
    TONGUE_OUT = "tongueOut"
