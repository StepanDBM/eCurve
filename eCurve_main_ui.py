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

TREE_ROLE_OBJECT = QtCore.Qt.UserRole
TREE_ROLE_TYPE = QtCore.Qt.UserRole + 1

TREE_TYPE_ASSET = "asset"
TREE_TYPE_STROKE = "stroke"
TREE_TYPE_STANDALONE = "standalone"

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



class ECurveTreeItemWidget(QtWidgets.QWidget):
    symmetryChanged = QtCore.Signal(object)

    def __init__(self, drawable, is_asset=False, parent=None):
        super().__init__(parent)

        self.drawable = drawable
        self.is_asset = bool(is_asset)

        self.name_label = QtWidgets.QLabel(drawable.name)
        self.name_label.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Preferred
        )

        if self.is_asset:
            font = self.name_label.font()
            font.setBold(True)
            self.name_label.setFont(font)

        self.horizontal_button = QtWidgets.QPushButton("H")
        self.horizontal_button.setCheckable(True)
        self.horizontal_button.setChecked(
            drawable.horizontal_symmetry_enabled
        )
        self.horizontal_button.setToolTip(
            self._symmetry_tooltip("horizontal")
        )

        self.vertical_button = QtWidgets.QPushButton("V")
        self.vertical_button.setCheckable(True)
        self.vertical_button.setChecked(
            drawable.vertical_symmetry_enabled
        )
        self.vertical_button.setToolTip(
            self._symmetry_tooltip("vertical")
        )

        self.radial_button = QtWidgets.QPushButton("R")
        self.radial_button.setCheckable(True)
        self.radial_button.setChecked(
            drawable.radial_symmetry_enabled
        )
        self.radial_button.setToolTip(
            self._symmetry_tooltip("radial")
        )

        self.radial_count_spin = QtWidgets.QSpinBox()
        self.radial_count_spin.setRange(0, 32)
        self.radial_count_spin.setValue(
            drawable.radial_count_override
        )
        self.radial_count_spin.setToolTip(
            "0 uses the parent or global radial count. "
            "Any other value overrides it at this level"
        )

        self.radial_count_spin.setEnabled(
            drawable.radial_symmetry_enabled
        )

        for button in (
            self.horizontal_button,
            self.vertical_button,
            self.radial_button
        ):
            button.setFixedSize(24, 22)

        self.radial_count_spin.setFixedSize(48, 22)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(2, 1, 2, 1)
        layout.setSpacing(2)
        layout.addWidget(self.name_label, 1)
        layout.addWidget(self.horizontal_button)
        layout.addWidget(self.vertical_button)
        layout.addWidget(self.radial_button)
        layout.addWidget(self.radial_count_spin)

        self.horizontal_button.toggled.connect(
            self._horizontal_changed
        )
        self.vertical_button.toggled.connect(
            self._vertical_changed
        )
        self.radial_button.toggled.connect(
            self._radial_changed
        )
        self.radial_button.toggled.connect(
            self.radial_count_spin.setEnabled
        )
        self.radial_count_spin.valueChanged.connect(
            self._radial_count_changed
        )

    def _symmetry_tooltip(self, symmetry_type):
        level = "asset" if self.is_asset else "stroke"
        return "Allow global {} symmetry for this {}".format(
            symmetry_type,
            level
        )

    def _horizontal_changed(self, enabled):
        self.drawable.horizontal_symmetry_enabled = bool(enabled)
        self.symmetryChanged.emit(self.drawable)

    def _vertical_changed(self, enabled):
        self.drawable.vertical_symmetry_enabled = bool(enabled)
        self.symmetryChanged.emit(self.drawable)

    def _radial_changed(self, enabled):
        self.drawable.radial_symmetry_enabled = bool(enabled)
        self.symmetryChanged.emit(self.drawable)

    def _radial_count_changed(self, count):
        self.drawable.radial_count_override = int(count)
        self.symmetryChanged.emit(self.drawable)

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
        self._syncing_asset_tree = False

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

        self.asset_tree = QtWidgets.QTreeWidget()
        self.asset_tree.setColumnCount(2)
        self.asset_tree.setHeaderHidden(True)
        self.asset_tree.setColumnWidth(0, 24)
        self.asset_tree.setIndentation(14)
        self.asset_tree.setAnimated(True)

        header = self.asset_tree.header()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        header.resizeSection(0, 24)

        self.asset_tree.setIndentation(14)
        self.asset_tree.setAnimated(True)
        self.asset_tree.setMinimumWidth(250)
        self.asset_tree.setMaximumWidth(380)
        self.asset_tree.setSelectionMode(
            QtWidgets.QAbstractItemView.ExtendedSelection
        )
        self.asset_tree.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self.asset_tree.setUniformRowHeights(False)
        self.asset_tree.setToolTip(
            "Select assets or expand them to select individual strokes. "
            "Use Ctrl or Shift for multiple selection"
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
        toolbar_layout.addWidget(self.create_button)

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
        side_layout.addWidget(QtWidgets.QLabel("Asset List"))
        side_layout.addWidget(self.asset_tree)

        side_layout.addLayout(curve_buttons_layout)
        side_layout.addSpacing(8)
        side_layout.addWidget(QtWidgets.QLabel("File"))
        side_layout.addLayout(file_storage_layout)
        side_layout.addWidget(QtWidgets.QLabel("Maya Scene"))
        side_layout.addLayout(scene_storage_layout)

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
        self.content_splitter.setSizes([800, 300])

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

        self.asset_tree.itemSelectionChanged.connect(self._select_canvas_strokes)
        self.asset_tree.itemChanged.connect(self._tree_item_changed)

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

    def _tree_symmetry_changed(self, drawable):
        if drawable in self.canvas.assets:
            self.canvas.update()
            return

        if drawable in self.canvas.strokes:
            self.canvas.update()

    def _create_asset_tree_item(self, asset):
        item = QtWidgets.QTreeWidgetItem()
        item.setFlags(
            item.flags()
            | QtCore.Qt.ItemIsSelectable
            | QtCore.Qt.ItemIsEnabled
            | QtCore.Qt.ItemIsUserCheckable
        )
        item.setData(0, TREE_ROLE_OBJECT, asset)
        item.setData(0, TREE_ROLE_TYPE, TREE_TYPE_ASSET)
        visible_strokes = [
            stroke
            for stroke in asset.strokes
            if stroke in self.canvas.strokes and stroke.visible
        ]

        if not visible_strokes:
            check_state = QtCore.Qt.Unchecked
        elif len(visible_strokes) == len(asset.strokes):
            check_state = QtCore.Qt.Checked
        else:
            check_state = QtCore.Qt.PartiallyChecked

        item.setCheckState(0, check_state)
        return item


    def _create_stroke_tree_item(self, stroke):
        item = QtWidgets.QTreeWidgetItem()
        item.setFlags(
            item.flags()
            | QtCore.Qt.ItemIsSelectable
            | QtCore.Qt.ItemIsEnabled
            | QtCore.Qt.ItemIsUserCheckable
        )
        item.setData(0, TREE_ROLE_OBJECT, stroke)
        item.setData(0, TREE_ROLE_TYPE, TREE_TYPE_STROKE)
        item.setCheckState(
            0,
            QtCore.Qt.Checked
            if stroke.visible
            else QtCore.Qt.Unchecked
        )
        return item

    def _install_asset_tree_widget(self, item, asset):
        row_widget = ECurveTreeItemWidget(asset, is_asset=True)
        row_widget.symmetryChanged.connect(self._tree_symmetry_changed)

        item.setSizeHint(1, row_widget.sizeHint())
        self.asset_tree.setItemWidget(item, 1, row_widget)


    def _install_stroke_tree_widget(self, item, stroke):
        row_widget = ECurveTreeItemWidget(stroke, is_asset=False)
        row_widget.symmetryChanged.connect(self._tree_symmetry_changed)

        item.setSizeHint(1, row_widget.sizeHint())
        self.asset_tree.setItemWidget(item, 1, row_widget)


    def _create_standalone_tree_item(self, stroke):
        item = self._create_stroke_tree_item(stroke)
        item.setData(0, TREE_ROLE_TYPE, TREE_TYPE_STANDALONE)
        return item

    def _expanded_asset_names(self):
        names = set()

        for index in range(self.asset_tree.topLevelItemCount()):
            item = self.asset_tree.topLevelItem(index)

            if item.data(0, TREE_ROLE_TYPE) != TREE_TYPE_ASSET:
                continue

            asset = item.data(0, TREE_ROLE_OBJECT)

            if asset and item.isExpanded():
                names.add(asset.name)

        return names

    def _refresh_curve_list(self):
        if self._syncing_asset_tree:
            return

        selected_strokes = self.canvas.get_selected_strokes()
        active_stroke = self.canvas.get_selected_stroke()
        expanded_assets = self._expanded_asset_names()

        self._syncing_asset_tree = True
        previous_block_state = self.asset_tree.blockSignals(True)

        try:
            self.asset_tree.clear()

            added_strokes = set()
            active_item = None

            for asset in self.canvas.assets:
                asset_item = self._create_asset_tree_item(asset)
                self.asset_tree.addTopLevelItem(asset_item)
                self._install_asset_tree_widget(asset_item, asset)

                asset_strokes = [
                    stroke
                    for stroke in asset.strokes
                    if stroke in self.canvas.strokes
                ]

                asset_is_selected = (
                    bool(asset_strokes)
                    and all(
                        stroke in selected_strokes
                        for stroke in asset_strokes
                    )
                )

                asset_item.setSelected(asset_is_selected)
                asset_item.setExpanded(asset.name in expanded_assets)

                for stroke in asset_strokes:
                    stroke_item = self._create_stroke_tree_item(stroke)
                    asset_item.addChild(stroke_item)
                    self._install_stroke_tree_widget(stroke_item, stroke)

                    added_strokes.add(stroke)

                    if not asset_is_selected:
                        stroke_item.setSelected(
                            stroke in selected_strokes
                        )

                    if stroke is active_stroke:
                        active_item = stroke_item

            for stroke in self.canvas.strokes:
                if stroke in added_strokes:
                    continue

                standalone_item = self._create_standalone_tree_item(stroke)
                self.asset_tree.addTopLevelItem(standalone_item)
                self._install_stroke_tree_widget(
                    standalone_item,
                    stroke
                )

                standalone_item.setSelected(
                    stroke in selected_strokes
                )

                if stroke is active_stroke:
                    active_item = standalone_item

            if active_item:
                self.asset_tree.setCurrentItem(
                    active_item,
                    0,
                    QtCore.QItemSelectionModel.NoUpdate
                )

        finally:
            self.asset_tree.blockSignals(previous_block_state)
            self._syncing_asset_tree = False

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

    def _select_curve_list_item(self, active_stroke):
        if self._syncing_asset_tree:
            return

        self._syncing_asset_tree = True
        previous_block_state = self.asset_tree.blockSignals(True)

        try:
            selected_strokes = self.canvas.get_selected_strokes()
            self.asset_tree.clearSelection()
            active_item = None

            for index in range(self.asset_tree.topLevelItemCount()):
                top_item = self.asset_tree.topLevelItem(index)
                item_type = top_item.data(0, TREE_ROLE_TYPE)
                drawable = top_item.data(0, TREE_ROLE_OBJECT)

                if item_type == TREE_TYPE_ASSET:
                    asset_strokes = [
                        stroke
                        for stroke in drawable.strokes
                        if stroke in self.canvas.strokes
                    ]

                    asset_is_selected = (
                        bool(asset_strokes)
                        and all(
                            stroke in selected_strokes
                            for stroke in asset_strokes
                        )
                    )

                    top_item.setSelected(asset_is_selected)

                    for child_index in range(top_item.childCount()):
                        child = top_item.child(child_index)
                        stroke = child.data(0, TREE_ROLE_OBJECT)

                        child.setSelected(
                            not asset_is_selected
                            and stroke in selected_strokes
                        )

                        if stroke is active_stroke:
                            active_item = child

                elif drawable in self.canvas.strokes:
                    top_item.setSelected(
                        drawable in selected_strokes
                    )

                    if drawable is active_stroke:
                        active_item = top_item

            if active_item:
                parent = active_item.parent()

                if parent:
                    parent.setExpanded(True)

                self.asset_tree.setCurrentItem(
                    active_item,
                    0,
                    QtCore.QItemSelectionModel.NoUpdate
                )

        finally:
            self.asset_tree.blockSignals(previous_block_state)
            self._syncing_asset_tree = False

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
        if self._syncing_asset_tree:
            return

        self._syncing_asset_tree = True

        try:
            strokes = []
            active_stroke = None
            current_item = self.asset_tree.currentItem()

            for item in self.asset_tree.selectedItems():
                item_type = item.data(0, TREE_ROLE_TYPE)
                drawable = item.data(0, TREE_ROLE_OBJECT)

                if item_type == TREE_TYPE_ASSET:
                    asset_strokes = [
                        stroke
                        for stroke in drawable.strokes
                        if stroke in self.canvas.strokes
                        and stroke.visible
                    ]

                    for stroke in asset_strokes:
                        if stroke not in strokes:
                            strokes.append(stroke)

                    if item is current_item and asset_strokes:
                        active_stroke = asset_strokes[-1]

                elif (
                    item_type in (
                        TREE_TYPE_STROKE,
                        TREE_TYPE_STANDALONE
                    )
                    and drawable in self.canvas.strokes
                    and drawable.visible
                ):
                    if drawable not in strokes:
                        strokes.append(drawable)

                    if item is current_item:
                        active_stroke = drawable

            if active_stroke not in strokes:
                active_stroke = strokes[-1] if strokes else None

            self.canvas.set_selected_strokes(
                strokes,
                active_stroke=active_stroke
            )

        finally:
            self._syncing_asset_tree = False

    def _tree_item_changed(self, item, column):
        if self._syncing_asset_tree or column != 0:
            return

        drawable = item.data(0, TREE_ROLE_OBJECT)
        item_type = item.data(0, TREE_ROLE_TYPE)

        if drawable is None:
            return

        visible = item.checkState(0) == QtCore.Qt.Checked
        self._syncing_asset_tree = True

        try:
            if item_type == TREE_TYPE_ASSET:
                self._set_asset_item_visibility(
                    item,
                    drawable,
                    visible
                )
                return

            if item_type in (
                TREE_TYPE_STROKE,
                TREE_TYPE_STANDALONE
            ):
                self.canvas.set_stroke_visibility(
                    drawable,
                    visible,
                    notify=False
                )

                parent_item = item.parent()

                if parent_item:
                    self._update_asset_item_check_state(parent_item)

        finally:
            self._syncing_asset_tree = False

    def _update_asset_item_check_state(self, asset_item):
        asset = asset_item.data(0, TREE_ROLE_OBJECT)

        if asset is None:
            return

        child_states = [
            asset_item.child(index).checkState(0)
            for index in range(asset_item.childCount())
        ]

        if not child_states:
            state = QtCore.Qt.Unchecked
            asset.visible = False

        elif all(
            child_state == QtCore.Qt.Checked
            for child_state in child_states
        ):
            state = QtCore.Qt.Checked
            asset.visible = True

        elif all(
            child_state == QtCore.Qt.Unchecked
            for child_state in child_states
        ):
            state = QtCore.Qt.Unchecked
            asset.visible = False

        else:
            state = QtCore.Qt.PartiallyChecked
            asset.visible = True

        previous_block_state = self.asset_tree.blockSignals(True)

        try:
            asset_item.setCheckState(0, state)

        finally:
            self.asset_tree.blockSignals(previous_block_state)

    def _set_asset_item_visibility(
        self,
        asset_item,
        asset,
        visible
    ):
        previous_block_state = self.asset_tree.blockSignals(True)

        try:
            check_state = (
                QtCore.Qt.Checked
                if visible
                else QtCore.Qt.Unchecked
            )

            for index in range(asset_item.childCount()):
                child_item = asset_item.child(index)
                child_item.setCheckState(0, check_state)

            self.canvas.set_asset_visibility(
                asset,
                visible,
                notify=False
            )

        finally:
            self.asset_tree.blockSignals(previous_block_state)


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