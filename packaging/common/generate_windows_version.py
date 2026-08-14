from __future__ import annotations

import argparse
from pathlib import Path


TEMPLATE = """# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({version_tuple}),
    prodvers=({version_tuple}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'WireWizardGUI contributors'),
          StringStruct('FileDescription', 'WireWizardGUI'),
          StringStruct('FileVersion', '{version}'),
          StringStruct('InternalName', 'WireWizardGUI'),
          StringStruct('LegalCopyright', 'GNU GPL v3'),
          StringStruct('OriginalFilename', 'WireWizardGUI.exe'),
          StringStruct('ProductName', 'WireWizardGUI'),
          StringStruct('ProductVersion', '{version}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def version_tuple(version: str) -> tuple[int, int, int, int]:
    values = version.split(".")
    if not values or len(values) > 4 or any(not value.isdigit() for value in values):
        raise ValueError("Version must contain one to four numeric components")
    numbers = [int(value) for value in values]
    return tuple(numbers + [0] * (4 - len(numbers)))


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate PyInstaller Windows version metadata")
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    values = version_tuple(args.version)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        TEMPLATE.format(version=args.version, version_tuple=", ".join(map(str, values))),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
