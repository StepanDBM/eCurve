# eCurve_asset_strip.py

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets

class eCurveAssetButton(QtWidgets.QToolButton):
    BUTTON_WIDTH = 66
    BUTTON_HEIGHT = 48
    THUMBNAIL_MARGIN = 4

    def __init__(self, item_data, parent=None):
        super().__init__(parent)

        self.item_data = item_data
        self.thumbnail = item_data.get("thumbnail", QtGui.QPixmap())

        self.setFixedSize(self.BUTTON_WIDTH, self.BUTTON_HEIGHT)
        self.setCheckable(False)
        self.setAttribute(QtCore.Qt.WA_Hover, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setToolTip(item_data.get("tooltip", item_data["name"]))
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.update()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)

        self._draw_background(painter)
        self._draw_thumbnail(painter)
        self._draw_name(painter)

    def _draw_background(self, painter):
        rect = QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        if not self.isEnabled():
            background = QtGui.QColor(48, 48, 48)
            border = QtGui.QColor(65, 65, 65)
        elif self.isDown():
            background = QtGui.QColor(42, 42, 42)
            border = QtGui.QColor(75, 135, 190)
        elif self.underMouse():
            background = QtGui.QColor(70, 70, 70)
            border = QtGui.QColor(220, 220, 220)
        else:
            background = QtGui.QColor(56, 56, 56)
            border = QtGui.QColor(78, 78, 78)

        painter.setBrush(background)
        painter.setPen(QtGui.QPen(border, 1.0))
        painter.drawRoundedRect(rect, 3.0, 3.0) 

    def _draw_thumbnail(self, painter):
        if self.thumbnail.isNull():
            return

        margin = self.THUMBNAIL_MARGIN
        available_rect = self.rect().adjusted(
            margin,
            margin,
            -margin,
            -margin
        )

        pixmap_size = self.thumbnail.size()
        pixmap_size.scale(
            available_rect.size(),
            QtCore.Qt.KeepAspectRatio
        )

        x = available_rect.center().x() - pixmap_size.width() * 0.5
        y = available_rect.center().y() - pixmap_size.height() * 0.5

        target_rect = QtCore.QRectF(
            x,
            y,
            pixmap_size.width(),
            pixmap_size.height()
        )

        painter.drawPixmap(
            target_rect,
            self.thumbnail,
            QtCore.QRectF(self.thumbnail.rect())
        )

    def _draw_name(self, painter):
        text = self.item_data.get("name", "")
        font = QtGui.QFont(self.font())
        font.setPixelSize(9)

        painter.setFont(font)

        metrics = QtGui.QFontMetrics(font)
        maximum_width = self.width() - 10
        text = metrics.elidedText(
            text,
            QtCore.Qt.ElideRight,
            maximum_width
        )

        text_width = metrics.horizontalAdvance(text)
        text_height = metrics.height()

        horizontal_padding = 4
        vertical_padding = 1
        badge_width = text_width + horizontal_padding * 2
        badge_height = text_height + vertical_padding * 2

        badge_rect = QtCore.QRectF(
            self.width() - badge_width - 3,
            self.height() - badge_height - 3,
            badge_width,
            badge_height
        )

        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(10, 10, 10, 145))
        painter.drawRoundedRect(badge_rect, 2.5, 2.5)

        text_rect = badge_rect.adjusted(
            horizontal_padding,
            vertical_padding,
            -horizontal_padding,
            -vertical_padding
        )

        text_color = QtGui.QColor(240, 240, 240, 220)

        if not self.isEnabled():
            text_color.setAlpha(100)

        painter.setPen(text_color)
        painter.drawText(
            text_rect,
            QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter,
            text
        )


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
        self.scroll_area.setFixedHeight(66)

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