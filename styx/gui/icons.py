"""Small line icons, drawn from inline SVG so they follow the theme colour."""

from __future__ import annotations

from PyQt5.QtCore import QByteArray, QRectF, Qt
from PyQt5.QtGui import QIcon, QPainter, QPixmap
from PyQt5.QtSvg import QSvgRenderer

# 24x24 viewBox, 1.75 stroke, round caps/joins.
_PATHS = {
    "file": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/>'
            '<path d="M14 3v5h5"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2H5'
              'a2 2 0 0 1-2-2z"/>',
    "eye": '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/>'
           '<circle cx="12" cy="12" r="3"/>',
    "eye-off": '<path d="M3 3l18 18"/>'
               '<path d="M10.6 5.6A9.6 9.6 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a16.4 16.4 0 0 1-2.9 3.7"/>'
               '<path d="M6.6 6.7C3.9 8.4 2.5 12 2.5 12S6 18.5 12 18.5a9 9 0 0 0 4.4-1.1"/>'
               '<path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    "lock": '<rect x="4.5" y="10.5" width="15" height="10" rx="2"/>'
            '<path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/>',
    "unlock": '<rect x="4.5" y="10.5" width="15" height="10" rx="2"/>'
              '<path d="M8 10.5V7.5a4 4 0 0 1 7.7-1.5"/>',
    "drop": '<path d="M12 4v11"/><path d="M7.5 10.5 12 15l4.5-4.5"/>'
            '<path d="M4 17.5v1a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1"/>',
}


def svg(name: str, colour: str) -> bytes:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{colour}" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">'
        f"{_PATHS[name]}</svg>"
    ).encode()


def pixmap(name: str, colour: str, size: int = 20, ratio: float = 2.0) -> QPixmap:
    pm = QPixmap(int(size * ratio), int(size * ratio))
    pm.fill(Qt.transparent)
    renderer = QSvgRenderer(QByteArray(svg(name, colour)))
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter, QRectF(0, 0, pm.width(), pm.height()))
    painter.end()
    pm.setDevicePixelRatio(ratio)
    return pm


def icon(name: str, colour: str, size: int = 20) -> QIcon:
    return QIcon(pixmap(name, colour, size))
