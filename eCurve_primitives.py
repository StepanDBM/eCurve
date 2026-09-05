# eCurve_primitives.py

import math

try:
    from PySide6 import QtCore
except ImportError:
    from PySide2 import QtCore

from eCurve_drawables import ECurveAsset, ECurveStroke


PRIMITIVE_LINE = "line"
PRIMITIVE_TRIANGLE = "triangle"
PRIMITIVE_SQUARE = "square"
PRIMITIVE_DIAMOND = "diamond"
PRIMITIVE_CIRCLE = "circle"
PRIMITIVE_CROSS = "cross"
PRIMITIVE_ARROW = "arrow"
PRIMITIVE_CUBE = "cube"


def _points(values):
    return [QtCore.QPointF(x, y) for x, y in values]


def _stroke(values, closed=False):
    return ECurveStroke(_points(values), closed=closed)


def _circle_points(radius=64.0, segments=32):
    return [
        QtCore.QPointF(
            math.cos(math.tau * index / segments) * radius,
            math.sin(math.tau * index / segments) * radius
        )
        for index in range(segments)
    ]


def create_line():
    return ECurveAsset(
        name="Line",
        strokes=[
            _stroke([
                (-64.0, 0.0),
                (64.0, 0.0)
            ])
        ],
        asset_type="primitive",
        primitive_type=PRIMITIVE_LINE
    )


def create_triangle():
    return ECurveAsset(
        name="Triangle",
        strokes=[
            _stroke([
                (0.0, -64.0),
                (56.0, 40.0),
                (-56.0, 40.0)
            ], closed=True)
        ],
        asset_type="primitive",
        primitive_type=PRIMITIVE_TRIANGLE
    )


def create_square():
    return ECurveAsset(
        name="Square",
        strokes=[
            _stroke([
                (-56.0, -56.0),
                (56.0, -56.0),
                (56.0, 56.0),
                (-56.0, 56.0)
            ], closed=True)
        ],
        asset_type="primitive",
        primitive_type=PRIMITIVE_SQUARE
    )


def create_diamond():
    return ECurveAsset(
        name="Diamond",
        strokes=[
            _stroke([
                (0.0, -64.0),
                (64.0, 0.0),
                (0.0, 64.0),
                (-64.0, 0.0)
            ], closed=True)
        ],
        asset_type="primitive",
        primitive_type=PRIMITIVE_DIAMOND
    )


def create_circle():
    return ECurveAsset(
        name="Circle",
        strokes=[
            ECurveStroke(
                _circle_points(radius=64.0, segments=32),
                closed=True
            )
        ],
        asset_type="primitive",
        primitive_type=PRIMITIVE_CIRCLE
    )


def create_cross():
    return ECurveAsset(
        name="Cross",
        strokes=[
            _stroke([
                (-64.0, 0.0),
                (64.0, 0.0)
            ]),
            _stroke([
                (0.0, -64.0),
                (0.0, 64.0)
            ])
        ],
        asset_type="primitive",
        primitive_type=PRIMITIVE_CROSS
    )


def create_arrow():
    return ECurveAsset(
        name="Arrow",
        strokes=[
            _stroke([
                (0.0, 64.0),
                (0.0, -48.0)
            ]),
            _stroke([
                (-28.0, -20.0),
                (0.0, -48.0),
                (28.0, -20.0)
            ])
        ],
        asset_type="primitive",
        primitive_type=PRIMITIVE_ARROW
    )


def create_cube():
    return ECurveAsset(
        name="Cube",
        strokes=[
            _stroke([
                (-48.0, -32.0),
                (16.0, -48.0),
                (56.0, -8.0),
                (-8.0, 8.0)
            ], closed=True),
            _stroke([
                (-48.0, -32.0),
                (-48.0, 24.0),
                (-8.0, 56.0),
                (-8.0, 8.0)
            ]),
            _stroke([
                (-8.0, 56.0),
                (56.0, 40.0),
                (56.0, -8.0)
            ])
        ],
        asset_type="primitive",
        primitive_type=PRIMITIVE_CUBE
    )


PRIMITIVE_FACTORIES = {
    PRIMITIVE_LINE: create_line,
    PRIMITIVE_TRIANGLE: create_triangle,
    PRIMITIVE_SQUARE: create_square,
    PRIMITIVE_DIAMOND: create_diamond,
    PRIMITIVE_CIRCLE: create_circle,
    PRIMITIVE_CROSS: create_cross,
    PRIMITIVE_ARROW: create_arrow,
    PRIMITIVE_CUBE: create_cube
}


PRIMITIVE_INFO = {
    PRIMITIVE_LINE: {
        "name": "Line",
        "category": "Basic",
        "factory": create_line
    },
    PRIMITIVE_TRIANGLE: {
        "name": "Triangle",
        "category": "Basic",
        "factory": create_triangle
    },
    PRIMITIVE_SQUARE: {
        "name": "Square",
        "category": "Basic",
        "factory": create_square
    },
    PRIMITIVE_DIAMOND: {
        "name": "Diamond",
        "category": "Basic",
        "factory": create_diamond
    },
    PRIMITIVE_CIRCLE: {
        "name": "Circle",
        "category": "Basic",
        "factory": create_circle
    },
    PRIMITIVE_CROSS: {
        "name": "Cross",
        "category": "Control",
        "factory": create_cross
    },
    PRIMITIVE_ARROW: {
        "name": "Arrow",
        "category": "Control",
        "factory": create_arrow
    },
    PRIMITIVE_CUBE: {
        "name": "Cube",
        "category": "Control",
        "factory": create_cube
    }
}


def create_primitive(primitive_type):
    factory = PRIMITIVE_FACTORIES.get(primitive_type)

    if factory is None:
        raise ValueError(
            "Unsupported eCurve primitive: {}".format(primitive_type)
        )

    return factory()


def primitive_types():
    return tuple(PRIMITIVE_FACTORIES)


def primitive_info(primitive_type):
    return PRIMITIVE_INFO.get(primitive_type)