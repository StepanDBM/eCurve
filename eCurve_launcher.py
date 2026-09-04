# eCurve_launcher.py

import importlib

from maya import cmds

import eCurve_main_ui

WINDOW_INSTANCE = None


def launch():
    """
    Launch eCurve UI.
    """

    global WINDOW_INSTANCE

    importlib.reload(eCurve_main_ui)

    try:
        if WINDOW_INSTANCE:
            WINDOW_INSTANCE.close()
            WINDOW_INSTANCE.deleteLater()
    except:
        pass

    WINDOW_INSTANCE = eCurve_main_ui.ECurveMainUI()
    WINDOW_INSTANCE.show()

    return WINDOW_INSTANCE