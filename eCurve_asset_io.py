# eCurve_asset_io.py

import json
import os
import re

from maya import cmds

try:
    from PySide6 import QtCore
except ImportError:
    from PySide2 import QtCore

from eCurve_drawables import ECurveAsset, ECurveStroke


ASSET_FORMAT = "eCurveAsset"
ASSET_VERSION = 1
ASSET_EXTENSION = ".ecurve"

ASSET_DIRECTORY = os.path.join(
    cmds.internalVar(userAppDir=True),
    "eCurve",
    "assets"
)


def ensure_asset_directory():
    if not os.path.isdir(ASSET_DIRECTORY):
        os.makedirs(ASSET_DIRECTORY)

    return ASSET_DIRECTORY


def sanitize_asset_name(name):
    name = str(name).strip()
    name = re.sub(r'[<>:"/\\|?*]+', "_", name)
    name = re.sub(r"\s+", " ", name)
    name = name.strip(" ._")

    return name or "Untitled"


def unique_asset_name(name, directory=None):
    directory = directory or ensure_asset_directory()
    base_name = sanitize_asset_name(name)
    existing_names = {
        os.path.splitext(filename)[0].lower()
        for filename in os.listdir(directory)
        if filename.lower().endswith(ASSET_EXTENSION)
    }

    if base_name.lower() not in existing_names:
        return base_name

    index = 2

    while True:
        candidate = "{}_{:02d}".format(base_name, index)

        if candidate.lower() not in existing_names:
            return candidate

        index += 1


def asset_file_path(name, directory=None):
    directory = directory or ensure_asset_directory()
    return os.path.join(
        directory,
        sanitize_asset_name(name) + ASSET_EXTENSION
    )


def asset_to_data(asset):
    return {
        "format": ASSET_FORMAT,
        "version": ASSET_VERSION,
        "name": asset.name,
        "asset_type": asset.asset_type,
        "primitive_type": asset.primitive_type,
        "metadata": dict(asset.metadata),
        "strokes": [
            {
                "closed": stroke.closed,
                "points": [
                    [point.x(), point.y()]
                    for point in stroke.points
                ]
            }
            for stroke in asset.strokes
            if stroke.points
        ]
    }


def asset_from_data(data):
    if not isinstance(data, dict):
        raise ValueError("Asset data must be a dictionary.")

    if data.get("format") != ASSET_FORMAT:
        raise ValueError("Unsupported eCurve asset format.")

    version = int(data.get("version", 0))

    if version != ASSET_VERSION:
        raise ValueError(
            "Unsupported eCurve asset version: {}".format(version)
        )

    name = sanitize_asset_name(data.get("name", "Untitled"))
    stroke_data = data.get("strokes", [])

    if not isinstance(stroke_data, list):
        raise ValueError("Asset strokes must be a list.")

    strokes = []

    for index, item in enumerate(stroke_data):
        if not isinstance(item, dict):
            raise ValueError(
                "Invalid stroke data at index {}.".format(index)
            )

        point_data = item.get("points", [])

        if not isinstance(point_data, list):
            raise ValueError(
                "Invalid point list at stroke {}.".format(index)
            )

        points = []

        for point_index, point in enumerate(point_data):
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                raise ValueError(
                    "Invalid point {} in stroke {}.".format(
                        point_index,
                        index
                    )
                )

            points.append(QtCore.QPointF(
                float(point[0]),
                float(point[1])
            ))

        if not points:
            continue

        stroke = ECurveStroke(
            points=points,
            closed=bool(item.get("closed", False))
        )
        stroke.edited = True
        strokes.append(stroke)

    asset = ECurveAsset(
        name=name,
        strokes=strokes,
        asset_type=data.get("asset_type", "custom"),
        primitive_type=data.get("primitive_type")
    )

    metadata = data.get("metadata", {})

    if isinstance(metadata, dict):
        asset.metadata = dict(metadata)

    return asset


def save_asset(asset, name=None, directory=None):
    if not isinstance(asset, ECurveAsset):
        raise TypeError("Expected ECurveAsset.")

    if asset.is_empty():
        raise ValueError("Cannot save an empty asset.")

    directory = directory or ensure_asset_directory()
    unique_name = unique_asset_name(name or asset.name, directory)

    asset.name = unique_name
    file_path = asset_file_path(unique_name, directory)
    temporary_path = file_path + ".tmp"
    data = asset_to_data(asset)

    with open(temporary_path, "w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=4)

    os.replace(temporary_path, file_path)
    return file_path


def load_asset(file_path):
    with open(file_path, "r", encoding="utf-8") as stream:
        data = json.load(stream)

    asset = asset_from_data(data)
    asset.metadata["file_path"] = file_path
    return asset


def load_asset_library(directory=None):
    directory = directory or ensure_asset_directory()
    assets = []

    for filename in sorted(os.listdir(directory), key=str.lower):
        if not filename.lower().endswith(ASSET_EXTENSION):
            continue

        file_path = os.path.join(directory, filename)

        try:
            asset = load_asset(file_path)
            assets.append(asset)

        except Exception as error:
            cmds.warning(
                "eCurve: Could not load '{}': {}".format(
                    file_path,
                    error
                )
            )

    return assets