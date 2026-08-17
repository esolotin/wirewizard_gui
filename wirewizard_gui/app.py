from __future__ import annotations

import logging
import sys

from wirewizard_gui.metadata import APP_NAME, APP_VERSION, ORGANIZATION_NAME
from wirewizard_gui.runtime import (
    configure_bundled_graphviz,
    configure_logging,
    install_exception_handler,
)


logger = logging.getLogger("wirewizard_gui.app")


def main(argv: list[str] | None = None) -> int:
    log_path = configure_logging()
    install_exception_handler()
    configure_bundled_graphviz()

    # Delay Qt and UI imports until the process environment and crash log are
    # ready. This is important for windowed builds that have no console.
    from PySide6.QtWidgets import QApplication, QMessageBox

    from wirewizard_gui.services.session_service import SessionService
    from wirewizard_gui.ui.main_window import MainWindow

    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORGANIZATION_NAME)

    def show_exception(title: str, message: str) -> None:
        QMessageBox.critical(None, title, message)

    install_exception_handler(show_exception)
    window = MainWindow(session_service=SessionService())
    window.show()
    logger.info("Runtime log: %s", log_path)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
