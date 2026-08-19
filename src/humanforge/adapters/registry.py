"""Adapter registry — discover and retrieve source/destination adapters.

Adapters self-register by calling register_source() or register_destination()
at import time (or can be registered programmatically).
"""
from __future__ import annotations

from pathlib import Path
from typing import Type

from humanforge.adapters.base import AdapterError, DestinationAdapter, SourceAdapter

_SOURCE_REGISTRY: dict[str, SourceAdapter] = {}
_DESTINATION_REGISTRY: dict[str, DestinationAdapter] = {}


def register_source(adapter: SourceAdapter) -> None:
    _SOURCE_REGISTRY[adapter.ADAPTER_ID] = adapter


def register_destination(adapter: DestinationAdapter) -> None:
    _DESTINATION_REGISTRY[adapter.ADAPTER_ID] = adapter


def source_by_id(adapter_id: str) -> SourceAdapter:
    try:
        return _SOURCE_REGISTRY[adapter_id]
    except KeyError:
        raise AdapterError(f"No source adapter registered with id {adapter_id!r}") from None


def destination_by_id(adapter_id: str) -> DestinationAdapter:
    try:
        return _DESTINATION_REGISTRY[adapter_id]
    except KeyError:
        raise AdapterError(f"No destination adapter registered with id {adapter_id!r}") from None


def find_source_adapter(source: str | Path) -> SourceAdapter:
    """Return the first registered source adapter that declares it can handle *source*."""
    for adapter in _SOURCE_REGISTRY.values():
        if adapter.can_handle(source):
            return adapter
    raise AdapterError(
        f"No registered source adapter can handle {str(source)!r}. "
        f"Registered adapters: {list(_SOURCE_REGISTRY)}"
    )


def find_destination_adapter(destination_type: str) -> DestinationAdapter:
    """Return the first registered destination adapter matching *destination_type*."""
    for adapter in _DESTINATION_REGISTRY.values():
        if adapter.DESTINATION_TYPE == destination_type:
            return adapter
    raise AdapterError(
        f"No registered destination adapter for type {destination_type!r}. "
        f"Registered adapters: {list(_DESTINATION_REGISTRY)}"
    )


def list_source_adapters() -> list[dict]:
    return [
        {
            "adapter_id": a.ADAPTER_ID,
            "adapter_version": a.ADAPTER_VERSION,
            "source_type": a.SOURCE_TYPE,
            "support_level": a.SUPPORT_LEVEL,
        }
        for a in _SOURCE_REGISTRY.values()
    ]


def list_destination_adapters() -> list[dict]:
    return [
        {
            "adapter_id": a.ADAPTER_ID,
            "adapter_version": a.ADAPTER_VERSION,
            "destination_type": a.DESTINATION_TYPE,
        }
        for a in _DESTINATION_REGISTRY.values()
    ]
