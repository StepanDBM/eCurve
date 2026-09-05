# eCurve_main_ui.py

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets

import maya.cmds as cmds

from eCurve_canvas import ECurveCanvas
from eCurve_storage import ECurveStorage
from eCurve_asset_strip import eCurveAssetStrip
from eCurve_primitives import PRIMITIVE_INFO, create_primitive
from eCurve_asset_io import (
    ASSET_DIRECTORY,
    load_asset,
    load_asset_library,
    save_asset
)
from eCurve_thumbnail import render_asset_thumbnail


def build_primitive_items():
    items = []

    for primitive_type, info in PRIMITIVE_INFO.items():
        asset = create_primitive(primitive_type)
        thumbnail = render_asset_thumbnail(asset)

        items.append({
            "name": info["name"],
            "type": "primitive",
            "primitive": primitive_type,
            "category": info["category"],
            "thumbnail": thumbnail,
            "tooltip": "Create a {} primitive".format(
                info["name"].lower()
            ),
        })

    return items

PRIMITIVE_ITEMS = build_primitive_items()


ASSET_ITEMS = []



class ECurveListItemWidget(QtWidgets.QWidget):
    symmetryChanged = QtCore.Signal(object)

    def __init__(self, stroke, parent=None):
        super().__init__(parent)

        self.stroke = stroke

        self.name_label = QtWidgets.QLabel(stroke.name)
        self.name_label.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Preferred
        )

        self.horizontal_button = QtWidgets.QPushButton("H")
        self.horizontal_button.setCheckable(True)
        self.horizontal_button.setChecked(
            stroke.horizontal_symmetry_enabled
        )
        self.horizontal_button.setToolTip(
            "Allow global horizontal symmetry for this curve"
        )

        self.vertical_button = QtWidgets.QPushButton("V")
        self.vertical_button.setCheckable(True)
        self.vertical_button.setChecked(
            stroke.vertical_symmetry_enabled
        )
        self.vertical_button.setToolTip(
            "Allow global vertical symmetry for this curve"
        )

        self.radial_button = QtWidgets.QPushButton("R")
        self.radial_button.setCheckable(True)
        self.radial_button.setChecked(
            stroke.radial_symmetry_enabled
        )
        self.radial_button.setToolTip(
            "Allow global radial symmetry for this curve"
        )

        self.radial_count_spin = QtWidgets.QSpinBox()
        self.radial_count_spin.setRange(0, 32)
        self.radial_count_spin.setValue(
            stroke.radial_count_override
        )
        self.radial_count_spin.setToolTip(
            "0 uses the global radial count. "
            "Any other value overrides it for this curve"
        )

        for button in (
            self.horizontal_button,
            self.vertical_button,
            self.radial_button
        ):
            button.setFixedSize(24, 22)

        self.radial_count_spin.setFixedWidth(48)
        self.radial_count_spin.setFixedHeight(22)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 1, 2, 1)
        layout.setSpacing(2)
        layout.addWidget(self.name_label, 1)
        layout.addWidget(self.horizontal_button)
        layout.addWidget(self.vertical_button)
        layout.addWidget(self.radial_button)
        layout.addWidget(self.radial_count_spin)

        self.horizontal_button.toggled.connect(self._horizontal_changed)
        self.vertical_button.toggled.connect(self._vertical_changed)
        self.radial_button.toggled.connect(self._radial_changed)
        self.radial_count_spin.valueChanged.connect(self._radial_count_changed)

    def _horizontal_changed(self, enabled):
        self.stroke.horizontal_symmetry_enabled = bool(enabled)
        self.symmetryChanged.emit(self.stroke)

    def _vertical_changed(self, enabled):
        self.stroke.vertical_symmetry_enabled = bool(enabled)
        self.symmetryChanged.emit(self.stroke)

    def _radial_changed(self, enabled):
        self.stroke.radial_symmetry_enabled = bool(enabled)
        self.symmetryChanged.emit(self.stroke)

    def _radial_count_changed(self, count):
        self.stroke.radial_count_override = int(count)
        self.symmetryChanged.emit(self.stroke)

