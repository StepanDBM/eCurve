try:
    from PySide6 import QtCore, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtWidgets

import maya.cmds as cmds

from eCurve_canvas import ECurveCanvas
from eCurve_storage import ECurveStorage


class ECurveMainUI(QtWidgets.QDialog):
    WINDOW_TITLE = "eCurve"

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(self.WINDOW_TITLE)
        self.resize(760, 600)
        self.setMinimumSize(520, 400)

        self.canvas = ECurveCanvas()
        self.storage = ECurveStorage(self.canvas)
        self._build_ui()
        self._connect_signals()
        self._refresh_curve_list()

    def _build_ui(self):
        self.pencil_button = QtWidgets.QPushButton("Pencil")
        self.pencil_button.setCheckable(True)
        self.pencil_button.setChecked(True)

        self.edit_button = QtWidgets.QPushButton("Edit")
        self.edit_button.setCheckable(True)

        self.transform_button = QtWidgets.QPushButton("Transform")
        self.transform_button.setCheckable(True)
        self.transform_button.setToolTip(
            "Transform selected curves. W: Move, E: Rotate, R: Scale"
        )

        self.transform_operation_combo = QtWidgets.QComboBox()
        self.transform_operation_combo.addItem(
            "Move", ECurveCanvas.TRANSFORM_MOVE
        )
        self.transform_operation_combo.addItem(
            "Rotate", ECurveCanvas.TRANSFORM_ROTATE
        )
        self.transform_operation_combo.addItem(
            "Scale", ECurveCanvas.TRANSFORM_SCALE
        )
        self.transform_operation_combo.setToolTip(
            "Choose the curve transformation operation"
        )
        self.transform_operation_combo.setEnabled(False)

        self.tool_group = QtWidgets.QButtonGroup(self)
        self.tool_group.setExclusive(True)
        self.tool_group.addButton(self.pencil_button)
        self.tool_group.addButton(self.edit_button)
        self.tool_group.addButton(self.transform_button)

        self.tolerance_spin = QtWidgets.QDoubleSpinBox()
        self.tolerance_spin.setRange(0.0, 25.0)
        self.tolerance_spin.setValue(2.0)
        self.tolerance_spin.setSingleStep(0.25)

        self.curve_list = QtWidgets.QListWidget()
        self.curve_list.setMinimumWidth(170)
        self.curve_list.setMaximumWidth(240)
        self.curve_list.setSelectionMode(
            QtWidgets.QAbstractItemView.ExtendedSelection
        )
        self.curve_list.setToolTip(
            "Select one or more curves. Use Ctrl or Shift for multiple selection"
        )

        self.delete_button = QtWidgets.QPushButton("Delete")
        self.clear_button = QtWidgets.QPushButton("Clear All")
        self.create_button = QtWidgets.QPushButton("Create Control")

        self.save_file_button = QtWidgets.QPushButton("Save SVG")
        self.save_file_button.setToolTip(
            "Save the current drawing to an SVG file"
        )

        self.load_file_button = QtWidgets.QPushButton("Import SVG")
        self.load_file_button.setToolTip(
            "Import curves from an SVG file without clearing the canvas"
        )

        self.save_scene_button = QtWidgets.QPushButton("Save to Scene")
        self.save_scene_button.setToolTip(
            "Save the current drawing inside the Maya scene"
        )

        self.load_scene_button = QtWidgets.QPushButton("Load from Scene")
        self.load_scene_button.setToolTip(
            "Load the stored drawing from the Maya scene"
        )

        toolbar_layout = QtWidgets.QHBoxLayout()
        toolbar_layout.addWidget(self.pencil_button)
        toolbar_layout.addWidget(self.edit_button)
        toolbar_layout.addWidget(self.transform_button)
        toolbar_layout.addSpacing(12)
        toolbar_layout.addWidget(QtWidgets.QLabel("Operation"))
        toolbar_layout.addWidget(self.transform_operation_combo)
        toolbar_layout.addSpacing(12)
        toolbar_layout.addWidget(QtWidgets.QLabel("Simplify"))
        toolbar_layout.addWidget(self.tolerance_spin)
        toolbar_layout.addStretch()

        self.vertical_symmetry_button = QtWidgets.QPushButton("Vertical")
        self.vertical_symmetry_button.setCheckable(True)
        self.vertical_symmetry_button.setToolTip(
            "Mirror across the vertical canvas axis"
        )

        self.horizontal_symmetry_button = QtWidgets.QPushButton("Horizontal")
        self.horizontal_symmetry_button.setCheckable(True)
        self.horizontal_symmetry_button.setToolTip(
            "Mirror across the horizontal canvas axis"
        )

        self.radial_symmetry_button = QtWidgets.QPushButton("Radial")
        self.radial_symmetry_button.setCheckable(True)
        self.radial_symmetry_button.setToolTip(
            "Repeat strokes around the canvas origin"
        )

        self.radial_count_spin = QtWidgets.QSpinBox()
        self.radial_count_spin.setRange(2, 32)
        self.radial_count_spin.setValue(4)
        self.radial_count_spin.setEnabled(False)
        self.radial_count_spin.setToolTip(
            "Number of radial copies, including the original"
        )

        symmetry_layout = QtWidgets.QHBoxLayout()
        symmetry_layout.addWidget(QtWidgets.QLabel("Symmetry"))
        symmetry_layout.addWidget(self.vertical_symmetry_button)
        symmetry_layout.addWidget(self.horizontal_symmetry_button)
        symmetry_layout.addWidget(self.radial_symmetry_button)
        symmetry_layout.addWidget(QtWidgets.QLabel("Count"))
        symmetry_layout.addWidget(self.radial_count_spin)
        symmetry_layout.addStretch()

        curve_buttons_layout = QtWidgets.QHBoxLayout()
        curve_buttons_layout.addWidget(self.delete_button)
        curve_buttons_layout.addWidget(self.clear_button)

        file_storage_layout = QtWidgets.QHBoxLayout()
        file_storage_layout.addWidget(self.save_file_button)
        file_storage_layout.addWidget(self.load_file_button)

        scene_storage_layout = QtWidgets.QHBoxLayout()
        scene_storage_layout.addWidget(self.save_scene_button)
        scene_storage_layout.addWidget(self.load_scene_button)

        side_layout = QtWidgets.QVBoxLayout()
        side_layout.addWidget(QtWidgets.QLabel("Curves"))
        side_layout.addWidget(self.curve_list)
        side_layout.addLayout(curve_buttons_layout)
        side_layout.addSpacing(8)
        side_layout.addWidget(QtWidgets.QLabel("File"))
        side_layout.addLayout(file_storage_layout)
        side_layout.addWidget(QtWidgets.QLabel("Maya Scene"))
        side_layout.addLayout(scene_storage_layout)
        side_layout.addSpacing(8)
        side_layout.addWidget(self.create_button)

        content_layout = QtWidgets.QHBoxLayout()
        content_layout.addWidget(self.canvas, 1)
        content_layout.addLayout(side_layout, 0)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addLayout(toolbar_layout)
        main_layout.addLayout(symmetry_layout)
        main_layout.addLayout(content_layout, 1)

    def _connect_signals(self):
        self.pencil_button.clicked.connect(self._activate_pencil_tool)
        self.edit_button.clicked.connect(self._activate_edit_tool)
        self.tolerance_spin.valueChanged.connect(self.canvas.set_simplify_tolerance)

        self.canvas.strokesChanged.connect(self._refresh_curve_list)
        self.canvas.strokeSelected.connect(self._select_curve_list_item)

        self.curve_list.itemSelectionChanged.connect(self._select_canvas_strokes)
        self.curve_list.itemChanged.connect(self._curve_item_changed)

        self.delete_button.clicked.connect(self.canvas.delete_selected_stroke)
        self.clear_button.clicked.connect(self.canvas.clear_strokes)
        self.create_button.clicked.connect(self._create_control)

        self.vertical_symmetry_button.toggled.connect(self.canvas.set_vertical_symmetry)
        self.horizontal_symmetry_button.toggled.connect(self.canvas.set_horizontal_symmetry)
        self.radial_symmetry_button.toggled.connect(self.canvas.set_radial_symmetry)
        self.radial_symmetry_button.toggled.connect(self.radial_count_spin.setEnabled)
        self.radial_count_spin.valueChanged.connect(self.canvas.set_radial_count)

        self.save_file_button.clicked.connect(self._save_svg)
        self.load_file_button.clicked.connect(self._load_svg)
        self.save_scene_button.clicked.connect(self.storage.save_to_scene)
        self.load_scene_button.clicked.connect(self._load_from_scene)

        self.transform_button.clicked.connect(self._activate_transform_tool)
        self.canvas.transformOperationChanged.connect(self._sync_transform_operation_combo)
        self.transform_button.toggled.connect(self.transform_operation_combo.setEnabled)
        self.transform_button.toggled.connect(
            lambda enabled: self.tolerance_spin.setEnabled(not enabled))
        self.transform_operation_combo.currentIndexChanged.connect(self._transform_operation_changed)

    def _activate_pencil_tool(self):
        self.canvas.set_tool(ECurveCanvas.TOOL_PENCIL)

    def _activate_edit_tool(self):
        self.canvas.set_tool(ECurveCanvas.TOOL_EDIT)

    def _refresh_curve_list(self):
        selected_strokes = self.canvas.get_selected_strokes()
        active_stroke = self.canvas.get_selected_stroke()

        self.curve_list.blockSignals(True)
        self.curve_list.clear()

        active_item = None

        for stroke in self.canvas.strokes:
            item = QtWidgets.QListWidgetItem(stroke.name)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(
                QtCore.Qt.Checked
                if stroke.visible
                else QtCore.Qt.Unchecked
            )
            item.setData(QtCore.Qt.UserRole, stroke)
            self.curve_list.addItem(item)

            if stroke in selected_strokes:
                item.setSelected(True)

            if stroke is active_stroke:
                active_item = item

        if active_item:
            self.curve_list.setCurrentItem(
                active_item,
                QtCore.QItemSelectionModel.NoUpdate
            )

        self.curve_list.blockSignals(False)

    def _select_curve_list_item(self, stroke):
        selected_strokes = self.canvas.get_selected_strokes()

        self.curve_list.blockSignals(True)
        self.curve_list.clearSelection()

        active_item = None

        for index in range(self.curve_list.count()):
            item = self.curve_list.item(index)
            item_stroke = item.data(QtCore.Qt.UserRole)

            if item_stroke in selected_strokes:
                item.setSelected(True)

            if item_stroke is stroke:
                active_item = item

        if active_item:
            self.curve_list.setCurrentItem(
                active_item,
                QtCore.QItemSelectionModel.NoUpdate
            )

        self.curve_list.blockSignals(False)

    def _activate_transform_tool(self):
        self.canvas.set_tool(ECurveCanvas.TOOL_TRANSFORM)
        self._transform_operation_changed()
        self.canvas.setFocus()

    def _sync_transform_operation_combo(self, operation):
        index = self.transform_operation_combo.findData(operation)

        if index < 0:
            return

        self.transform_operation_combo.blockSignals(True)
        self.transform_operation_combo.setCurrentIndex(index)
        self.transform_operation_combo.blockSignals(False)

    def _transform_operation_changed(self, index=None):
        operation = self.transform_operation_combo.currentData()

        if operation:
            self.canvas.set_transform_operation(operation)

    def _select_canvas_strokes(self):
        strokes = [
            item.data(QtCore.Qt.UserRole)
            for item in self.curve_list.selectedItems()
        ]

        active_item = self.curve_list.currentItem()
        active_stroke = (
            active_item.data(QtCore.Qt.UserRole)
            if active_item
            else None
        )

        self.canvas.set_selected_strokes(strokes,active_stroke=active_stroke)

    def _curve_item_changed(self, item):
        stroke = item.data(QtCore.Qt.UserRole)
        visible = item.checkState() == QtCore.Qt.Checked
        self.canvas.set_stroke_visibility(stroke, visible)

    def _save_svg(self):
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save eCurve SVG",
            "",
            "SVG Files (*.svg)",
        )

        if file_path:
            self.storage.save_to_file(file_path)

    def _load_svg(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load SVG",
            "",
            "SVG Files (*.svg)",
        )

        if not file_path:
            return

        if self.storage.load_from_file(file_path):
            self._refresh_curve_list()
            self.canvas.setFocus()

    def _load_from_scene(self):
        if self.storage.load_from_scene():
            self._sync_ui_after_load()

    def _sync_ui_after_load(self):
        self.tolerance_spin.blockSignals(True)
        self.tolerance_spin.setValue(self.canvas.simplify_tolerance)
        self.tolerance_spin.blockSignals(False)

        self._update_zoom_label(self.canvas.zoom)
        self._refresh_curve_list()

    def _create_control(self):
        visible_strokes = self.canvas.get_visible_strokes()

        if not visible_strokes:
            cmds.warning(
                "eCurve: There are no visible curves to create."
            )
            return

        curve_transforms = []

        cmds.undoInfo(
            openChunk=True,
            chunkName="eCurve Create Control"
        )

        try:
            for stroke in visible_strokes:
                point_sets = self.canvas.get_stroke_point_sets(stroke)

                for points in point_sets:
                    if len(points) < 2:
                        continue

                    maya_points = [
                        self._canvas_to_maya(point)
                        for point in points
                    ]

                    curve = cmds.curve(
                        name="eCurve_#",
                        degree=1,
                        point=maya_points
                    )

                    if stroke.closed:
                        curve = cmds.closeCurve(
                            curve,
                            constructionHistory=False,
                            preserveShape=True,
                            replaceOriginal=True
                        )[0]

                    curve_transforms.append(curve)

            if not curve_transforms:
                cmds.warning(
                    "eCurve: No valid curves were found."
                )
                return

            control = self._combine_curve_shapes(
                curve_transforms,
                "eCurve_CTRL"
            )

            cmds.select(control, replace=True)

        except Exception as error:
            if curve_transforms:
                cmds.delete([
                    curve
                    for curve in curve_transforms
                    if cmds.objExists(curve)
                ])

            cmds.warning(
                "eCurve: Control creation failed: {}".format(error)
            )

        finally:
            cmds.undoInfo(closeChunk=True)

    def _canvas_to_maya(self, point):
        scale = 128.0
        return point.x() / scale, -point.y() / scale, 0.0

    def _combine_curve_shapes(self, curves, name):
        control = cmds.createNode("transform", name=name)

        for curve in curves:
            shapes = cmds.listRelatives(
                curve,
                shapes=True,
                fullPath=True
            ) or []

            for shape in shapes:
                cmds.parent(shape, control, shape=True, relative=True)

            cmds.delete(curve)

        return control