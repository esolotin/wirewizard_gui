from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata


PROJECT_ROOT = Path(SPECPATH).resolve().parents[1]
ENTRY_POINT = PROJECT_ROOT / "wirewizard_gui" / "app.py"
if (PROJECT_ROOT / "__init__.py").exists():
    raise SystemExit(
        "The repository root must not be a Python package: remove the top-level "
        "__init__.py so it cannot shadow the canonical wirewizard_gui package."
    )

wireviz_datas, wireviz_binaries, wireviz_hiddenimports = collect_all("wireviz")

datas = list(wireviz_datas)
for distribution_name in (
    "wireviz",
    "PyYAML",
    "graphviz",
    "Pillow",
    "click",
    "PySide6",
    "PySide6_Essentials",
    "PySide6_Addons",
    "shiboken6",
):
    datas.extend(copy_metadata(distribution_name))
datas.extend(
    [
        (str(PROJECT_ROOT / "LICENSE"), "."),
        (str(PROJECT_ROOT / "THIRD_PARTY_NOTICES.md"), "."),
        (str(PROJECT_ROOT / "packaging" / "licenses" / "EPL-2.0.txt"), "licenses"),
    ]
)
binaries = list(wireviz_binaries)

graphviz_root_value = os.environ.get("WW_GRAPHVIZ_ROOT", "").strip()
if graphviz_root_value:
    graphviz_root = Path(graphviz_root_value).resolve()
    dot_names = ("dot.exe", "dot")
    if not graphviz_root.is_dir():
        raise SystemExit(f"WW_GRAPHVIZ_ROOT is not a directory: {graphviz_root}")
    if not any((graphviz_root / "bin" / name).is_file() for name in dot_names):
        raise SystemExit(f"Graphviz dot executable was not found under {graphviz_root / 'bin'}")
    datas.append((str(graphviz_root), "graphviz"))

icon_value = os.environ.get("WW_ICON_PATH", "").strip()
icon_path = str(Path(icon_value).resolve()) if icon_value else None
version_value = os.environ.get("WW_VERSION_FILE", "").strip()
version_path = str(Path(version_value).resolve()) if version_value and os.name == "nt" else None

hiddenimports = sorted(
    set(
        wireviz_hiddenimports
        + [
            "PySide6.QtSvg",
            "PySide6.QtSvgWidgets",
            "wirewizard_gui.metadata",
            "wirewizard_gui.runtime",
            "wirewizard_gui.services.wireviz_service",
            "wireviz.wireviz",
        ]
    )
)

a = Analysis(
    [str(ENTRY_POINT)],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WireWizardGUI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
    version=version_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="WireWizardGUI",
)
