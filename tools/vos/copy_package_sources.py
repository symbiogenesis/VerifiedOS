# SPDX-License-Identifier: Apache-2.0
"""Inputs to the [standalone copy recipe](../../docs/implementation/contracts/fixed-packages.md#standalone-copy-service-source-recipe)."""

from pathlib import Path
from typing import Final

from vos import python_dependencies, sailbundle

C_FILES: Final = (
    "src/package_unit.c", "src/copy_service.c", "src/target_layout.c",
    "include/vos_copy_service.h", "include/vos_copy_atomic.h",
    "include/vos_copy_notification.h",
)
ADAPTERS: Final = ("src/atomic_target.s", "src/notification_target.s")
DATA_INPUTS: Final = (
    "interfaces/ring-reference.json", "interfaces/device-registers.json",
    "interfaces/device-registers.schema.json", "model/config/verifiedos.json",
    sailbundle.BUNDLE, "model/model/sys/platform.sail", "model/model/sys/rot.sail",
    "model/model/sys/block_device.sail", "tools/pyproject.toml", "tools/uv.lock",
)
ENTRYPOINTS: Final = ("tools/vos/copy_package.py", "tools/vos/cli/copy_service.py")


def source_paths(root: Path) -> tuple[str, ...]:
    """Share recipe declarations while reading the selected checkout's imports."""
    return tuple(sorted({*(f"copy-service/{name}" for name in (*C_FILES, *ADAPTERS)),
                         *DATA_INPUTS, *python_dependencies.sources(root, ENTRYPOINTS)}))
