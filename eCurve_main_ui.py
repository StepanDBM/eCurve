try:
    from PySide6 import QtCore, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtWidgets

import maya.cmds as cmds

from eCurve_canvas import ECurveCanvas


class ECurveMainUI(QtWidgets.QDialog):
    WINDOW_TITLE = "eCurve"

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(self.WINDOW_TITLE)
        self.resize(760, 600)
        self.setMinimumSize(520, 400)

        self.canvas = ECurveCanvas()
        self._build_ui()
        self._connect_signals()
        self._refresh_curve_list()

    def _build_ui(self):
        self.pencil_button = QtWidgets.QPushButton("Pencil")
        self.pencil_button.setCheckable(True)
        self.pencil_button.setChecked(True)

        self.edit_button = QtWidgets.QPushButton("Edit")
        self.edit_button.setCheckable(True)

        self.tool_group = QtWidgets.QButtonGroup(self)
        self.tool_group.setExclusive(True)
        self.tool_group.addButton(self.pencil_button)
        self.tool_group.addButton(self.edit_button)

        self.tolerance_spin = QtWidgets.QDoubleSpinBox()
        self.tolerance_spin.setRange(0.0, 25.0)
        self.tolerance_spin.setValue(2.0)
        self.tolerance_spin.setSingleStep(0.25)

        self.curve_list = QtWidgets.QListWidget()
        self.curve_list.setMinimumWidth(170)
        self.curve_list.setMaximumWidth(240)

        self.delete_button = QtWidgets.QPushButton("Delete")
        self.clear_button = QtWidgets.QPushButton("Clear All")
        self.create_button = QtWidgets.QPushButton("Create Control")

        toolbar_layout = QtWidgets.QHBoxLayout()
        toolbar_layout.addWidget(self.pencil_button)
        toolbar_layout.addWidget(self.edit_button)
        toolbar_layout.addSpacing(12)
        toolbar_layout.addWidget(QtWidgets.QLabel("Simplify"))
        toolbar_layout.addWidget(self.tolerance_spin)
        toolbar_layout.addStretch()

        curve_buttons_layout = QtWidgets.QHBoxLayout()
        curve_buttons_layout.addWidget(self.delete_button)
        curve_buttons_layout.addWidget(self.clear_button)

        side_layout = QtWidgets.QVBoxLayout()
        side_layout.addWidget(QtWidgets.QLabel("Curves"))
        side_layout.addWidget(self.curve_list)
        side_layout.addLayout(curve_buttons_layout)
        side_layout.addWidget(self.create_button)

        self.zoom_out_button = QtWidgets.QPushButton("-")
        self.zoom_out_button.setToolTip("Zoom Out")

        self.zoom_label = QtWidgets.QLabel("100%")
        self.zoom_label.setMinimumWidth(48)
        self.zoom_label.setAlignment(QtCore.Qt.AlignCenter)

        self.zoom_in_button = QtWidgets.QPushButton("+")
        self.zoom_in_button.setToolTip("Zoom In")

        self.reset_view_button = QtWidgets.QPushButton("Reset View")

        content_layout = QtWidgets.QHBoxLayout()
        content_layout.addWidget(self.canvas, 1)
        content_layout.addLayout(side_layout, 0)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addLayout(toolbar_layout)
        main_layout.addLayout(content_layout, 1)

    def _connect_signals(self):
        self.pencil_button.clicked.connect(self._activate_pencil_tool)
        self.edit_button.clicked.connect(self._activate_edit_tool)
        self.tolerance_spin.valueChanged.connect(
            self.canvas.set_simplify_tolerance
        )

        self.canvas.strokesChanged.connect(self._refresh_curve_list)
        self.canvas.strokeSelected.connect(self._select_curve_list_item)

        self.curve_list.currentRowChanged.connect(self._select_canvas_stroke)
        self.curve_list.itemChanged.connect(self._curve_item_changed)

        self.delete_button.clicked.connect(self.canvas.delete_selected_stroke)
        self.clear_button.clicked.connect(self.canvas.clear_strokes)
        self.create_button.clicked.connect(self._create_control)    

    def _activate_pencil_tool(self):
        self.canvas.set_tool(ECurveCanvas.TOOL_PENCIL)

    def _activate_edit_tool(self):
        self.canvas.set_tool(ECurveCanvas.TOOL_EDIT)

    def _refresh_curve_list(self):
        selected_stroke = self.canvas.get_selected_stroke()

        self.curve_list.blockSignals(True)
        self.curve_list.clear()

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

            if stroke is selected_stroke:
                self.curve_list.setCurrentItem(item)

        self.curve_list.blockSignals(False)

    def _select_curve_list_item(self, stroke):
        self.curve_list.blockSignals(True)

        if stroke is None:
            self.curve_list.clearSelection()
            self.curve_list.setCurrentRow(-1)
        else:
            for index in range(self.curve_list.count()):
                item = self.curve_list.item(index)

                if item.data(QtCore.Qt.UserRole) is stroke:
                    self.curve_list.setCurrentItem(item)
                    break

        self.curve_list.blockSignals(False)

    def _select_canvas_stroke(self, row):
        if row < 0:
            self.canvas.select_stroke(None)
            return

        item = self.curve_list.item(row)
        self.canvas.select_stroke(item.data(QtCore.Qt.UserRole))

    def _curve_item_changed(self, item):
        stroke = item.data(QtCore.Qt.UserRole)
        visible = item.checkState() == QtCore.Qt.Checked
        self.canvas.set_stroke_visibility(stroke, visible)

    def _create_control(self):
        visible_strokes = self.canvas.get_visible_strokes()

        if not visible_strokes:
            cmds.warning("eCurve: There are no visible curves to create.")
            return

        curve_transforms = []

        for stroke in visible_strokes:
            if len(stroke.points) < 2:
                continue

            maya_points = [
                self._canvas_to_maya(point)
                for point in stroke.points
            ]

            curve = cmds.curve(
                name="eCurve_#",
                degree=1,
                point=maya_points
            )

            curve_transforms.append(curve)

        if not curve_transforms:
            cmds.warning("eCurve: No valid curves were found.")
            return

        control = self._combine_curve_shapes(
            curve_transforms,
            "eCurve_CTRL"
        )

        cmds.select(control, replace=True)

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