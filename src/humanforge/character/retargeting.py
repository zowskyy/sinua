"""Character retargeting engine.

Applies a RetargetProfile to an SPF package, renaming channels from source
naming to target rig naming, applying scale/offset/invert, and clamping
to the target control's declared range.

The input package is not mutated; a new package is returned with
character_mapping set and retargeted face channels.
"""
from __future__ import annotations

import copy
from dataclasses import replace

from humanforge.character.schema import ChannelMapping, RetargetProfile, RigProfile
from humanforge.spf.schema import (
    CharacterMapping,
    Confidence,
    FaceChannel,
    PerformanceFrame,
    SemanticPerformancePackage,
)


class RetargetError(Exception):
    pass


def retarget(
    pkg: SemanticPerformancePackage,
    *,
    rig_profile: RigProfile,
    retarget_profile: RetargetProfile,
    character_id: str,
    unmapped_policy: str = "drop",  # "drop" | "passthrough" | "zero"
) -> SemanticPerformancePackage:
    """Return a new package with face channels retargeted to *rig_profile*.

    unmapped_policy controls what happens to source channels with no mapping:
    - "drop"        : omit them from the output (default; keeps output clean)
    - "passthrough" : keep them unchanged (useful for debugging)
    - "zero"        : include them at value=0.0

    Body joints and head pose are preserved unchanged.
    """
    if (
        retarget_profile.source_rig_id != "*"
        and pkg.character_mapping
        and retarget_profile.source_rig_id != pkg.character_mapping.rig_profile_id
    ):
        raise RetargetError(
            f"RetargetProfile {retarget_profile.profile_id!r} expects source rig "
            f"{retarget_profile.source_rig_id!r} but package has "
            f"{pkg.character_mapping.rig_profile_id!r}"
        )

    new_frames = [
        _retarget_frame(frame, rig_profile, retarget_profile, unmapped_policy)
        for frame in pkg.frames
    ]

    new_mapping = CharacterMapping(
        character_id=character_id,
        rig_profile_id=rig_profile.profile_id,
        retarget_profile_id=retarget_profile.profile_id,
        channel_overrides=list(pkg.character_mapping.channel_overrides) if pkg.character_mapping else [],
    )

    return SemanticPerformancePackage(
        schema_version=pkg.schema_version,
        source=pkg.source,
        frames=new_frames,
        character_mapping=new_mapping,
        repair_layers=list(pkg.repair_layers),
        provenance=pkg.provenance,
    )


def _retarget_frame(
    frame: PerformanceFrame,
    rig: RigProfile,
    profile: RetargetProfile,
    unmapped_policy: str,
) -> PerformanceFrame:
    out_channels: list[FaceChannel] = []

    for source_ch in frame.face_channels:
        mapping = profile.mapping_for(source_ch.name)

        if mapping is None:
            if unmapped_policy == "passthrough":
                out_channels.append(source_ch)
            elif unmapped_policy == "zero":
                out_channels.append(FaceChannel(name=source_ch.name, value=0.0, confidence=Confidence(0.0, reason="unmapped")))
            # else "drop" → skip
            continue

        raw_value = mapping.apply(source_ch.value)

        # Clamp to target control's declared range if the control is known
        control = rig.control_by_name(mapping.target_name)
        if control:
            raw_value = max(control.min_value, min(control.max_value, raw_value))

        out_channels.append(
            FaceChannel(
                name=mapping.target_name,
                value=raw_value,
                confidence=source_ch.confidence,
            )
        )

    return PerformanceFrame(
        timecode=frame.timecode,
        head_pose=frame.head_pose,
        face_channels=out_channels,
        eye_gaze=frame.eye_gaze,
        body_joints=list(frame.body_joints),
        audio_alignments=list(frame.audio_alignments),
    )


def list_unmapped_channels(
    pkg: SemanticPerformancePackage,
    retarget_profile: RetargetProfile,
) -> set[str]:
    """Return channel names that have no mapping in *retarget_profile*."""
    mapped_sources = {m.source_name for m in retarget_profile.channel_mappings}
    return pkg.face_channel_names() - mapped_sources


def list_missing_targets(
    rig_profile: RigProfile,
    retarget_profile: RetargetProfile,
) -> set[str]:
    """Return target control names referenced by the profile but absent in the rig."""
    target_names = {c.name for c in rig_profile.facial_controls}
    mapped_targets = {m.target_name for m in retarget_profile.channel_mappings}
    return mapped_targets - target_names