class ECurveMainUI(QtWidgets.QDialog):
    WINDOW_TITLE = "eCurve"
    OBJECT_NAME = "eCurveMainWindow"

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.resize(760, 600)
        self.setMinimumSize(520, 400)

        self.control_color = QtGui.QColor(255, 200, 0)

        self.library_assets = []

        self.canvas = ECurveCanvas()
        self.storage = ECurveStorage(self.canvas)
        self._build_ui()
        self._connect_signals()
        self._refresh_curve_list()
        self._refresh_asset_library()

    def _create_strip_section(self, title, strip, extra_widget=None):
        section = QtWidgets.QWidget()

        title_label = QtWidgets.QLabel(title)
        title_label.setFixedWidth(65)

        layout = QtWidgets.QHBoxLayout(section)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)
        layout.addWidget(title_label)
        layout.addWidget(strip, 1)

        if extra_widget:
            layout.addWidget(extra_widget)

        return section

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

        self.color_button = QtWidgets.QPushButton("Controller Color")
        self.color_button.setToolTip(
            "Choose the viewport color for generated Maya controllers"
        )
        self.color_button.setMinimumWidth(110)
        self._update_color_button()

        self.curve_list = QtWidgets.QListWidget()
        self.curve_list.setMinimumWidth(250)
        self.curve_list.setMaximumWidth(330)
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
        toolbar_layout.addWidget(self.color_button)
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

        self.primitive_strip = eCurveAssetStrip(PRIMITIVE_ITEMS)
        self.asset_strip = eCurveAssetStrip(ASSET_ITEMS)

        self.save_asset_button = QtWidgets.QPushButton("Save Asset")
        self.save_asset_button.setToolTip(
            "Save the selected strokes as one reusable asset.\n"
            "Library: {}".format(ASSET_DIRECTORY)
        )

        self.primitive_section = self._create_strip_section("Primitives:",
            self.primitive_strip,
        )

        self.asset_section = self._create_strip_section(
            "Assets:",
            self.asset_strip,
            self.save_asset_button,
        )

        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        side_widget = QtWidgets.QWidget()
        side_widget.setLayout(side_layout)
        side_widget.setMinimumWidth(0)
        side_widget.setMaximumWidth(16777215)

        self.content_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.content_splitter.setChildrenCollapsible(True)
        self.content_splitter.setHandleWidth(5)
        self.content_splitter.addWidget(self.canvas)
        self.content_splitter.addWidget(side_widget)
        self.content_splitter.setStretchFactor(0, 1)
        self.content_splitter.setStretchFactor(1, 0)
        self.content_splitter.setSizes([800, 270])

        content_layout.addWidget(self.content_splitter)

        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.main_splitter.setChildrenCollapsible(True)
        self.main_splitter.setHandleWidth(5)
        self.main_splitter.addWidget(self.primitive_section)
        self.main_splitter.addWidget(self.asset_section)
        self.main_splitter.addWidget(content_widget)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 0)
        self.main_splitter.setStretchFactor(2, 1)
        self.main_splitter.setSizes([68, 68, 600])

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(4)
        main_layout.addLayout(toolbar_layout)
        main_layout.addLayout(symmetry_layout)
        main_layout.addWidget(self.main_splitter, 1)

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

        self.color_button.clicked.connect(self._choose_control_color)

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


        self.primitive_strip.item_clicked.connect(self._primitive_clicked)
        self.asset_strip.item_clicked.connect(self._asset_clicked)
        self.save_asset_button.clicked.connect(self._save_asset_clicked)

    def _activate_pencil_tool(self):
        self.canvas.set_tool(ECurveCanvas.TOOL_PENCIL)

    def _activate_edit_tool(self):
        self.canvas.set_tool(ECurveCanvas.TOOL_EDIT)

    def _curve_symmetry_changed(self, stroke):
        if stroke not in self.canvas.strokes:
            return
        self.canvas.update()

    def _refresh_curve_list(self):
        selected_strokes = self.canvas.get_selected_strokes()
        active_stroke = self.canvas.get_selected_stroke()

        self.curve_list.blockSignals(True)
        self.curve_list.clear()

        active_item = None

        for stroke in self.canvas.strokes:
            item = QtWidgets.QListWidgetItem()
            item.setFlags(
                item.flags()
                | QtCore.Qt.ItemIsUserCheckable
                | QtCore.Qt.ItemIsSelectable
                | QtCore.Qt.ItemIsEnabled
            )
            item.setCheckState(
                QtCore.Qt.Checked
                if stroke.visible
                else QtCore.Qt.Unchecked
            )
            item.setData(QtCore.Qt.UserRole, stroke)

            row_widget = ECurveListItemWidget(stroke)
            row_widget.symmetryChanged.connect(
                self._curve_symmetry_changed
            )

            item.setSizeHint(row_widget.sizeHint())

            self.curve_list.addItem(item)
            self.curve_list.setItemWidget(item, row_widget)

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

    def _build_asset_item(self, asset):
        return {
            "name": asset.name,
            "type": "asset",
            "asset": asset,
            "file_path": asset.metadata.get("file_path"),
            "thumbnail": render_asset_thumbnail(
                asset,
                width=64,
                height=44,
                padding=5
            ),
            "tooltip": "Insert the '{}' asset".format(asset.name)
        }

    def _refresh_asset_library(self):
        self.library_assets = load_asset_library()

        items = [
            self._build_asset_item(asset)
            for asset in self.library_assets
        ]

        self.asset_strip.set_items(items)

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

    def _choose_control_color(self):
        color = QtWidgets.QColorDialog.getColor(
            self.control_color,
            self,
            "Choose Controller Color"
        )

        if not color.isValid():
            return

        self.control_color = color
        self._update_color_button()

    def _update_color_button(self):
        color = self.control_color
        text_color = self._contrasting_text_color(color)

        self.color_button.setStyleSheet(
            """
            QPushButton {{
                background-color: rgb({red}, {green}, {blue});
                color: rgb({text_red}, {text_green}, {text_blue});
                border: 1px solid rgb(80, 80, 80);
                border-radius: 3px;
                padding: 4px;
            }}

            QPushButton:hover {{
                border: 1px solid rgb(180, 180, 180);
            }}
            """.format(
                red=color.red(),
                green=color.green(),
                blue=color.blue(),
                text_red=text_color.red(),
                text_green=text_color.green(),
                text_blue=text_color.blue()
            )
        )

    def _contrasting_text_color(self, color):
        brightness = (
            color.red() * 0.299 +
            color.green() * 0.587 +
            color.blue() * 0.114
        )

        if brightness > 150:
            return QtGui.QColor(25, 25, 25)

        return QtGui.QColor(240, 240, 240)

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
        self.tolerance_spin.setValue(
            self.canvas.simplify_tolerance
        )
        self.tolerance_spin.blockSignals(False)

        self.vertical_symmetry_button.blockSignals(True)
        self.horizontal_symmetry_button.blockSignals(True)
        self.radial_symmetry_button.blockSignals(True)
        self.radial_count_spin.blockSignals(True)

        self.vertical_symmetry_button.setChecked(
            self.canvas.vertical_symmetry
        )
        self.horizontal_symmetry_button.setChecked(
            self.canvas.horizontal_symmetry
        )
        self.radial_symmetry_button.setChecked(
            self.canvas.radial_symmetry
        )
        self.radial_count_spin.setValue(
            self.canvas.radial_count
        )
        self.radial_count_spin.setEnabled(
            self.canvas.radial_symmetry
        )

        self.vertical_symmetry_button.blockSignals(False)
        self.horizontal_symmetry_button.blockSignals(False)
        self.radial_symmetry_button.blockSignals(False)
        self.radial_count_spin.blockSignals(False)

        self._refresh_curve_list()
        self.canvas.update()

    def _apply_control_color(self, control):
        shapes = cmds.listRelatives(
            control,
            shapes=True,
            fullPath=True
        ) or []

        red = self.control_color.redF()
        green = self.control_color.greenF()
        blue = self.control_color.blueF()

        for shape in shapes:
            cmds.setAttr("{}.overrideEnabled".format(shape), True)
            cmds.setAttr("{}.overrideRGBColors".format(shape), True)
            cmds.setAttr(
                "{}.overrideColorRGB".format(shape),
                red,
                green,
                blue,
                type="double3"
            )

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

            self._apply_control_color(control)
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

    def _primitive_clicked(self, item_data):
        primitive_type = item_data.get("primitive")

        if not primitive_type:
            cmds.warning("eCurve: Invalid primitive information.")
            return

        try:
            self.canvas.add_asset(create_primitive(primitive_type))
        except Exception as error:
            cmds.warning(
                "eCurve: Could not create primitive '{}': {}".format(
                    item_data.get("name", primitive_type),
                    error
                )
            )


    def _asset_clicked(self, item_data):
        file_path = item_data.get("file_path")

        try:
            if file_path:
                asset = load_asset(file_path)
            else:
                asset = item_data.get("asset")

            if asset is None:
                cmds.warning("eCurve: Invalid asset information.")
                return

            self.canvas.add_asset(asset)

        except Exception as error:
            cmds.warning(
                "eCurve: Could not insert asset '{}': {}".format(
                    item_data.get("name", "Unknown"),
                    error
                )
            )

    def _save_asset_clicked(self):
        selected_strokes = self.canvas.get_selected_strokes()

        if not selected_strokes:
            cmds.warning(
                "eCurve: Select one or more strokes or assets first."
            )
            return

        name, accepted = QtWidgets.QInputDialog.getText(
            self,
            "Save eCurve Asset",
            "Asset name:",
            QtWidgets.QLineEdit.Normal,
            "New Asset"
        )

        if not accepted:
            return

        name = name.strip()

        if not name:
            cmds.warning("eCurve: Asset name cannot be empty.")
            return

        try:
            asset = self.canvas.create_asset_from_selection(name)

            if asset is None or asset.is_empty():
                cmds.warning(
                    "eCurve: The current selection contains no valid strokes."
                )
                return

            file_path = save_asset(asset, name)
            self._refresh_asset_library()

            cmds.inViewMessage(
                assistMessage="Saved eCurve asset: <hl>{}</hl>".format(
                    asset.name
                ),
                position="midCenterTop",
                fade=True
            )

            print("eCurve asset saved:", file_path)

        except Exception as error:
            cmds.warning(
                "eCurve: Could not save asset '{}': {}".format(
                    name,
                    error
                )
            )