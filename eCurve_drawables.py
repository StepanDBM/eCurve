# eCurve_drawables.py

try:
    from PySide6 import QtCore, QtGui
except ImportError:
    from PySide2 import QtCore, QtGui


class ECurveStroke:
    def __init__(self, points=None, closed=False, name="Curve"):
        self.name = str(name)
        self.raw_points = self._copy_points(points or [])
        self.points = self._copy_points(points or [])
        self.closed = bool(closed)
        self.edited = False

        self.visible = True
        self.selected = False
        self.asset = None

        self.horizontal_symmetry_enabled = True
        self.vertical_symmetry_enabled = True
        self.radial_symmetry_enabled = True
        self.radial_count_override = 0

    @staticmethod
    def _copy_points(points):
        return [QtCore.QPointF(point) for point in points]

    def copy(self):
        stroke = ECurveStroke(
            self.raw_points,
            closed=self.closed,
            name=self.name
        )
        stroke.points = self._copy_points(self.points)
        stroke.edited = self.edited
        stroke.visible = self.visible
        stroke.horizontal_symmetry_enabled = self.horizontal_symmetry_enabled
        stroke.vertical_symmetry_enabled = self.vertical_symmetry_enabled
        stroke.radial_symmetry_enabled = self.radial_symmetry_enabled
        stroke.radial_count_override = self.radial_count_override
        return stroke

    def simplify(self, tolerance):
        if self.edited:
            return

        if len(self.raw_points) < 3:
            self.points = self._copy_points(self.raw_points)
            return

        self.points = douglas_peucker(self.raw_points, tolerance)

    def make_editable(self):
        if self.edited:
            return

        self.raw_points = self._copy_points(self.points)
        self.edited = True

    def set_points(self, points, edited=False):
        self.points = self._copy_points(points)
        self.raw_points = self._copy_points(points)

        if edited:
            self.edited = True

    def set_point(self, index, point):
        if not 0 <= index < len(self.points):
            return False

        self.points[index] = QtCore.QPointF(point)
        self.raw_points = self._copy_points(self.points)
        self.edited = True
        return True

    def delete_point(self, index):
        if len(self.points) <= 2 or not 0 <= index < len(self.points):
            return False

        del self.points[index]
        self.raw_points = self._copy_points(self.points)
        self.edited = True
        return True

    def bounds(self):
        if not self.points:
            return QtCore.QRectF()

        return QtGui.QPolygonF(self.points).boundingRect()


class ECurveAsset:
    def __init__(
        self,
        name,
        strokes=None,
        asset_type="custom",
        primitive_type=None
    ):
        self.name = str(name)
        self.strokes = list(strokes or [])

        self.asset_type = str(asset_type)
        self.primitive_type = primitive_type

        self.visible = True
        self.selected = False

        self.horizontal_symmetry_enabled = True
        self.vertical_symmetry_enabled = True
        self.radial_symmetry_enabled = True
        self.radial_count_override = 0

        self.metadata = {}

        self._connect_strokes()

    def copy(self, name=None):
        asset = ECurveAsset(
            name or self.name,
            [stroke.copy() for stroke in self.strokes],
            self.asset_type,
            self.primitive_type
        )

        asset.visible = self.visible
        asset.horizontal_symmetry_enabled = self.horizontal_symmetry_enabled
        asset.vertical_symmetry_enabled = self.vertical_symmetry_enabled
        asset.radial_symmetry_enabled = self.radial_symmetry_enabled
        asset.radial_count_override = self.radial_count_override
        asset.metadata = dict(self.metadata)
        return asset
    
    def _connect_strokes(self):
        multiple_strokes = len(self.strokes) > 1

        for index, stroke in enumerate(self.strokes):
            stroke.asset = self

            if multiple_strokes:
                stroke.name = "{}_{:02d}".format(self.name, index + 1)
            else:
                stroke.name = self.name

    def iter_strokes(self):
        return iter(self.strokes)

    def all_points(self):
        return [
            point
            for stroke in self.strokes
            for point in stroke.points
        ]

    def all_raw_points(self):
        return [
            point
            for stroke in self.strokes
            for point in stroke.raw_points
        ]

    def bounds(self):
        points = self.all_points()

        if not points:
            return QtCore.QRectF()

        return QtGui.QPolygonF(points).boundingRect()

    def pivot(self):
        bounds = self.bounds()
        return bounds.center() if not bounds.isNull() else QtCore.QPointF()

    def simplify(self, tolerance):
        for stroke in self.strokes:
            stroke.simplify(tolerance)

    def make_editable(self):
        for stroke in self.strokes:
            stroke.make_editable()

    def is_empty(self):
        return not any(stroke.points for stroke in self.strokes)

    def is_closed(self):
        return bool(self.strokes) and all(
            stroke.closed
            for stroke in self.strokes
        )

    def point_count(self):
        return sum(len(stroke.points) for stroke in self.strokes)

    def raw_point_count(self):
        return sum(len(stroke.raw_points) for stroke in self.strokes)


def point_segment_distance(point, start, end):
    dx = end.x() - start.x()
    dy = end.y() - start.y()

    if dx == 0.0 and dy == 0.0:
        return point_distance(point, start)

    t = (
        (point.x() - start.x()) * dx +
        (point.y() - start.y()) * dy
    ) / (dx * dx + dy * dy)

    t = max(0.0, min(1.0, t))

    projection = QtCore.QPointF(
        start.x() + t * dx,
        start.y() + t * dy
    )
    return point_distance(point, projection)


def point_distance(point_a, point_b):
    dx = point_b.x() - point_a.x()
    dy = point_b.y() - point_a.y()
    return (dx * dx + dy * dy) ** 0.5


def douglas_peucker(points, tolerance):
    if len(points) < 3 or tolerance <= 0.0:
        return [QtCore.QPointF(point) for point in points]

    start = points[0]
    end = points[-1]
    maximum_distance = 0.0
    split_index = 0

    for index in range(1, len(points) - 1):
        distance = point_segment_distance(points[index], start, end)

        if distance > maximum_distance:
            maximum_distance = distance
            split_index = index

    if maximum_distance <= tolerance:
        return [QtCore.QPointF(start), QtCore.QPointF(end)]

    left = douglas_peucker(points[:split_index + 1], tolerance)
    right = douglas_peucker(points[split_index:], tolerance)
    return left[:-1] + right