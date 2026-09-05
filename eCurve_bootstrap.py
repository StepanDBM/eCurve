# eCurve_bootstrap.py

import importlib

MODULE_NAMES = [
    "eCurve_drawables",
    "eCurve_primitives",
    "eCurve_thumbnail",
    "eCurve_asset_io",
    "eCurve_asset_strip",
    "eCurve_canvas",
    "eCurve_storage",
    "eCurve_main_ui",
    "eCurve_launcher",
]

modules = {}

for module_name in MODULE_NAMES:
    module = importlib.import_module(module_name)
    modules[module_name] = importlib.reload(module)
    print("Reloaded module: {}".format(module_name))

modules["eCurve_launcher"].launch()