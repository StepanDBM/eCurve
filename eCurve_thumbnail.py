# eCurve_thumbnail.py

try:
    from PySide6 import QtCore, QtGui
except ImportError:
    from PySide2 import QtCore, QtGui


def render_asset_thumbnail(
    asset,
    width=64,
    height=44,
    padding=5,
    stroke_color=None,
    background_color=None
):
    stroke_color = stroke_color or QtGui.QColor(220, 220, 220)
    pixmap = QtGui.QPixmap(width, height)

    if background_color is None:
        pixmap.fill(QtCore.Qt.transparent)
    else:
        pixmap.fill(background_color)

    bounds = asset.bounds()

    if bounds.isNull():
        return pixmap

    available_width = max(1.0, width - padding * 2.0)
    available_height = max(1.0, height - padding * 2.0)

    bounds_width = bounds.width()
    bounds_height = bounds.height()

    if bounds_width <= 0.0001 and bounds_height <= 0.0001:
        scale = 1.0
    elif bounds_width <= 0.0001:
        scale = available_height / bounds_height
    elif bounds_height <= 0.0001:
        scale = available_width / bounds_width
    else:
        scale = min(
            available_width / bounds_width,
            available_height / bounds_height
        )

    source_center = bounds.center()
    target_center = QtCore.QPointF(width * 0.5, height * 0.5)

    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
    painter.setBrush(QtCore.Qt.NoBrush)
    painter.setPen(QtGui.QPen(
        stroke_color,
        1.5,
        QtCore.Qt.SolidLine,
        QtCore.Qt.RoundCap,
        QtCore.Qt.RoundJoin
    ))

    for stroke in asset.strokes:
        points = [
            QtCore.QPointF(
                target_center.x() + (point.x() - source_center.x()) * scale,
                target_center.y() + (point.y() - source_center.y()) * scale
            )
            for point in stroke.points
        ]

        _draw_point_set(painter, points, stroke.closed)

    painter.end()
    return pixmap


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