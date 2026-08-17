from __future__ import annotations

import argparse
from pathlib import Path
import sys

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 (Ubuntu 22.04)
    import tomli as tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wirewizard_gui.metadata import APP_VERSION  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Check release version consistency")
    parser.add_argument("--expected")
    args = parser.parse_args()

    if not ((3, 10, 1) <= sys.version_info[:3] < (3, 15, 0)):
        current = ".".join(str(part) for part in sys.version_info[:3])
        print(
            f"Unsupported Python {current}; use Python 3.10.1 through 3.14.x.",
            file=sys.stderr,
        )
        return 2

    pyproject = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    project_version = str(pyproject["project"]["version"])
    versions = {
        "wirewizard_gui.metadata": APP_VERSION,
        "pyproject.toml": project_version,
    }
    if args.expected is not None:
        versions["build argument"] = args.expected

    unique = set(versions.values())
    if len(unique) != 1:
        details = ", ".join(f"{source}={value}" for source, value in versions.items())
        print(f"Version mismatch: {details}", file=sys.stderr)
        return 1

    print(APP_VERSION)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
