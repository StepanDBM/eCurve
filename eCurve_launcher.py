# eCurve_launcher.py

import importlib

try:
    from PySide6 import QtWidgets
except ImportError:
    from PySide2 import QtWidgets

import eCurve_main_ui


WINDOW_INSTANCE = None
WINDOW_OBJECT_NAME = "eCurveMainWindow"


def _close_existing_windows():
    app = QtWidgets.QApplication.instance()

    if not app:
        return

    for widget in app.topLevelWidgets():
        if widget.objectName() != WINDOW_OBJECT_NAME:
            continue

        widget.close()
        widget.deleteLater()


def launch():
    """Launch a single instance of the eCurve UI."""

    global WINDOW_INSTANCE

    _close_existing_windows()
    importlib.reload(eCurve_main_ui)

    WINDOW_INSTANCE = eCurve_main_ui.ECurveMainUI()
    WINDOW_INSTANCE.show()
    WINDOW_INSTANCE.raise_()
    WINDOW_INSTANCE.activateWindow()

    return WINDOW_INSTANCE