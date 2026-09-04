# eCurve_bootstrap.py

import importlib

MODULE_NAMES = [
    "eCurve_canvas",
    "eCurve_main_ui",
    "eCurve_launcher",
]

modules = {}

for module_name in MODULE_NAMES:
    module = importlib.import_module(module_name)
    modules[module_name] = importlib.reload(module)
    print(f"Reloaded module: {module_name}")

modules["eCurve_launcher"].launch()