"""Compatibility launcher; the canonical application lives in the package."""

from wirewizard_gui.app import main


if __name__ == "__main__":
    raise SystemExit(main())
