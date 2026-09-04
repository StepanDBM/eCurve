# eCurve_storage.py

import json
import math
import os
import re
import xml.etree.ElementTree as ET

from maya import cmds

try:
    from PySide6 import QtCore
except ImportError:
    from PySide2 import QtCore

from eCurve_canvas import ECurveStroke


ECURVE_STORAGE_NODE = "eCurve_DATA"
ECURVE_STORAGE_ATTR = "curveDataJson"
ECURVE_STORAGE_VERSION = 1

SVG_NAMESPACE = "http://www.w3.org/2000/svg"
ECURVE_NAMESPACE = "https://eCurve.dev/schema/1"

ET.register_namespace("", SVG_NAMESPACE)
ET.register_namespace("ecurve", ECURVE_NAMESPACE)


class ECurveStorage:
    FILE_EXTENSION = ".svg"

    def __init__(self, canvas):
        self.canvas = canvas

    # -----------------------------------------------------
    # Collect / Apply
    # -----------------------------------------------------

    def collect_data(self):
        curves = []

        for stroke in self.canvas.strokes:
            curves.append({
                "name": str(stroke.name),
                "raw_points": self._serialize_points(stroke.raw_points),
                "points": self._serialize_points(stroke.points),
                "visible": bool(stroke.visible),
                "closed": bool(stroke.closed),
            })

        return {
            "version": ECURVE_STORAGE_VERSION,
            "curves": curves,
            "settings": {
                "zoom": float(self.canvas.zoom),
                "pan": [
                    float(self.canvas.pan.x()),
                    float(self.canvas.pan.y()),
                ],
                "simplify_tolerance": float(self.canvas.simplify_tolerance),
            },
        }

    def apply_data(self, data):
        if not data:
            cmds.warning("[eCurve] No curve data to apply.")
            return False

        curves = data.get("curves", [])
        settings = data.get("settings", {})

        self.canvas.clear_strokes()
        self.canvas.blockSignals(True)

        try:
            for index, curve_data in enumerate(curves):
                points = self._deserialize_points(curve_data.get("points", []))
                raw_points = self._deserialize_points(
                    curve_data.get("raw_points", [])
                )

                if not points and raw_points:
                    points = list(raw_points)

                if not raw_points and points:
                    raw_points = list(points)

                if len(points) < 2:
                    continue

                stroke = ECurveStroke(
                    curve_data.get("name", "Curve_{:02d}".format(index + 1)),
                    raw_points,
                )

                stroke.points = points
                stroke.visible = bool(curve_data.get("visible", True))
                stroke.closed = bool(curve_data.get("closed", False))
                stroke.selected = False

                self.canvas.strokes.append(stroke)

            self._apply_settings(settings)
        finally:
            self.canvas.blockSignals(False)

        self.canvas.active_stroke = None
        self.canvas.selected_stroke = None
        self.canvas.update()
        self.canvas.strokeSelected.emit(None)
        self.canvas.strokesChanged.emit()

        print("[eCurve] Applied {} curve(s).".format(len(self.canvas.strokes)))
        return True

    def _apply_settings(self, settings):
        tolerance = settings.get("simplify_tolerance")

        if tolerance is not None:
            self.canvas.simplify_tolerance = float(tolerance)

        zoom = settings.get("zoom")
        pan = settings.get("pan")

        if zoom is not None:
            self.canvas.zoom = max(
                self.canvas.minimum_zoom,
                min(self.canvas.maximum_zoom, float(zoom)),
            )

        if pan and len(pan) == 2:
            self.canvas.pan = QtCore.QPointF(
                float(pan[0]),
                float(pan[1]),
            )

        self.canvas.zoomChanged.emit(self.canvas.zoom)

    # -----------------------------------------------------
    # SVG file storage
    # -----------------------------------------------------

    def save_to_file(self, file_path):
        if not file_path:
            return False

        if not file_path.lower().endswith(self.FILE_EXTENSION):
            file_path += self.FILE_EXTENSION

        data = self.collect_data()

        try:
            root = self._build_svg(data)
            tree = ET.ElementTree(root)
            tree.write(file_path, encoding="utf-8", xml_declaration=True)

            print("[eCurve] Saved SVG file:")
            print("         path:", file_path)
            return True
        except Exception as exc:
            cmds.warning("[eCurve] Failed to save SVG file.")
            print("[eCurve] Failed to save SVG file:")
            print(exc)
            return False

    def load_from_file(self, file_path):
        if not file_path:
            return False

        if not os.path.exists(file_path):
            cmds.warning("[eCurve] SVG file does not exist.")
            print("[eCurve] SVG file does not exist:", file_path)
            return False

        try:
            root = ET.parse(file_path).getroot()
            data = self._read_ecurve_metadata(root)

            if not data:
                data = self._import_svg_geometry(root)

            if not data or not data.get("curves"):
                cmds.warning("[eCurve] No supported curves found in SVG.")
                return False

            result = self.apply_data(data)

            if result:
                print("[eCurve] Loaded SVG file:")
                print("         path:", file_path)

            return result
        except Exception as exc:
            cmds.warning("[eCurve] Failed to load SVG file.")
            print("[eCurve] Failed to load SVG file:")
            print(exc)
            return False

    def _build_svg(self, data):
        bounds = self._calculate_bounds()

        minimum_x = bounds[0]
        minimum_y = bounds[1]
        width = bounds[2]
        height = bounds[3]

        root = ET.Element(
            self._svg_tag("svg"),
            {
                "version": "1.1",
                "width": self._number(width),
                "height": self._number(height),
                "viewBox": "{} {} {} {}".format(
                    self._number(minimum_x),
                    self._number(minimum_y),
                    self._number(width),
                    self._number(height),
                ),
            },
        )

        title = ET.SubElement(root, self._svg_tag("title"))
        title.text = "eCurve drawing"

        metadata = ET.SubElement(root, self._svg_tag("metadata"))
        project_data = ET.SubElement(
            metadata,
            "{{{}}}projectData".format(ECURVE_NAMESPACE),
        )
        project_data.text = json.dumps(
            data,
            separators=(",", ":"),
            sort_keys=True,
        )

        group = ET.SubElement(
            root,
            self._svg_tag("g"),
            {
                "fill": "none",
                "stroke": "#ffffff",
                "stroke-width": "2",
                "stroke-linecap": "round",
                "stroke-linejoin": "round",
            },
        )

        for index, stroke in enumerate(self.canvas.strokes):
            if len(stroke.points) < 2:
                continue

            attributes = {
                "id": self._safe_svg_id(stroke.name, index),
                "d": self._points_to_svg_path(stroke.points, stroke.closed),
                "{{{}}}name".format(ECURVE_NAMESPACE): stroke.name,
                "{{{}}}visible".format(ECURVE_NAMESPACE): str(
                    stroke.visible
                ).lower(),
            }

            if not stroke.visible:
                attributes["display"] = "none"

            ET.SubElement(group, self._svg_tag("path"), attributes)

        return root

    def _read_ecurve_metadata(self, root):
        project_data_tag = "{{{}}}projectData".format(ECURVE_NAMESPACE)
        project_data = root.find(".//{}".format(project_data_tag))

        if project_data is None or not project_data.text:
            return None

        return json.loads(project_data.text)

    # -----------------------------------------------------
    # Basic generic SVG import
    # -----------------------------------------------------

    def _import_svg_geometry(self, root):
        curves = []
        curve_index = 1

        for element in root.iter():
            tag = self._local_tag(element.tag)

            if tag == "path":
                point_groups = self._parse_svg_path(element.get("d", ""))

                for points, closed in point_groups:
                    if len(points) < 2:
                        continue

                    curves.append(
                        self._svg_curve_data(
                            element,
                            points,
                            closed,
                            curve_index,
                        )
                    )
                    curve_index += 1

            elif tag in ("polyline", "polygon"):
                points = self._parse_svg_points(element.get("points", ""))

                if len(points) < 2:
                    continue

                curves.append(
                    self._svg_curve_data(
                        element,
                        points,
                        tag == "polygon",
                        curve_index,
                    )
                )
                curve_index += 1

            elif tag == "line":
                points = [
                    QtCore.QPointF(
                        float(element.get("x1", 0.0)),
                        float(element.get("y1", 0.0)),
                    ),
                    QtCore.QPointF(
                        float(element.get("x2", 0.0)),
                        float(element.get("y2", 0.0)),
                    ),
                ]

                curves.append(
                    self._svg_curve_data(
                        element,
                        points,
                        False,
                        curve_index,
                    )
                )
                curve_index += 1

        if not curves:
            return None

        curves = self._center_imported_curves(curves)

        return {
            "version": ECURVE_STORAGE_VERSION,
            "curves": curves,
            "settings": {
                "zoom": 1.0,
                "pan": [0.0, 0.0],
                "simplify_tolerance": float(
                    self.canvas.simplify_tolerance
                ),
            },
        }

    def _parse_svg_path(self, path_data):
        tokens = re.findall(
            r"[MmLlHhVvZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?",
            path_data,
        )

        paths = []
        points = []
        current = QtCore.QPointF(0.0, 0.0)
        start = QtCore.QPointF(0.0, 0.0)
        command = None
        index = 0
        closed = False

        while index < len(tokens):
            token = tokens[index]

            if re.match(r"[A-Za-z]", token):
                command = token
                index += 1

                if command in ("Z", "z"):
                    closed = True

                    if points:
                        paths.append((points, closed))

                    points = []
                    closed = False
                    current = QtCore.QPointF(start)
                    command = None

                continue

            if command is None:
                index += 1
                continue

            if command in ("M", "m", "L", "l"):
                if index + 1 >= len(tokens):
                    break

                x = float(tokens[index])
                y = float(tokens[index + 1])
                index += 2

                if command.islower():
                    x += current.x()
                    y += current.y()

                current = QtCore.QPointF(x, y)

                if command in ("M", "m"):
                    if points:
                        paths.append((points, False))

                    points = [current]
                    start = QtCore.QPointF(current)
                    command = "l" if command == "m" else "L"
                else:
                    points.append(current)

            elif command in ("H", "h"):
                x = float(tokens[index])
                index += 1

                if command == "h":
                    x += current.x()

                current = QtCore.QPointF(x, current.y())
                points.append(current)

            elif command in ("V", "v"):
                y = float(tokens[index])
                index += 1

                if command == "v":
                    y += current.y()

                current = QtCore.QPointF(current.x(), y)
                points.append(current)

            else:
                index += 1

        if points:
            paths.append((points, closed))

        return paths

    def _parse_svg_points(self, points_text):
        values = re.findall(
            r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?",
            points_text,
        )

        points = []

        for index in range(0, len(values) - 1, 2):
            points.append(
                QtCore.QPointF(
                    float(values[index]),
                    float(values[index + 1]),
                )
            )

        return points

    def _svg_curve_data(
        self,
        element,
        points,
        closed,
        curve_index,
    ):
        name_attribute = "{{{}}}name".format(ECURVE_NAMESPACE)
        name = element.get(
            name_attribute,
            element.get("id", "Curve_{:02d}".format(curve_index)),
        )

        visible_attribute = "{{{}}}visible".format(ECURVE_NAMESPACE)
        visible = element.get(visible_attribute, "true").lower() != "false"
        visible = visible and element.get("display") != "none"

        serialized_points = self._serialize_points(points)

        return {
            "name": name,
            "raw_points": list(serialized_points),
            "points": list(serialized_points),
            "visible": visible,
            "closed": bool(closed),
        }

    def _center_imported_curves(self, curves):
        all_points = []

        for curve in curves:
            all_points.extend(curve.get("points", []))

        if not all_points:
            return curves

        minimum_x = min(point[0] for point in all_points)
        maximum_x = max(point[0] for point in all_points)
        minimum_y = min(point[1] for point in all_points)
        maximum_y = max(point[1] for point in all_points)

        center_x = (minimum_x + maximum_x) * 0.5
        center_y = (minimum_y + maximum_y) * 0.5

        for curve in curves:
            for key in ("raw_points", "points"):
                curve[key] = [
                    [point[0] - center_x, point[1] - center_y]
                    for point in curve[key]
                ]

        return curves

    # -----------------------------------------------------
    # Scene node storage
    # -----------------------------------------------------

    def get_or_create_scene_node(self):
        if cmds.objExists(ECURVE_STORAGE_NODE):
            node = ECURVE_STORAGE_NODE
        else:
            node = cmds.createNode(
                "network",
                name=ECURVE_STORAGE_NODE,
            )

        if not cmds.attributeQuery(
            ECURVE_STORAGE_ATTR,
            node=node,
            exists=True,
        ):
            cmds.addAttr(
                node,
                longName=ECURVE_STORAGE_ATTR,
                dataType="string",
            )

        return node

    def save_to_scene(self):
        node = self.get_or_create_scene_node()
        json_text = json.dumps(
            self.collect_data(),
            separators=(",", ":"),
            sort_keys=True,
        )

        try:
            cmds.setAttr(
                "{}.{}".format(node, ECURVE_STORAGE_ATTR),
                json_text,
                type="string",
            )

            print("[eCurve] Saved drawing to Maya scene:")
            print("         node:", node)
            return True
        except Exception as exc:
            cmds.warning("[eCurve] Failed to save drawing to scene.")
            print("[eCurve] Failed to save drawing to scene:")
            print(exc)
            return False

    def load_from_scene(self):
        if not cmds.objExists(ECURVE_STORAGE_NODE):
            cmds.warning("[eCurve] No eCurve storage node found.")
            return False

        if not cmds.attributeQuery(
            ECURVE_STORAGE_ATTR,
            node=ECURVE_STORAGE_NODE,
            exists=True,
        ):
            cmds.warning("[eCurve] Storage node has no data attribute.")
            return False

        try:
            json_text = cmds.getAttr(
                "{}.{}".format(
                    ECURVE_STORAGE_NODE,
                    ECURVE_STORAGE_ATTR,
                )
            )

            if not json_text:
                cmds.warning("[eCurve] Scene drawing data is empty.")
                return False

            result = self.apply_data(json.loads(json_text))

            if result:
                print("[eCurve] Loaded drawing from Maya scene:")
                print("         node:", ECURVE_STORAGE_NODE)

            return result
        except Exception as exc:
            cmds.warning("[eCurve] Failed to load drawing from scene.")
            print("[eCurve] Failed to load drawing from scene:")
            print(exc)
            return False

    # -----------------------------------------------------
    # Utilities
    # -----------------------------------------------------

    def _calculate_bounds(self):
        points = [
            point
            for stroke in self.canvas.strokes
            for point in stroke.points
        ]

        if not points:
            return -128.0, -128.0, 256.0, 256.0

        minimum_x = min(point.x() for point in points)
        maximum_x = max(point.x() for point in points)
        minimum_y = min(point.y() for point in points)
        maximum_y = max(point.y() for point in points)

        padding = 16.0
        minimum_x -= padding
        minimum_y -= padding
        maximum_x += padding
        maximum_y += padding

        width = max(maximum_x - minimum_x, 1.0)
        height = max(maximum_y - minimum_y, 1.0)

        return minimum_x, minimum_y, width, height

    def _points_to_svg_path(self, points, closed=False):
        path_parts = [
            "M {} {}".format(
                self._number(points[0].x()),
                self._number(points[0].y()),
            )
        ]

        for point in points[1:]:
            path_parts.append(
                "L {} {}".format(
                    self._number(point.x()),
                    self._number(point.y()),
                )
            )

        if closed:
            path_parts.append("Z")

        return " ".join(path_parts)

    @staticmethod
    def _serialize_points(points):
        return [
            [float(point.x()), float(point.y())]
            for point in points
        ]

    @staticmethod
    def _deserialize_points(points):
        return [
            QtCore.QPointF(float(point[0]), float(point[1]))
            for point in points
            if len(point) >= 2
        ]

    @staticmethod
    def _safe_svg_id(name, index):
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name))

        if not safe_name or not safe_name[0].isalpha():
            safe_name = "curve_{}_{}".format(index + 1, safe_name)

        return safe_name

    @staticmethod
    def _number(value):
        if math.isclose(float(value), round(float(value))):
            return str(int(round(float(value))))

        return "{:.6f}".format(float(value)).rstrip("0").rstrip(".")

    @staticmethod
    def _svg_tag(name):
        return "{{{}}}{}".format(SVG_NAMESPACE, name)

    @staticmethod
    def _local_tag(tag):
        return tag.split("}", 1)[-1]