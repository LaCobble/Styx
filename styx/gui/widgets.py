"""Custom widgets: the river progress line, strength meter, password field, drop zone."""

from __future__ import annotations

import math
from pathlib import Path

from PyQt5.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import icons
from .theme import DARK, Theme


def display_path(path: str | Path) -> str:
    """Shorten the home folder to ``~`` for display."""
    p = str(path)
    home = str(Path.home())
    if p == home or p.startswith(home + ("\\" if "\\" in home else "/")):
        return "~" + p[len(home):]
    return p


class RiverProgress(QProgressBar):
    """A progress bar drawn as a river: the brass current advances as files cross.

    It stays a real ``QProgressBar`` so assistive technologies read its value.
    With ``calm=True`` it is a static divider (no value, no coin).
    """

    def __init__(self, parent=None, *, calm: bool = False, amplitude: float = 4.0, waves: float = 3.5):
        super().__init__(parent)
        self._theme: Theme = DARK
        self._calm = calm
        self._amp = amplitude
        self._waves = waves
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)
        self.setTextVisible(False)
        self.setRange(0, 100)
        self.setValue(0)
        self.setMinimumHeight(int(amplitude * 2 + 14))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if calm:
            self.setFocusPolicy(Qt.NoFocus)
            self.setAccessibleName("")

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def set_flowing(self, flowing: bool) -> None:
        """Animate the water gently while work is in progress."""
        if flowing and not self._timer.isActive():
            self._timer.start()
        elif not flowing:
            self._timer.stop()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.12) % (2 * math.pi)
        self.update()

    def _path(self, rect: QRectF) -> QPainterPath:
        path = QPainterPath()
        mid = rect.center().y()
        steps = max(int(rect.width() / 3), 2)
        for i in range(steps + 1):
            x = rect.left() + rect.width() * i / steps
            y = mid + self._amp * math.sin(i / steps * self._waves * 2 * math.pi + self._phase)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        return path

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        t = self._theme
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pad = 8.0
        rect = QRectF(self.rect()).adjusted(pad, 0, -pad, 0)
        path = self._path(rect)
        width = 1.5 if self._calm else 3.0

        p.setPen(QPen(QColor(t.border), width, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(path)
        if self._calm:
            return

        span = self.maximum() - self.minimum()
        fraction = (self.value() - self.minimum()) / span if span > 0 else 0.0
        fraction = min(max(fraction, 0.0), 1.0)
        if fraction > 0:
            p.save()
            p.setClipRect(QRectF(0, 0, rect.left() + rect.width() * fraction, self.height()))
            p.setPen(QPen(QColor(t.accent), width, Qt.SolidLine, Qt.RoundCap))
            p.drawPath(path)
            p.restore()

        # The obol: a small coin riding the current at the progress point.
        x = rect.left() + rect.width() * fraction
        y = path.pointAtPercent(min(max(fraction, 0.0), 1.0)).y()
        p.setPen(QPen(QColor(t.bg), 2))
        p.setBrush(QColor(t.accent))
        p.drawEllipse(QPointF(x, y), 6.5, 6.5)


class ElidedLabel(QLabel):
    """Single-line label that shortens its text with an ellipsis instead of clipping it."""

    def __init__(self, text: str = "", mode=Qt.ElideMiddle, parent=None):
        super().__init__(parent)
        self._full = ""
        self._mode = mode
        self.setMinimumWidth(10)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802
        self._full = text
        self.setToolTip(text)
        self.setAccessibleName(text)
        super().setText(text)
        self.update()

    def full_text(self) -> str:
        return self._full

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setPen(self.palette().color(self.foregroundRole()))
        rect = self.contentsRect()
        text = self.fontMetrics().elidedText(self._full, self._mode, rect.width())
        p.drawText(rect, int(self.alignment()) | Qt.AlignVCenter, text)


class StrengthMeter(QWidget):
    """Four segments filled according to a 0..4 score."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._theme: Theme = DARK
        self._score = -1
        self.setFixedHeight(4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def set_score(self, score: int) -> None:
        self._score = score
        self.update()

    def colour(self) -> str:
        t = self._theme
        return (t.danger, t.danger, t.warn, t.ok, t.ok)[max(self._score, 0)]

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        gap = 6
        w = (self.width() - 3 * gap) / 4
        filled = 0 if self._score < 0 else max(self._score, 1)
        for i in range(4):
            colour = QColor(self.colour() if i < filled else self._theme.border)
            p.setPen(Qt.NoPen)
            p.setBrush(colour)
            p.drawRoundedRect(QRectF(i * (w + gap), 0, w, self.height()), 2, 2)


class PasswordField(QLineEdit):
    """Password input with a keyboard-reachable show/hide button inside it."""

    def __init__(self, placeholder: str, accessible_name: str, parent=None):
        super().__init__(parent)
        self._theme: Theme = DARK
        self.setEchoMode(QLineEdit.Password)
        self.setPlaceholderText(placeholder)
        self.setAccessibleName(accessible_name)
        self.setMinimumHeight(42)
        self.toggle = QToolButton(self)
        self.toggle.setCursor(Qt.PointingHandCursor)
        self.toggle.setCheckable(True)
        self.toggle.setIconSize(QSize(18, 18))
        self.toggle.setFixedSize(30, 30)
        self.toggle.toggled.connect(self._on_toggle)
        self._on_toggle(False)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self._on_toggle(self.toggle.isChecked())

    def _on_toggle(self, shown: bool) -> None:
        self.setEchoMode(QLineEdit.Normal if shown else QLineEdit.Password)
        label = "Hide password" if shown else "Show password"
        self.toggle.setIcon(icons.icon("eye-off" if shown else "eye", self._theme.muted, 18))
        self.toggle.setToolTip(label)
        self.toggle.setAccessibleName(label)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.toggle.move(self.width() - self.toggle.width() - 6, (self.height() - self.toggle.height()) // 2)


class ItemRow(QWidget):
    """One selected file or folder in the drop zone list."""

    remove_requested = pyqtSignal(str)

    def __init__(self, path: str, theme: Theme, parent=None):
        super().__init__(parent)
        self.path = path
        p = Path(path)
        is_dir = p.is_dir()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 4, 4)
        lay.setSpacing(10)
        glyph = QLabel()
        glyph.setPixmap(icons.pixmap("folder" if is_dir else "file", theme.muted, 18))
        glyph.setFixedWidth(20)
        name = QLabel(p.name or str(p))
        name.setToolTip(str(p))
        where = ElidedLabel(display_path(p.parent))
        where.setProperty("role", "muted")
        remove = QToolButton()
        remove.setIcon(icons.icon("close", theme.muted, 16))
        remove.setIconSize(QSize(16, 16))
        remove.setToolTip(f"Remove {p.name}")
        remove.setAccessibleName(f"Remove {p.name}")
        remove.setCursor(Qt.PointingHandCursor)
        remove.clicked.connect(lambda: self.remove_requested.emit(self.path))
        lay.addWidget(glyph)
        lay.addWidget(name)
        lay.addWidget(where, 1)
        lay.addWidget(remove)


class DropZone(QFrame):
    """Accepts dropped files and folders; lists the current selection."""

    paths_dropped = pyqtSignal(list)
    add_files_clicked = pyqtSignal()
    add_folder_clicked = pyqtSignal()
    remove_requested = pyqtSignal(str)
    clear_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._theme: Theme = DARK
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setProperty("dragActive", False)
        self.setMinimumHeight(190)
        self.setAccessibleName("Files to process")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 14)
        outer.setSpacing(10)

        # Empty state
        self.empty = QWidget()
        e = QVBoxLayout(self.empty)
        e.setContentsMargins(0, 0, 0, 0)
        e.setSpacing(6)
        e.addStretch(1)
        self.drop_glyph = QLabel()
        self.drop_glyph.setAlignment(Qt.AlignCenter)
        title = QLabel("Drop files or folders here")
        title.setObjectName("dropTitle")
        title.setAlignment(Qt.AlignCenter)
        sub = QLabel("Folders are processed with everything inside them.")
        sub.setProperty("role", "muted")
        sub.setAlignment(Qt.AlignCenter)
        e.addWidget(self.drop_glyph)
        e.addWidget(title)
        e.addWidget(sub)
        e.addStretch(1)

        # Filled state
        self.list = QListWidget()
        self.list.setObjectName("itemList")
        self.list.setAccessibleName("Selected files and folders")
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.installEventFilter(self)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.count = QLabel()
        self.count.setProperty("role", "muted")
        self.add_files = QPushButton("Add files…")
        self.add_files.setToolTip("Add files (Ctrl+O)")
        self.add_folder = QPushButton("Add folder…")
        self.add_folder.setToolTip("Add a folder (Ctrl+Shift+O)")
        self.clear = QPushButton("Clear")
        self.clear.setToolTip("Remove everything from the list")
        for b in (self.add_files, self.add_folder, self.clear):
            b.setCursor(Qt.PointingHandCursor)
        self.add_files.clicked.connect(self.add_files_clicked)
        self.add_folder.clicked.connect(self.add_folder_clicked)
        self.clear.clicked.connect(self.clear_clicked)
        buttons.addStretch(1)
        buttons.addWidget(self.count)
        buttons.addSpacing(6)
        buttons.addWidget(self.clear)
        buttons.addWidget(self.add_files)
        buttons.addWidget(self.add_folder)
        buttons.addStretch(1)

        outer.addWidget(self.empty, 1)
        outer.addWidget(self.list, 1)
        outer.addLayout(buttons)
        self.set_paths([])

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.drop_glyph.setPixmap(icons.pixmap("drop", theme.muted, 30))
        self.set_paths(self.paths())

    def paths(self) -> list[str]:
        return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())]

    def set_paths(self, paths: list[str]) -> None:
        self.list.clear()
        for path in paths:
            row = ItemRow(path, self._theme)
            row.remove_requested.connect(self.remove_requested)
            item = QListWidgetItem()
            item.setData(Qt.UserRole, path)
            item.setData(Qt.AccessibleTextRole, Path(path).name)
            item.setToolTip(path)
            item.setSizeHint(QSize(0, 38))
            self.list.addItem(item)
            self.list.setItemWidget(item, row)
        filled = bool(paths)
        self.empty.setVisible(not filled)
        self.list.setVisible(filled)
        self.clear.setVisible(filled)
        self.count.setVisible(filled)
        n = len(paths)
        self.count.setText(f"{n} item{'s' if n != 1 else ''}")

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self.list and event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            item = self.list.currentItem()
            if item is not None:
                self.remove_requested.emit(item.data(Qt.UserRole))
                return True
        return super().eventFilter(obj, event)

    # Drag and drop
    def _set_drag(self, active: bool) -> None:
        self.setProperty("dragActive", active)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls() and any(u.isLocalFile() for u in event.mimeData().urls()):
            event.acceptProposedAction()
            self._set_drag(True)
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._set_drag(False)

    def dropEvent(self, event) -> None:  # noqa: N802
        self._set_drag(False)
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            event.acceptProposedAction()
            self.paths_dropped.emit(paths)
