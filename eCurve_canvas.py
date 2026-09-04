# eCurve_canvas.py
try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets

import math


class ECurveStroke:
    def __init__(self, name, points=None):
        self.name = name
        self.raw_points = list(points or [])
        self.points = list(points or [])
        self.visible = True
        self.selected = False
        self.closed = False

    def simplify(self, tolerance):
        if len(self.raw_points) < 3:
            self.points = list(self.raw_points)
            return

        self.points = douglas_peucker(self.raw_points, tolerance)

    def set_points(self, points):
        self.raw_points = list(points)
        self.points = list(points)


class ECurveCanvas(QtWidgets.QWidget):
    strokeCreated = QtCore.Signal(object)
    strokeSelected = QtCore.Signal(object)
    strokesChanged = QtCore.Signal()
    zoomChanged = QtCore.Signal(float)

    TOOL_PENCIL = "pencil"
    TOOL_EDIT = "edit"

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setMinimumSize(256, 256)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding
        )
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        self.strokes = []
        self.active_stroke = None
        self.selected_stroke = None

        self.current_tool = self.TOOL_PENCIL
        self.simplify_tolerance = 2.0
        self.minimum_point_distance = 1.5

        self.zoom = 1.0
        self.minimum_zoom = 0.1
        self.maximum_zoom = 10.0
        self.zoom_step = 1.2

        self.pan = QtCore.QPointF(0.0, 0.0)
        self.is_panning = False
        self.last_pan_position = QtCore.QPointF()

        self.background_color = QtGui.QColor(34, 34, 34)
        self.grid_color = QtGui.QColor(50, 50, 50)
        self.axis_color = QtGui.QColor(75, 75, 75)
        self.stroke_color = QtGui.QColor(210, 210, 210)
        self.selected_color = QtGui.QColor(70, 170, 255)
        self.active_color = QtGui.QColor(255, 180, 60)


    def _update_cursor(self):
        if self.is_panning:
            cursor = QtCore.Qt.ClosedHandCursor
        elif self.current_tool == self.TOOL_PENCIL:
            cursor = QtCore.Qt.CrossCursor
        else:
            cursor = QtCore.Qt.ArrowCursor

        self.setCursor(cursor)

    def set_tool(self, tool):
        if tool not in (self.TOOL_PENCIL, self.TOOL_EDIT):
            raise ValueError("Unsupported canvas tool: {}".format(tool))

        self.current_tool = tool
        self._update_cursor()

    # ------------------------------------------------------------------
    # Zoom in/out methods and view transformation methods
    # ------------------------------------------------------------------
    def view_center(self):
        return QtCore.QPointF(self.width() * 0.5, self.height() * 0.5)

    def canvas_to_view(self, point):
        center = self.view_center()
        return center + self.pan + point * self.zoom

    def view_to_canvas(self, point):
        center = self.view_center()
        return (point - center - self.pan) / self.zoom
    
    def wheelEvent(self, event):
        position = event_position(event)

        if event.angleDelta().y() > 0:
            self.set_zoom(self.zoom * self.zoom_step, position)
        else:
            self.set_zoom(self.zoom / self.zoom_step, position)

        event.accept()

    # ------------------------------------------------------------------
    # Strokes management methods
    # ------------------------------------------------------------------

    def set_simplify_tolerance(self, tolerance):
        self.simplify_tolerance = max(0.0, float(tolerance))

    def get_visible_strokes(self):
        return [stroke for stroke in self.strokes if stroke.visible]

    def get_selected_stroke(self):
        return self.selected_stroke

    def set_stroke_visibility(self, stroke, visible):
        if stroke not in self.strokes:
            return

        stroke.visible = bool(visible)
        self.update()
        self.strokesChanged.emit()

    def select_stroke(self, stroke):
        if stroke is not None and stroke not in self.strokes:
            return

        for item in self.strokes:
            item.selected = item is stroke

        self.selected_stroke = stroke
        self.update()
        self.strokeSelected.emit(stroke)

    def delete_stroke(self, stroke):
        if stroke not in self.strokes:
            return

        self.strokes.remove(stroke)

        if self.selected_stroke is stroke:
            self.selected_stroke = None
            self.strokeSelected.emit(None)

        self.update()
        self.strokesChanged.emit()

    def delete_selected_stroke(self):
        if self.selected_stroke:
            self.delete_stroke(self.selected_stroke)

    def clear_strokes(self):
        self.strokes.clear()
        self.active_stroke = None
        self.selected_stroke = None
        self.update()
        self.strokeSelected.emit(None)
        self.strokesChanged.emit()

    def mousePressEvent(self, event):
        position = event_position(event)

        if event.button() == QtCore.Qt.MiddleButton:
            self.is_panning = True
            self.last_pan_position = position
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            event.accept()
            return

        if event.button() != QtCore.Qt.LeftButton:
            return super().mousePressEvent(event)

        canvas_position = self.view_to_canvas(position)

        if self.current_tool == self.TOOL_PENCIL:
            self._begin_stroke(canvas_position)
        elif self.current_tool == self.TOOL_EDIT:
            threshold = 7.0 / self.zoom
            self.select_stroke(self.stroke_at(canvas_position, threshold))

        event.accept()

    def mouseMoveEvent(self, event):
        position = event_position(event)

        if self.is_panning:
            delta = position - self.last_pan_position
            self.pan += delta
            self.last_pan_position = position
            self.update()
            event.accept()
            return

        if not self.active_stroke:
            return super().mouseMoveEvent(event)

        if not event.buttons() & QtCore.Qt.LeftButton:
            return super().mouseMoveEvent(event)

        self._append_stroke_point(self.view_to_canvas(position))
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MiddleButton and self.is_panning:
            self.is_panning = False
            self._update_cursor()
            event.accept()
            return

        if event.button() == QtCore.Qt.LeftButton and self.active_stroke:
            self._finish_stroke()
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace):
            self.delete_selected_stroke()
            event.accept()
            return

        super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), self.background_color)

        painter.save()
        painter.translate(self.view_center() + self.pan)
        painter.scale(self.zoom, self.zoom)

        self._draw_grid(painter)

        for stroke in self.strokes:
            if stroke.visible:
                self._draw_stroke(painter, stroke)

        if self.active_stroke:
            self._draw_stroke(painter, self.active_stroke, active=True)

        painter.restore()

    def stroke_at(self, position, threshold=7.0):
        closest_stroke = None
        closest_distance = float("inf")

        for stroke in reversed(self.strokes):
            if not stroke.visible or len(stroke.points) < 2:
                continue

            distance = polyline_distance(position, stroke.points)

            if distance <= threshold and distance < closest_distance:
                closest_stroke = stroke
                closest_distance = distance

        return closest_stroke

    def _begin_stroke(self, position):
        name = "Curve_{:02d}".format(len(self.strokes) + 1)
        self.active_stroke = ECurveStroke(name, [position])
        self.update()

    def _append_stroke_point(self, position):
        points = self.active_stroke.raw_points
        minimum_distance = self.minimum_point_distance / self.zoom

        if points and point_distance(points[-1], position) < minimum_distance:
            return

        points.append(position)
        self.active_stroke.points = list(points)
        self.update()

    def _finish_stroke(self):
        stroke = self.active_stroke
        self.active_stroke = None

        if len(stroke.raw_points) < 2:
            self.update()
            return

        stroke.simplify(self.simplify_tolerance / self.zoom)
        self.strokes.append(stroke)
        self.select_stroke(stroke)

        self.strokeCreated.emit(stroke)
        self.strokesChanged.emit()
        self.update()

    def _draw_grid(self, painter):
        view_rect = self.rect()
        top_left = self.view_to_canvas(QtCore.QPointF(view_rect.topLeft()))
        bottom_right = self.view_to_canvas(QtCore.QPointF(view_rect.bottomRight()))

        left = min(top_left.x(), bottom_right.x())
        right = max(top_left.x(), bottom_right.x())
        top = min(top_left.y(), bottom_right.y())
        bottom = max(top_left.y(), bottom_right.y())

        spacing = 16.0
        start_x = math.floor(left / spacing) * spacing
        start_y = math.floor(top / spacing) * spacing

        grid_pen = QtGui.QPen(self.grid_color, 1.0 / self.zoom)
        painter.setPen(grid_pen)

        x = start_x
        while x <= right:
            painter.drawLine(QtCore.QPointF(x, top), QtCore.QPointF(x, bottom))
            x += spacing

        y = start_y
        while y <= bottom:
            painter.drawLine(QtCore.QPointF(left, y), QtCore.QPointF(right, y))
            y += spacing

        axis_pen = QtGui.QPen(self.axis_color, 1.0 / self.zoom)
        painter.setPen(axis_pen)
        painter.drawLine(QtCore.QPointF(0.0, top), QtCore.QPointF(0.0, bottom))
        painter.drawLine(QtCore.QPointF(left, 0.0), QtCore.QPointF(right, 0.0))

    def _draw_stroke(self, painter, stroke, active=False):
        points = stroke.raw_points if active else stroke.points

        if not points:
            return

        if active:
            color = self.active_color
        elif stroke.selected:
            color = self.selected_color
        else:
            color = self.stroke_color

        painter.setPen(QtGui.QPen(
            color,
            2.0 / self.zoom,
            QtCore.Qt.SolidLine,
            QtCore.Qt.RoundCap,
            QtCore.Qt.RoundJoin
        ))

        if len(points) == 1:
            painter.drawPoint(points[0])
            return

        path = QtGui.QPainterPath(points[0])

        for point in points[1:]:
            path.lineTo(point)

        if stroke.closed:
            path.closeSubpath()

        painter.drawPath(path)


def event_position(event):
    if hasattr(event, "position"):
        position = event.position()
    else:
        position = event.localPos()

    return QtCore.QPointF(position.x(), position.y())


def point_distance(point_a, point_b):
    return math.hypot(point_b.x() - point_a.x(), point_b.y() - point_a.y())


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


def polyline_distance(point, points):
    if not points:
        return float("inf")

    if len(points) == 1:
        return point_distance(point, points[0])

    return min(
        point_segment_distance(point, points[index], points[index + 1])
        for index in range(len(points) - 1)
    )


def douglas_peucker(points, tolerance):
    if len(points) < 3 or tolerance <= 0.0:
        return list(points)

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
        return [start, end]

    left = douglas_peucker(points[:split_index + 1], tolerance)
    right = douglas_peucker(points[split_index:], tolerance)

    return left[:-1] + right