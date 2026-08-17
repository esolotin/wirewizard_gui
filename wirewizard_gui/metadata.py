"""Application metadata shared by the runtime and packaging entry points."""

from __future__ import annotations

APP_NAME = "WireWizardGUI"
APP_ID = "wirewizardgui"
APP_VERSION = "0.1.0"
ORGANIZATION_NAME = "WireWizard"

# WireViz does not promise a stable Python API. Keep the version used by the
# in-process integration explicit and pin the same version in release builds.
WIREVIZ_VERSION = "0.4.1"

__version__ = APP_VERSION

__all__ = [
    "APP_ID",
    "APP_NAME",
    "APP_VERSION",
    "ORGANIZATION_NAME",
    "WIREVIZ_VERSION",
    "__version__",
]
