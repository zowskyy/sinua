from humanforge.adapters.base import (
    AdapterError,
    DestinationAdapter,
    ExportCheckResult,
    ExportValidationReport,
    SourceAdapter,
)
from humanforge.adapters.registry import (
    find_destination_adapter,
    find_source_adapter,
    list_destination_adapters,
    list_source_adapters,
    register_destination,
    register_source,
)

# Trigger adapter self-registration
import humanforge.adapters.source.curves   # noqa: F401
import humanforge.adapters.source.video    # noqa: F401
import humanforge.adapters.source.audio    # noqa: F401
import humanforge.adapters.destination.json_export  # noqa: F401
import humanforge.adapters.destination.csv_export   # noqa: F401
import humanforge.adapters.destination.blender      # noqa: F401
import humanforge.adapters.destination.gltf         # noqa: F401
import humanforge.adapters.destination.fbx          # noqa: F401
import humanforge.adapters.source.bvh               # noqa: F401
import humanforge.adapters.destination.bvh          # noqa: F401
import humanforge.adapters.destination.unreal       # noqa: F401
import humanforge.adapters.destination.unity        # noqa: F401
import humanforge.adapters.destination.godot        # noqa: F401
import humanforge.adapters.destination.maya         # noqa: F401
