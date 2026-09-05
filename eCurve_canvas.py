# eCurve_canvas.py
try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets

import math

from eCurve_drawables import ECurveAsset, ECurveStroke

class ECurveCanvas(QtWidgets.QWidget):
    strokeCreated = QtCore.Signal(object)
    strokeSelected = QtCore.Signal(object)
    strokesChanged = QtCore.Signal()
    zoomChanged = QtCore.Signal(float)
    transformOperationChanged = QtCore.Signal(str)

    TOOL_PENCIL = "pencil"
    TOOL_EDIT = "edit"
    TOOL_TRANSFORM = "transform"

    TRANSFORM_MOVE = "move"
    TRANSFORM_ROTATE = "rotate"
    TRANSFORM_SCALE = "scale"

    VALID_TOOLS = (
        TOOL_PENCIL,
        TOOL_EDIT,
        TOOL_TRANSFORM
    )

    VALID_TRANSFORMS = (
        TRANSFORM_MOVE,
        TRANSFORM_ROTATE,
        TRANSFORM_SCALE
    )

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setMinimumSize(256, 256)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding
        )
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        self.assets = []
        self.strokes = []
        self.active_stroke = None
        self.selected_stroke = None
        self.selected_strokes = []

        self.selected_point_index = None
        self.is_dragging_point = False
        self.point_hit_radius = 8.0

        self.transform_operation = self.TRANSFORM_MOVE
        self.is_transforming = False
        self.transform_start_position = QtCore.QPointF()
        self.transform_pivot = QtCore.QPointF()
        self.transform_start_points = {}

        self.is_pending_rect_select = False
        self.pending_rect_start = QtCore.QPointF()
        self.pending_rect_additive = False
        self.pending_rect_subtractive = False

        self.is_rect_selecting = False
        self.rect_select_start = QtCore.QPointF()
        self.rect_select_current = QtCore.QPointF()
        self.rect_select_additive = False
        self.rect_select_subtractive = False
        self.rect_select_threshold = 4.0

        self.rect_select_fill = QtGui.QColor(70, 170, 255, 35)
        self.rect_select_outline = QtGui.QColor(70, 170, 255, 220)

        self.current_tool = self.TOOL_PENCIL
        self.simplify_tolerance = 2.0
        self.minimum_point_distance = 1.5

        self.vertical_symmetry = False
        self.horizontal_symmetry = False
        self.radial_symmetry = False
        self.radial_count = 4

        self.symmetry_color = QtGui.QColor(110, 110, 110, 150)
        self.active_symmetry_color = QtGui.QColor(180, 125, 55, 160)

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
        if self.is_panning or self.is_dragging_point:
            cursor = QtCore.Qt.ClosedHandCursor

        elif self.is_transforming:
            if self.transform_operation == self.TRANSFORM_MOVE:
                cursor = QtCore.Qt.SizeAllCursor
            elif self.transform_operation == self.TRANSFORM_ROTATE:
                cursor = QtCore.Qt.CrossCursor
            else:
                cursor = QtCore.Qt.SizeFDiagCursor

        elif self.is_rect_selecting:
            cursor = QtCore.Qt.CrossCursor

        elif self.current_tool == self.TOOL_PENCIL:
            cursor = QtCore.Qt.CrossCursor

        elif self.current_tool == self.TOOL_TRANSFORM:
            cursor = QtCore.Qt.SizeAllCursor

        else:
            cursor = QtCore.Qt.ArrowCursor

        self.setCursor(cursor)

    def set_tool(self, tool):
        if tool not in self.VALID_TOOLS:
            raise ValueError("Unsupported canvas tool: {}".format(tool))

        self.current_tool = tool
        self.selected_point_index = None
        self.is_dragging_point = False
        self.is_transforming = False
        self.cancel_pending_rect_selection()
        self.cancel_rect_selection()
        self._update_cursor()
        self.update()

    def set_transform_operation(self, operation):
        if operation not in self.VALID_TRANSFORMS:
            raise ValueError(
                "Unsupported transform operation: {}".format(operation)
            )

        if operation == self.transform_operation:
            return

        self.transform_operation = operation
        self.transformOperationChanged.emit(operation)
        self._update_cursor()
        self.update()

    def set_vertical_symmetry(self, enabled):
        self.vertical_symmetry = bool(enabled)
        self.update()

    def set_horizontal_symmetry(self, enabled):
        self.horizontal_symmetry = bool(enabled)
        self.update()

    def set_radial_symmetry(self, enabled):
        self.radial_symmetry = bool(enabled)
        self.update()

    def set_radial_count(self, count):
        self.radial_count = max(2, int(count))
        self.update()

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
        
    def zoom_in(self):
        self.set_zoom(self.zoom * self.zoom_step)

    def zoom_out(self):
        self.set_zoom(self.zoom / self.zoom_step)

    def set_zoom(self, zoom, anchor=None):
        zoom = max(self.minimum_zoom, min(self.maximum_zoom, float(zoom)))

        if math.isclose(zoom, self.zoom):
            return

        if anchor is None:
            anchor = self.view_center()

        canvas_position = self.view_to_canvas(anchor)
        self.zoom = zoom
        self.pan = anchor - self.view_center() - canvas_position * self.zoom

        self.zoomChanged.emit(self.zoom)
        self.update()

    def reset_view(self):
        self.zoom = 1.0
        self.pan = QtCore.QPointF(0.0, 0.0)
        self.zoomChanged.emit(self.zoom)
        self.update()

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
        canvas_tolerance = self.simplify_tolerance / self.zoom

        for stroke in self.strokes:
            if not stroke.edited:
                stroke.simplify(canvas_tolerance)

        self.update()

    def get_visible_strokes(self):
        return [stroke for stroke in self.strokes if stroke.visible]

    def set_stroke_visibility(self, stroke, visible):
        if stroke not in self.strokes:
            return

        stroke.visible = bool(visible)
        self.update()
        self.strokesChanged.emit()

    def get_selected_stroke(self):
        return self.selected_stroke

    def get_selected_strokes(self):
        return list(self.selected_strokes)

    def clear_selection(self):
        for stroke in self.strokes:
            stroke.selected = False

        self.selected_strokes = []
        self.selected_stroke = None
        self.selected_point_index = None
        self.is_dragging_point = False

        self.strokeSelected.emit(None)
        self.update()



    # ------------------------------------------------------------------
    # Asset to stroke management methods
    # ------------------------------------------------------------------
    def get_selected_asset_strokes(self):
        result = []
        processed_assets = set()

        for selected_stroke in self.selected_strokes:
            asset = selected_stroke.asset

            if asset is None:
                if selected_stroke not in result:
                    result.append(selected_stroke)
                continue

            asset_key = id(asset)

            if asset_key in processed_assets:
                continue

            processed_assets.add(asset_key)

            for stroke in asset.strokes:
                if stroke in self.strokes and stroke not in result:
                    result.append(stroke)

        return result

    def create_asset_from_selection(self, name):
        source_strokes = self.get_selected_asset_strokes()

        if not source_strokes:
            return None

        all_points = [
            point
            for stroke in source_strokes
            for point in stroke.points
        ]

        if not all_points:
            return None

        bounds = QtGui.QPolygonF(all_points).boundingRect()
        pivot = bounds.center()
        asset_strokes = []

        for source_stroke in source_strokes:
            points = [
                QtCore.QPointF(
                    point.x() - pivot.x(),
                    point.y() - pivot.y()
                )
                for point in source_stroke.points
            ]

            if not points:
                continue

            stroke = ECurveStroke(
                points=points,
                closed=source_stroke.closed
            )
            stroke.edited = True
            asset_strokes.append(stroke)

        if not asset_strokes:
            return None

        asset = ECurveAsset(
            name=name,
            strokes=asset_strokes,
            asset_type="custom"
        )

        asset.metadata["source_stroke_count"] = len(asset_strokes)
        return asset

    def set_selected_strokes(self, strokes, active_stroke=None):
        selected = []

        for stroke in strokes:
            if stroke in self.strokes and stroke.visible and stroke not in selected:
                selected.append(stroke)

        for stroke in self.strokes:
            stroke.selected = stroke in selected

        self.selected_strokes = selected

        if active_stroke in selected:
            self.selected_stroke = active_stroke
        elif selected:
            self.selected_stroke = selected[-1]
        else:
            self.selected_stroke = None

        self.selected_point_index = None
        self.is_dragging_point = False
        self.strokeSelected.emit(self.selected_stroke)
        self.update()

    def select_stroke(self, stroke, additive=False, subtractive=False):
        if stroke is not None and stroke not in self.strokes:
            return

        if stroke is None:
            if not additive and not subtractive:
                self.clear_selection()
            return

        selected = list(self.selected_strokes)

        if subtractive:
            if stroke in selected:
                selected.remove(stroke)

            self.set_selected_strokes(selected)
            return

        if additive:
            if stroke not in selected:
                selected.append(stroke)

            self.set_selected_strokes(selected, active_stroke=stroke)
            return

        self.set_selected_strokes([stroke], active_stroke=stroke)

    def delete_stroke(self, stroke):
        if stroke not in self.strokes:
            return

        self.strokes.remove(stroke)

        if stroke.asset and stroke in stroke.asset.strokes:
            stroke.asset.strokes.remove(stroke)

        self._remove_empty_assets()

        selected = [
            item
            for item in self.selected_strokes
            if item is not stroke
        ]

        self.set_selected_strokes(selected)
        self.strokesChanged.emit()
        self.update()

    def delete_selected_stroke(self):
        self.delete_selected_strokes()

    def delete_selected_strokes(self):
        selected = list(self.selected_strokes)

        if not selected and self.selected_stroke:
            selected = [self.selected_stroke]

        if not selected:
            return

        for stroke in selected:
            if stroke not in self.strokes:
                continue

            self.strokes.remove(stroke)

            if stroke.asset and stroke in stroke.asset.strokes:
                stroke.asset.strokes.remove(stroke)

        self._remove_empty_assets()

        self.clear_selection()
        self.strokesChanged.emit()
        self.update()

    def clear_strokes(self):
        self.assets.clear()
        self.strokes.clear()
        self.active_stroke = None
        self.selected_stroke = None
        self.selected_strokes = []
        self.selected_point_index = None
        self.is_dragging_point = False
        self.is_transforming = False
        self.transform_start_points = {}

        self.cancel_pending_rect_selection()
        self.cancel_rect_selection()
        self.update()
        self.strokeSelected.emit(None)
        self.strokesChanged.emit()

    def visible_canvas_center(self):
        return self.view_to_canvas(self.view_center())

    def unique_asset_name(self, base_name):
        existing_names = {
            asset.name.lower()
            for asset in self.assets
        }

        if base_name.lower() not in existing_names:
            return base_name

        index = 2

        while True:
            candidate = "{}_{:02d}".format(base_name, index)

            if candidate.lower() not in existing_names:
                return candidate

            index += 1

    def unique_stroke_name(self, base_name):
        existing_names = {stroke.name for stroke in self.strokes}

        if base_name not in existing_names:
            return base_name

        index = 2

        while "{}_{:02d}".format(base_name, index) in existing_names:
            index += 1

        return "{}_{:02d}".format(base_name, index)

    def asset_strokes(self, stroke):
        if stroke is None:
            return []

        if stroke.asset is None:
            return [stroke]

        return [
            asset_stroke
            for asset_stroke in stroke.asset.strokes
            if asset_stroke in self.strokes
        ]

    def add_asset(self, asset, position=None, select=True):
        if not isinstance(asset, ECurveAsset):
            raise TypeError("Expected ECurveAsset, got {}".format(type(asset)))

        asset = asset.copy()
        asset.name = self.unique_asset_name(asset.name)
        asset._connect_strokes()

        if position is None:
            position = self.visible_canvas_center()
        else:
            position = QtCore.QPointF(position)

        asset_center = asset.pivot()
        offset = position - asset_center
        created_strokes = []

        for index, stroke in enumerate(asset.strokes):
            points = [point + offset for point in stroke.points]
            raw_points = [point + offset for point in stroke.raw_points]

            stroke.points = points
            stroke.raw_points = raw_points
            stroke.asset = asset

            if len(asset.strokes) == 1:
                stroke.name = self.unique_stroke_name(asset.name)
            else:
                stroke.name = self.unique_stroke_name(
                    "{}_{:02d}".format(asset.name, index + 1)
                )

            self.strokes.append(stroke)
            created_strokes.append(stroke)
            self.strokeCreated.emit(stroke)

        if not created_strokes:
            return []

        self.assets.append(asset)

        if select:
            self.set_selected_strokes(
                created_strokes,
                active_stroke=created_strokes[-1]
            )

        self.strokesChanged.emit()
        self.update()
        self.setFocus()
        return created_strokes

    def _remove_empty_assets(self):
        active_assets = {
            stroke.asset
            for stroke in self.strokes
            if stroke.asset is not None
        }

        self.assets = [
            asset
            for asset in self.assets
            if asset in active_assets
        ]

    # ------------------------------------------------------------------
    # Mouse methods
    # ------------------------------------------------------------------

    @staticmethod
    def is_additive_selection(event):
        return bool(event.modifiers() & QtCore.Qt.ShiftModifier)

    @staticmethod
    def is_subtractive_selection(event):
        return bool(event.modifiers() & QtCore.Qt.ControlModifier)

    def begin_pending_rect_selection(
        self,
        position,
        additive=False,
        subtractive=False
    ):
        self.is_pending_rect_select = True
        self.pending_rect_start = QtCore.QPointF(position)
        self.pending_rect_additive = bool(additive)
        self.pending_rect_subtractive = bool(subtractive)

    def cancel_pending_rect_selection(self):
        self.is_pending_rect_select = False
        self.pending_rect_start = QtCore.QPointF()
        self.pending_rect_additive = False
        self.pending_rect_subtractive = False

    def should_start_rect_selection(self, position):
        if not self.is_pending_rect_select:
            return False

        dx = position.x() - self.pending_rect_start.x()
        dy = position.y() - self.pending_rect_start.y()
        threshold = self.rect_select_threshold

        return dx * dx + dy * dy >= threshold * threshold

    def begin_rect_selection(
        self,
        position,
        additive=False,
        subtractive=False
    ):
        self.is_rect_selecting = True
        self.rect_select_start = QtCore.QPointF(position)
        self.rect_select_current = QtCore.QPointF(position)
        self.rect_select_additive = bool(additive)
        self.rect_select_subtractive = bool(subtractive)
        self._update_cursor()
        self.update()

    def update_rect_selection(self, position):
        if not self.is_rect_selecting:
            return

        self.rect_select_current = QtCore.QPointF(position)
        self.update()

    def cancel_rect_selection(self):
        self.is_rect_selecting = False
        self.rect_select_start = QtCore.QPointF()
        self.rect_select_current = QtCore.QPointF()
        self.rect_select_additive = False
        self.rect_select_subtractive = False
        self._update_cursor()
        self.update()

    def get_rect_selection_view_rect(self):
        if not self.is_rect_selecting:
            return QtCore.QRectF()

        return QtCore.QRectF(
            self.rect_select_start,
            self.rect_select_current
        ).normalized()

    def get_rect_selection_canvas_rect(self):
        view_rect = self.get_rect_selection_view_rect()

        if view_rect.isNull():
            return QtCore.QRectF()

        top_left = self.view_to_canvas(view_rect.topLeft())
        bottom_right = self.view_to_canvas(view_rect.bottomRight())

        return QtCore.QRectF(
            top_left,
            bottom_right
        ).normalized()

    def stroke_bounds(self, stroke):
        if not stroke.points:
            return QtCore.QRectF()

        polygon = QtGui.QPolygonF(stroke.points)
        return polygon.boundingRect()

    def strokes_intersecting_rect(self, rect):
        result = []

        for stroke in self.strokes:
            if not stroke.visible or not stroke.points:
                continue

            if self.stroke_bounds(stroke).intersects(rect):
                result.append(stroke)

        return result

    def end_rect_selection(self):
        if not self.is_rect_selecting:
            return

        rect = self.get_rect_selection_canvas_rect()
        additive = self.rect_select_additive
        subtractive = self.rect_select_subtractive
        intersected = self.strokes_intersecting_rect(rect)
        selected = list(self.selected_strokes)

        if subtractive:
            selected = [
                stroke
                for stroke in selected
                if stroke not in intersected
            ]

        elif additive:
            for stroke in intersected:
                if stroke not in selected:
                    selected.append(stroke)

        else:
            selected = intersected

        active_stroke = intersected[-1] if intersected else None
        self.cancel_rect_selection()
        self.set_selected_strokes(selected, active_stroke)

    def mousePressEvent(self, event):
        self.setFocus()
        position = event_position(event)

        if event.button() == QtCore.Qt.MiddleButton:
            self.is_panning = True
            self.last_pan_position = position
            self._update_cursor()
            event.accept()
            return

        if event.button() != QtCore.Qt.LeftButton:
            super().mousePressEvent(event)
            return

        canvas_position = self.view_to_canvas(position)

        if self.current_tool == self.TOOL_PENCIL:
            self._begin_stroke(canvas_position)
            event.accept()
            return

        if self.current_tool == self.TOOL_EDIT:
            point_index = self.point_at(canvas_position)

            if point_index is not None:
                self.selected_stroke.make_editable()
                self.selected_point_index = point_index
                self.is_dragging_point = True
                self._update_cursor()
                self.update()
            else:
                threshold = 7.0 / self.zoom
                stroke = self.stroke_at(canvas_position, threshold)
                self.select_stroke(stroke)

            event.accept()
            return

        if self.current_tool == self.TOOL_TRANSFORM:
            additive = self.is_additive_selection(event)
            subtractive = self.is_subtractive_selection(event)
            threshold = 7.0 / self.zoom
            stroke = self.stroke_at(canvas_position, threshold)

            if stroke:
                related_strokes = self.asset_strokes(stroke)
                was_selected = all(
                    related_stroke in self.selected_strokes
                    for related_stroke in related_strokes
                )

                if subtractive:
                    selected = [
                        selected_stroke
                        for selected_stroke in self.selected_strokes
                        if selected_stroke not in related_strokes
                    ]
                    self.set_selected_strokes(selected)

                elif additive:
                    selected = list(self.selected_strokes)

                    for related_stroke in related_strokes:
                        if related_stroke not in selected:
                            selected.append(related_stroke)

                    self.set_selected_strokes(
                        selected,
                        active_stroke=stroke
                    )

                elif not was_selected:
                    self.set_selected_strokes(
                        related_strokes,
                        active_stroke=stroke
                    )

                else:
                    self.selected_stroke = stroke
                    self.strokeSelected.emit(stroke)
                    self.update()

                if not additive and not subtractive:
                    self.begin_transform(canvas_position)

            else:
                self.begin_pending_rect_selection(
                    position,
                    additive=additive,
                    subtractive=subtractive
                )

            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        position = event_position(event)

        if self.is_panning:
            delta = position - self.last_pan_position
            self.pan += delta
            self.last_pan_position = position
            self.update()
            event.accept()
            return

        if self.is_pending_rect_select:
            if self.should_start_rect_selection(position):
                start = QtCore.QPointF(self.pending_rect_start)
                additive = self.pending_rect_additive
                subtractive = self.pending_rect_subtractive
                self.cancel_pending_rect_selection()
                self.begin_rect_selection(
                    start,
                    additive=additive,
                    subtractive=subtractive
                )
                self.update_rect_selection(position)

            event.accept()
            return

        if self.is_rect_selecting:
            self.update_rect_selection(position)
            event.accept()
            return

        if self.is_transforming:
            if not event.buttons() & QtCore.Qt.LeftButton:
                self.end_transform()
                return

            self.update_transform(self.view_to_canvas(position))
            event.accept()
            return

        if self.is_dragging_point:
            if not event.buttons() & QtCore.Qt.LeftButton:
                self.is_dragging_point = False
                self._update_cursor()
                return

            self._move_selected_point(
                self.view_to_canvas(position)
            )
            event.accept()
            return

        if not self.active_stroke:
            return super().mouseMoveEvent(event)

        if not event.buttons() & QtCore.Qt.LeftButton:
            return super().mouseMoveEvent(event)

        self._append_stroke_point(
            self.view_to_canvas(position)
        )
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MiddleButton and self.is_panning:
            self.is_panning = False
            self._update_cursor()
            event.accept()
            return

        if event.button() == QtCore.Qt.LeftButton:
            if self.is_pending_rect_select:
                subtractive = self.pending_rect_subtractive
                additive = self.pending_rect_additive
                self.cancel_pending_rect_selection()

                if not additive and not subtractive:
                    self.clear_selection()

                event.accept()
                return

            if self.is_rect_selecting:
                self.end_rect_selection()
                event.accept()
                return

            if self.is_transforming:
                self.end_transform()
                event.accept()
                return

            if self.is_dragging_point:
                self.is_dragging_point = False
                self._update_cursor()
                self.strokesChanged.emit()
                self.update()
                event.accept()
                return

            if self.active_stroke:
                self._finish_stroke()
                event.accept()
                return

        super().mouseReleaseEvent(event)

    def _move_selected_point(self, position):
        stroke = self.selected_stroke
        index = self.selected_point_index

        if not stroke or index is None:
            return

        stroke.set_point(index, position)
        self.update()

    # ------------------------------------------------------------------
    # Transform methods
    # ------------------------------------------------------------------

    def selection_bounds(self):
        points = [
            point
            for stroke in self.selected_strokes
            for point in stroke.points
        ]

        if not points:
            return QtCore.QRectF()

        return QtGui.QPolygonF(points).boundingRect()

    def selection_pivot(self):
        bounds = self.selection_bounds()

        if bounds.isNull():
            return QtCore.QPointF()

        return bounds.center()

    def begin_transform(self, position):
        if not self.selected_strokes:
            return False

        self.is_transforming = True
        self.transform_start_position = QtCore.QPointF(position)
        self.transform_pivot = self.selection_pivot()
        self.transform_start_points = {}

        for stroke in self.selected_strokes:
            stroke.make_editable()
            self.transform_start_points[stroke] = [
                QtCore.QPointF(point)
                for point in stroke.points
            ]

        self._update_cursor()
        self.update()
        return True

    def update_transform(self, position):
        if not self.is_transforming:
            return

        if self.transform_operation == self.TRANSFORM_MOVE:
            self._update_move_transform(position)

        elif self.transform_operation == self.TRANSFORM_ROTATE:
            self._update_rotate_transform(position)

        elif self.transform_operation == self.TRANSFORM_SCALE:
            self._update_scale_transform(position)

        self.update()

    def _update_move_transform(self, position):
        delta = position - self.transform_start_position

        for stroke, start_points in self.transform_start_points.items():
            points = [
                point + delta
                for point in start_points
            ]
            stroke.set_points(points, edited=True)

    def _update_rotate_transform(self, position):
        pivot = self.transform_pivot
        start_vector = self.transform_start_position - pivot
        current_vector = position - pivot

        start_angle = math.atan2(
            start_vector.y(),
            start_vector.x()
        )
        current_angle = math.atan2(
            current_vector.y(),
            current_vector.x()
        )

        angle = current_angle - start_angle
        cosine = math.cos(angle)
        sine = math.sin(angle)

        for stroke, start_points in self.transform_start_points.items():
            points = []

            for point in start_points:
                local_x = point.x() - pivot.x()
                local_y = point.y() - pivot.y()

                points.append(QtCore.QPointF(
                    pivot.x() + local_x * cosine - local_y * sine,
                    pivot.y() + local_x * sine + local_y * cosine
                ))

            stroke.set_points(points, edited=True)

    def _update_scale_transform(self, position):
        pivot = self.transform_pivot
        start_distance = point_distance(
            pivot,
            self.transform_start_position
        )

        if start_distance <= 0.000001:
            return

        current_distance = point_distance(pivot, position)
        scale = max(0.001, current_distance / start_distance)

        for stroke, start_points in self.transform_start_points.items():
            points = [
                QtCore.QPointF(
                    pivot.x() + (point.x() - pivot.x()) * scale,
                    pivot.y() + (point.y() - pivot.y()) * scale
                )
                for point in start_points
            ]

            stroke.set_points(points, edited=True)

    def end_transform(self):
        if not self.is_transforming:
            return

        self.is_transforming = False
        self.transform_start_points = {}
        self._update_cursor()
        self.strokesChanged.emit()
        self.update()

    # ------------------------------------------------------------------
    # Symmetry management methods
    # ------------------------------------------------------------------

    def symmetry_point_sets(
        self,
        points,
        stroke=None,
        include_original=True
    ):
        if not points:
            return []

        vertical_enabled = self.vertical_symmetry
        horizontal_enabled = self.horizontal_symmetry
        radial_enabled = self.radial_symmetry
        radial_count = self.radial_count

        if stroke is not None:
            vertical_enabled = (
                vertical_enabled
                and stroke.vertical_symmetry_enabled
            )
            horizontal_enabled = (
                horizontal_enabled
                and stroke.horizontal_symmetry_enabled
            )
            radial_enabled = (
                radial_enabled
                and stroke.radial_symmetry_enabled
            )

            if stroke.radial_count_override > 0:
                radial_count = stroke.radial_count_override

        mirrored_sets = [list(points)]

        if vertical_enabled:
            mirrored_sets += [
                self._mirror_points(point_set, mirror_x=True)
                for point_set in list(mirrored_sets)
            ]

        if horizontal_enabled:
            mirrored_sets += [
                self._mirror_points(point_set, mirror_y=True)
                for point_set in list(mirrored_sets)
            ]

        transformed_sets = []

        if radial_enabled:
            radial_count = max(2, int(radial_count))

            for point_set in mirrored_sets:
                for index in range(radial_count):
                    angle = math.tau * index / radial_count
                    transformed_sets.append(
                        self._rotate_points(point_set, angle)
                    )
        else:
            transformed_sets = mirrored_sets

        transformed_sets = self._remove_duplicate_point_sets(
            transformed_sets
        )

        if include_original:
            return transformed_sets

        original_signature = self._point_set_signature(points)

        return [
            point_set
            for point_set in transformed_sets
            if self._point_set_signature(point_set) != original_signature
        ]

    @staticmethod
    def _mirror_points(points, mirror_x=False, mirror_y=False):
        x_multiplier = -1.0 if mirror_x else 1.0
        y_multiplier = -1.0 if mirror_y else 1.0

        return [
            QtCore.QPointF(
                point.x() * x_multiplier,
                point.y() * y_multiplier
            )
            for point in points
        ]

    @staticmethod
    def _rotate_points(points, angle):
        cosine = math.cos(angle)
        sine = math.sin(angle)

        return [
            QtCore.QPointF(
                point.x() * cosine - point.y() * sine,
                point.x() * sine + point.y() * cosine
            )
            for point in points
        ]

    @staticmethod
    def _point_set_signature(points, precision=4):
        return tuple(
            (round(point.x(), precision), round(point.y(), precision))
            for point in points
        )

    def _remove_duplicate_point_sets(self, point_sets):
        unique_sets = []
        signatures = set()

        for points in point_sets:
            signature = self._point_set_signature(points)

            if signature in signatures:
                continue

            signatures.add(signature)
            unique_sets.append(points)

        return unique_sets
    
    def _draw_symmetry_preview(self, painter, stroke, active=False):
        points = stroke.raw_points if active else stroke.points

        if not points:
            return

        point_sets = self.symmetry_point_sets(
            points,
            stroke=stroke,
            include_original=False
        )

        if not point_sets:
            return

        color = (
            self.active_symmetry_color
            if active
            else self.symmetry_color
        )

        painter.setPen(QtGui.QPen(
            color,
            1.5 / self.zoom,
            QtCore.Qt.DashLine,
            QtCore.Qt.RoundCap,
            QtCore.Qt.RoundJoin
        ))

        for transformed_points in point_sets:
            self._draw_point_set(
                painter,
                transformed_points,
                stroke.closed
            )

    # ------------------------------------------------------------------
    # Strokes and deletion methods
    # ------------------------------------------------------------------
    def get_stroke_point_sets(self, stroke):
        if stroke not in self.strokes or not stroke.visible:
            return []

        return self.symmetry_point_sets(
            stroke.points,
            stroke=stroke,
            include_original=True
        )

    @staticmethod
    def _draw_point_set(painter, points, closed=False):
        if not points:
            return

        if len(points) == 1:
            painter.drawPoint(points[0])
            return

        path = QtGui.QPainterPath(points[0])

        for point in points[1:]:
            path.lineTo(point)

        if closed:
            path.closeSubpath()

        painter.drawPath(path)

    def keyPressEvent(self, event):
        if self.current_tool == self.TOOL_TRANSFORM:
            if event.key() == QtCore.Qt.Key_W:
                self.set_transform_operation(self.TRANSFORM_MOVE)
                event.accept()
                return

            if event.key() == QtCore.Qt.Key_E:
                self.set_transform_operation(self.TRANSFORM_ROTATE)
                event.accept()
                return

            if event.key() == QtCore.Qt.Key_R:
                self.set_transform_operation(self.TRANSFORM_SCALE)
                event.accept()
                return

        if event.key() == QtCore.Qt.Key_Escape:
            if self.is_transforming:
                self.cancel_transform()
                event.accept()
                return

            if self.is_rect_selecting or self.is_pending_rect_select:
                self.cancel_pending_rect_selection()
                self.cancel_rect_selection()
                event.accept()
                return

            self.clear_selection()
            event.accept()
            return

        if event.key() in (
            QtCore.Qt.Key_Delete,
            QtCore.Qt.Key_Backspace
        ):
            if self._delete_selected_point():
                event.accept()
                return

            self.delete_selected_strokes()
            event.accept()
            return

        super().keyPressEvent(event)

    def cancel_transform(self):
        if not self.is_transforming:
            return

        for stroke, points in self.transform_start_points.items():
            stroke.set_points(points, edited=True)

        self.is_transforming = False
        self.transform_start_points = {}
        self._update_cursor()
        self.update()

    def _delete_selected_point(self):
        if self.current_tool != self.TOOL_EDIT:
            return False

        if not self.selected_stroke or self.selected_point_index is None:
            return False

        deleted = self.selected_stroke.delete_point(
            self.selected_point_index
        )

        if not deleted:
            return False

        self.selected_point_index = None
        self.update()
        self.strokesChanged.emit()
        return True

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), self.background_color)

        painter.save()
        painter.translate(self.view_center() + self.pan)
        painter.scale(self.zoom, self.zoom)

        self._draw_grid(painter)

        for stroke in self.strokes:
            if not stroke.visible:
                continue

            self._draw_symmetry_preview(painter, stroke)
            self._draw_stroke(painter, stroke)

        if self.active_stroke:
            self._draw_symmetry_preview(
                painter,
                self.active_stroke,
                active=True
            )
            self._draw_stroke(painter, self.active_stroke, active=True)

        if (
            self.current_tool == self.TOOL_TRANSFORM
            and self.selected_strokes
        ):
            self._draw_transform_bounds(painter)

        painter.restore()
        self._draw_rect_selection(painter)

    def _draw_transform_bounds(self, painter):
        bounds = self.selection_bounds()

        if bounds.isNull():
            return

        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(QtGui.QPen(
            self.selected_color,
            1.0 / self.zoom,
            QtCore.Qt.DashLine
        ))
        painter.drawRect(bounds)

        pivot = bounds.center()
        radius = 4.0 / self.zoom

        painter.setPen(QtGui.QPen(
            QtGui.QColor(25, 25, 25),
            1.0 / self.zoom
        ))
        painter.setBrush(QtGui.QBrush(self.active_color))
        painter.drawEllipse(pivot, radius, radius)
        painter.setBrush(QtCore.Qt.NoBrush)

    def _draw_rect_selection(self, painter):
        if not self.is_rect_selecting:
            return

        rect = self.get_rect_selection_view_rect()

        if rect.isNull():
            return

        painter.setBrush(QtGui.QBrush(self.rect_select_fill))
        painter.setPen(QtGui.QPen(
            self.rect_select_outline,
            1.0
        ))
        painter.drawRect(rect)

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

    def point_at(self, position, threshold=None):
        stroke = self.selected_stroke

        if not stroke or not stroke.visible:
            return None

        if threshold is None:
            threshold = self.point_hit_radius / self.zoom

        closest_index = None
        closest_distance = float("inf")

        for index, point in enumerate(stroke.points):
            distance = point_distance(position, point)

            if distance <= threshold and distance < closest_distance:
                closest_index = index
                closest_distance = distance

        return closest_index

    def _begin_stroke(self, position):
        base_name = "Curve_{:02d}".format(len(self.strokes) + 1)
        name = self.unique_stroke_name(base_name)

        self.active_stroke = ECurveStroke(
            points=[position],
            closed=False,
            name=name
        )
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

        self._draw_point_set(painter, points, stroke.closed)

        if stroke.selected and self.current_tool == self.TOOL_EDIT and not active:
            self._draw_edit_points(painter, stroke)

    def _draw_edit_points(self, painter, stroke):
        point_size = 7.0 / self.zoom
        half_size = point_size * 0.5

        normal_color = QtGui.QColor(225, 225, 225)
        selected_color = self.active_color
        outline_color = QtGui.QColor(25, 25, 25)

        for index, point in enumerate(stroke.points):
            rect = QtCore.QRectF(
                point.x() - half_size,
                point.y() - half_size,
                point_size,
                point_size
            )

            color = (
                selected_color
                if index == self.selected_point_index
                else normal_color
            )

            painter.setPen(QtGui.QPen(outline_color, 1.0 / self.zoom))
            painter.setBrush(QtGui.QBrush(color))
            painter.drawRect(rect)

        painter.setBrush(QtCore.Qt.NoBrush)

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