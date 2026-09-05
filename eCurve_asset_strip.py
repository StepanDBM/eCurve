# eCurve_asset_strip.py

try:
    from PySide6 import QtCore, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtWidgets


class eCurveAssetButton(QtWidgets.QPushButton):
    def __init__(self, item_data, parent=None):
        super().__init__(item_data["name"], parent)

        self.item_data = item_data

        self.setFixedSize(68, 42)
        self.setCheckable(False)
        self.setToolTip(item_data.get("tooltip", item_data["name"]))

        self.setStyleSheet("""
            QPushButton {
                background-color: rgb(58, 58, 58);
                border: 1px solid rgb(78, 78, 78);
                border-radius: 3px;
                color: rgb(220, 220, 220);
                padding: 2px;
            }

            QPushButton:hover {
                background-color: rgb(72, 72, 72);
                border-color: rgb(120, 170, 220);
            }

            QPushButton:pressed {
                background-color: rgb(45, 45, 45);
                border-color: rgb(90, 145, 200);
            }
        """)


class eCurveAssetStrip(QtWidgets.QWidget):
    item_clicked = QtCore.Signal(dict)

    def __init__(self, items=None, parent=None):
        super().__init__(parent)

        self.items = []
        self.buttons = []

        self._create_widgets()
        self._create_layout()
        self.set_items(items or [])

    def _create_widgets(self):
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll_area.setFixedHeight(60)

        self.content_widget = QtWidgets.QWidget()
        self.content_layout = QtWidgets.QHBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 2, 0, 2)
        self.content_layout.setSpacing(4)
        self.content_layout.setAlignment(QtCore.Qt.AlignLeft)

        self.scroll_area.setWidget(self.content_widget)

    def _create_layout(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.scroll_area)

    def set_items(self, items):
        self.clear()
        self.items = list(items)

        for item_data in self.items:
            self.add_item(item_data)

    def add_item(self, item_data):
        button = eCurveAssetButton(item_data)
        button.clicked.connect(lambda checked=False, data=item_data: self.item_clicked.emit(data))

        self.buttons.append(button)
        self.content_layout.addWidget(button)

    def clear(self):
        while self.content_layout.count():
            layout_item = self.content_layout.takeAt(0)
            widget = layout_item.widget()

            if widget:
                widget.deleteLater()

        self.buttons = []