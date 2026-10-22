"""The Styx desktop window."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt5.QtCore import QEvent, QObject, QSize, Qt, QThread
from PyQt5.QtGui import QIcon, QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QShortcut,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import strength
from .jobs import DECRYPT, ENCRYPT, JobSummary, JobWorker
from .theme import Theme, current_theme, palette, stylesheet
from .widgets import DropZone, ElidedLabel, display_path, PasswordField, RiverProgress, StrengthMeter

FORM, PROGRESS, RESULT = range(3)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _muted(text: str = "", role: str = "muted") -> QLabel:
    label = QLabel(text)
    label.setProperty("role", role)
    label.setWordWrap(True)
    return label


class StatCard(QFrame):
    def __init__(self, caption: str, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(0)
        self.value = QLabel("0")
        self.value.setObjectName("statValue")
        self.caption = _muted(caption)
        lay.addWidget(self.value)
        lay.addWidget(self.caption)

    def set(self, n: int, role: str | None = None) -> None:
        self.value.setText(str(n))
        self.value.setProperty("tone", role or "")
        self.value.style().unpolish(self.value)
        self.value.style().polish(self.value)
        self.setAccessibleName(f"{self.caption.text()}: {n}")


class DetailRow(QWidget):
    """A file that needs attention: its name, what happened, and why."""

    def __init__(self, path: Path, kind: str, tone: str, reason: str, parent=None):
        super().__init__(parent)
        self.setAccessibleName(f"{path.name}. {kind}. {reason}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(2)
        top = QHBoxLayout()
        name = ElidedLabel(path.name or str(path), Qt.ElideMiddle)
        name.setObjectName("detailName")
        name.setToolTip(str(path))
        badge = QLabel(kind)
        badge.setProperty("tone", tone)
        top.addWidget(name, 1)
        top.addWidget(badge)
        why = _muted(reason)
        lay.addLayout(top)
        lay.addWidget(why)


class MainWindow(QMainWindow):
    def __init__(self, theme: Theme | None = None, icon_path: str | None = None):
        super().__init__()
        self.theme = theme or current_theme()
        self.mode = ENCRYPT
        self._thread: QThread | None = None
        self._worker: JobWorker | None = None
        self._total = 0
        self.last_summary: JobSummary | None = None

        self.setWindowTitle("Styx")
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        self.setMinimumSize(540, 660)
        self.resize(580, 720)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(32, 26, 32, 28)
        outer.setSpacing(0)

        outer.addLayout(self._build_header())
        self.divider = RiverProgress(calm=True, amplitude=2.5, waves=6)
        outer.addSpacing(12)
        outer.addWidget(self.divider)
        outer.addSpacing(14)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_form())
        self.pages.addWidget(self._build_progress())
        self.pages.addWidget(self._build_result())
        outer.addWidget(self.pages, 1)

        self._shortcuts()
        self.apply_theme(self.theme)
        self.set_mode(ENCRYPT)
        self._validate()

    # ------------------------------------------------------------------ build
    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(16)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.wordmark = QLabel("Styx")
        self.wordmark.setObjectName("wordmark")
        self.wordmark.setAccessibleName("Styx")
        self.tagline = QLabel("Encrypt files and folders with a password.")
        self.tagline.setObjectName("tagline")
        titles.addWidget(self.wordmark)
        titles.addWidget(self.tagline)
        row.addLayout(titles, 1)

        switch = QFrame()
        switch.setObjectName("modeSwitch")
        s = QHBoxLayout(switch)
        s.setContentsMargins(3, 3, 3, 3)
        s.setSpacing(2)
        self.encrypt_tab = QPushButton("Encrypt")
        self.decrypt_tab = QPushButton("Decrypt")
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        for b, mode, key in ((self.encrypt_tab, ENCRYPT, "1"), (self.decrypt_tab, DECRYPT, "2")):
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(f"{b.text()} (Ctrl+{key})")
            b.setAccessibleName(f"{b.text()} mode")
            b.clicked.connect(lambda _=False, m=mode: self.set_mode(m))
            self.mode_group.addButton(b)
            s.addWidget(b)
        row.addWidget(switch, 0, Qt.AlignVCenter)
        return row

    def _build_form(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.drop = DropZone()
        self.drop.paths_dropped.connect(self.add_paths)
        self.drop.add_files_clicked.connect(self.choose_files)
        self.drop.add_folder_clicked.connect(self.choose_folder)
        self.drop.remove_requested.connect(self.remove_path)
        self.drop.clear_clicked.connect(lambda: self.set_paths([]))
        lay.addWidget(self.drop, 1)
        lay.addSpacing(20)

        self.password_label = QLabel("Password")
        self.password_label.setProperty("role", "section")
        self.password = PasswordField("Enter the password", "Password")
        self.password_label.setBuddy(self.password)
        self.password.textChanged.connect(self._validate)
        self.password.returnPressed.connect(self._submit_from_field)
        lay.addWidget(self.password_label)
        lay.addSpacing(6)
        lay.addWidget(self.password)

        self.meter = StrengthMeter()
        self.strength_label = _muted()
        self.strength_box = QWidget()
        sb = QVBoxLayout(self.strength_box)
        sb.setContentsMargins(0, 8, 0, 0)
        sb.setSpacing(6)
        sb.addWidget(self.meter)
        sb.addWidget(self.strength_label)
        lay.addWidget(self.strength_box)

        self.confirm_box = QWidget()
        cb = QVBoxLayout(self.confirm_box)
        cb.setContentsMargins(0, 14, 0, 0)
        cb.setSpacing(6)
        self.confirm_label = QLabel("Confirm password")
        self.confirm_label.setProperty("role", "section")
        self.confirm = PasswordField("Type it again", "Confirm password")
        self.confirm_label.setBuddy(self.confirm)
        self.confirm.textChanged.connect(self._validate)
        self.confirm.returnPressed.connect(self._submit_from_field)
        self.match_label = _muted()
        cb.addWidget(self.confirm_label)
        cb.addWidget(self.confirm)
        cb.addWidget(self.match_label)
        lay.addWidget(self.confirm_box)

        lay.addSpacing(16)
        self.note = _muted()
        lay.addWidget(self.note)
        lay.addSpacing(16)

        actions = QHBoxLayout()
        self.hint = _muted()
        self.start = QPushButton()
        self.start.setObjectName("primary")
        self.start.setCursor(Qt.PointingHandCursor)
        self.start.setMinimumWidth(180)
        self.start.clicked.connect(self.start_job)
        actions.addWidget(self.hint, 1)
        actions.addWidget(self.start)
        lay.addLayout(actions)
        return page

    def _build_progress(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.progress_title = QLabel()
        self.progress_title.setObjectName("pageTitle")
        self.progress_count = _muted()
        self.progress_file = ElidedLabel()
        self.progress_file.setObjectName("progressFile")
        self.progress_dir = ElidedLabel()
        self.progress_dir.setProperty("role", "muted")
        self.river = RiverProgress(amplitude=6, waves=3)
        self.river.setAccessibleName("Progress")
        self.cancel = QPushButton("Cancel")
        self.cancel.setCursor(Qt.PointingHandCursor)
        self.cancel.setToolTip("Stop after the current file (Esc)")
        self.cancel.clicked.connect(self.cancel_job)
        self.cancel_note = _muted("Each file is replaced only once it is fully processed, "
                                  "so stopping never leaves a half-written file.")

        lay.addStretch(2)
        lay.addWidget(self.progress_title)
        lay.addWidget(self.progress_count)
        lay.addSpacing(30)
        lay.addWidget(self.river)
        lay.addSpacing(14)
        lay.addWidget(self.progress_file)
        lay.addWidget(self.progress_dir)
        lay.addStretch(3)
        lay.addWidget(self.cancel_note)
        lay.addSpacing(12)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.cancel)
        lay.addLayout(row)
        return page

    def _build_result(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(8)
        self.result_title = QLabel()
        self.result_title.setObjectName("pageTitle")
        self.result_title.setWordWrap(True)
        self.result_text = _muted()

        grid = QGridLayout()
        grid.setSpacing(10)
        self.card_done = StatCard("Succeeded")
        self.card_skipped = StatCard("Skipped")
        self.card_failed = StatCard("Failed")
        self.card_legacy = StatCard("Old format")
        for i, card in enumerate((self.card_done, self.card_skipped, self.card_failed, self.card_legacy)):
            grid.addWidget(card, 0, i)

        self.details_label = QLabel("Details")
        self.details_label.setProperty("role", "section")
        self.details = QListWidget()
        self.details.setObjectName("details")
        self.details.setAccessibleName("Files that need attention")
        self.details.setSelectionMode(QListWidget.NoSelection)
        self.details.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.details.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.again = QPushButton()
        self.again.setObjectName("primary")
        self.again.setCursor(Qt.PointingHandCursor)
        self.again.clicked.connect(self.reset_form)

        lay.addWidget(self.result_title)
        lay.addWidget(self.result_text)
        lay.addSpacing(14)
        lay.addLayout(grid)
        lay.addSpacing(14)
        lay.addWidget(self.details_label)
        lay.addWidget(self.details, 1)
        self.result_spacer = QWidget()
        lay.addWidget(self.result_spacer, 1)
        lay.addSpacing(10)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.again)
        lay.addLayout(row)
        return page

    def _shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self._shortcut_files)
        QShortcut(QKeySequence("Ctrl+Shift+O"), self, activated=self._shortcut_folder)
        QShortcut(QKeySequence("Ctrl+1"), self, activated=lambda: self._shortcut_mode(ENCRYPT))
        QShortcut(QKeySequence("Ctrl+2"), self, activated=lambda: self._shortcut_mode(DECRYPT))
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self._escape)

    def _on_form(self) -> bool:
        return self.pages.currentIndex() == FORM

    def _shortcut_files(self) -> None:
        if self._on_form():
            self.choose_files()

    def _shortcut_folder(self) -> None:
        if self._on_form():
            self.choose_folder()

    def _shortcut_mode(self, mode: str) -> None:
        if self._on_form():
            self.set_mode(mode)

    def _escape(self) -> None:
        if self.pages.currentIndex() == PROGRESS:
            self.cancel_job()
        elif self.pages.currentIndex() == RESULT:
            self.reset_form()

    # ------------------------------------------------------------------ theme
    def apply_theme(self, theme: Theme) -> None:
        self.theme = theme
        app = QApplication.instance()
        app.setPalette(palette(theme))
        app.setStyleSheet(stylesheet(theme))
        for w in (self.divider, self.river, self.meter, self.password, self.confirm, self.drop):
            w.set_theme(theme)
        self._validate()

    # ------------------------------------------------------------------ state
    def set_mode(self, mode: str) -> None:
        self.mode = mode
        encrypting = mode == ENCRYPT
        self.encrypt_tab.setChecked(encrypting)
        self.decrypt_tab.setChecked(not encrypting)
        self.confirm_box.setVisible(encrypting)
        self.strength_box.setVisible(encrypting)
        if not encrypting:
            self.confirm.clear()
        self.note.setText(
            "Each file is replaced by its encrypted version. Keep the password safe: "
            "without it, the files cannot be recovered."
            if encrypting else
            "Each file is restored in place. With a wrong password, files are left unchanged."
        )
        self._validate()

    def paths(self) -> list[str]:
        return self.drop.paths()

    def set_paths(self, paths: list[str]) -> None:
        self.drop.set_paths(paths)
        self._validate()

    def add_paths(self, paths: list[str]) -> None:
        current = self.paths()
        known = {os.path.normcase(os.path.abspath(p)) for p in current}
        for p in paths:
            key = os.path.normcase(os.path.abspath(p))
            if key not in known:
                known.add(key)
                current.append(os.path.abspath(p))
        self.set_paths(current)

    def remove_path(self, path: str) -> None:
        self.set_paths([p for p in self.paths() if p != path])

    def choose_files(self) -> None:
        verb = "encrypt" if self.mode == ENCRYPT else "decrypt"
        files, _ = QFileDialog.getOpenFileNames(self, f"Choose files to {verb}")
        if files:
            self.add_paths(files)

    def choose_folder(self) -> None:
        verb = "encrypt" if self.mode == ENCRYPT else "decrypt"
        folder = QFileDialog.getExistingDirectory(self, f"Choose a folder to {verb}")
        if folder:
            self.add_paths([folder])

    def _set_state(self, widget, state: str) -> None:
        widget.setProperty("state", state)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _set_role(self, label: QLabel, role: str, text: str) -> None:
        label.setText(text)
        label.setProperty("role", role)
        label.style().unpolish(label)
        label.style().polish(label)

    def validation_error(self) -> str:
        """Why the start button is disabled, or an empty string."""
        if not self.paths():
            return "Add files or a folder to continue."
        if not self.password.text():
            return "Enter a password to continue."
        if self.mode == ENCRYPT and self.confirm.text() != self.password.text():
            return "Confirm the password to continue."
        return ""

    def _validate(self) -> None:
        if not hasattr(self, "start"):
            return
        encrypting = self.mode == ENCRYPT
        pw = self.password.text()

        if encrypting and pw:
            s = strength.estimate(pw)
            self.meter.set_score(s.score)
            role = "danger" if s.score < 2 else ("warn" if s.score == 2 else "ok")
            self._set_role(self.strength_label, role, f"{s.label}. {s.hint}")
            self.meter.setAccessibleName(f"Password strength: {s.label}")
        else:
            self.meter.set_score(-1)
            self._set_role(self.strength_label, "muted", "Long passphrases are stronger than short complex passwords.")

        confirm = self.confirm.text()
        if encrypting and confirm:
            if confirm == pw:
                self._set_role(self.match_label, "ok", "Passwords match.")
                self._set_state(self.confirm, "")
            elif pw.startswith(confirm):
                self._set_role(self.match_label, "muted", "Keep typing…")
                self._set_state(self.confirm, "")
            else:
                self._set_role(self.match_label, "danger", "Passwords don't match.")
                self._set_state(self.confirm, "error")
        else:
            self._set_role(self.match_label, "muted", "")
            self._set_state(self.confirm, "")
        self.match_label.setVisible(bool(self.match_label.text()))

        paths = self.paths()
        has_dir = any(Path(p).is_dir() for p in paths)
        noun = _plural(len(paths), "item" if has_dir else "file") if paths else "files"
        self.start.setText(f"{'Encrypt' if encrypting else 'Decrypt'} {noun}")
        error = self.validation_error()
        self.start.setEnabled(not error)
        self.hint.setText(error)
        self.start.setToolTip(error or "Start (Enter)")

    def _submit_from_field(self) -> None:
        if self.mode == ENCRYPT and self.sender() is self.password and not self.confirm.text():
            self.confirm.setFocus()
            return
        if self.start.isEnabled():
            self.start_job()

    # ------------------------------------------------------------------ jobs
    def start_job(self) -> None:
        if self.validation_error() or self._thread is not None:
            return
        verb = "Encrypting" if self.mode == ENCRYPT else "Decrypting"
        self.progress_title.setText(verb)
        self.progress_count.setText("Listing files…")
        self.progress_file.setText("")
        self.progress_dir.setText("")
        self.cancel.setEnabled(True)
        self.cancel.setText("Cancel")
        self.river.setRange(0, 1)
        self.river.setValue(0)
        self.river.set_flowing(True)
        self.encrypt_tab.setEnabled(False)
        self.decrypt_tab.setEnabled(False)
        self.pages.setCurrentIndex(PROGRESS)
        self.cancel.setFocus()

        password = self.password.text()
        self.password.clear()
        self.confirm.clear()

        self._thread = QThread(self)
        self._worker = JobWorker(self.mode, self.paths(), password)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.started.connect(self._on_started)
        self._worker.file_started.connect(self._on_file_started)
        self._worker.file_finished.connect(self._on_file_finished)
        self._worker.finished.connect(self._on_finished)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.start()

    def cancel_job(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.cancel.setEnabled(False)
            self.cancel.setText("Stopping…")

    def _on_started(self, total: int) -> None:
        self._total = total
        self.river.setRange(0, max(total, 1))
        self.river.setValue(0)
        self.progress_count.setText(_plural(total, "file") + " to process")

    def _on_file_started(self, index: int, path: str) -> None:
        self.progress_count.setText(f"File {index + 1} of {self._total}")
        p = Path(path)
        self.progress_file.setText(p.name)
        self.progress_dir.setText(display_path(p.parent))
        self.river.setAccessibleDescription(f"File {index + 1} of {self._total}")

    def _on_file_finished(self, index: int, path: str, outcome: str, detail: str) -> None:
        self.river.setValue(index + 1)

    def _on_finished(self, summary: JobSummary) -> None:
        self.river.set_flowing(False)
        if self._thread is not None:
            self._thread.quit()  # run() has returned; let the thread's event loop end
            self._thread.wait()
            self._thread.deleteLater()
        self._thread = None
        self._worker = None
        self.encrypt_tab.setEnabled(True)
        self.decrypt_tab.setEnabled(True)
        self.show_summary(summary)

    def show_summary(self, s: JobSummary) -> None:
        self.last_summary = s
        encrypting = s.mode == ENCRYPT
        verb = "encrypted" if encrypting else "decrypted"
        n_done = len(s.done)

        if s.cancelled:
            title = "Stopped"
            text = f"{_plural(n_done, 'file')} {verb} before you cancelled. The rest were not touched."
        elif not s.failed and n_done:
            title = f"{_plural(n_done, 'file')} {verb}"
            text = "Everything went through." if not s.skipped else "Some files were skipped; see below."
        elif not s.failed and not n_done:
            title = f"Nothing to {verb[:-1]}"
            text = "No file needed processing." if s.skipped else "The selection contained no files."
        elif s.bad_password and s.bad_password == len(s.failed) and not n_done:
            title = "Wrong password?"
            text = ("No file could be decrypted. Check the password: a wrong password and a "
                    "modified file look the same. The files were left unchanged.")
        else:
            title = "Finished with problems"
            n = len(s.failed)
            text = (f"{_plural(n, 'file')} could not be {verb}. "
                    f"{'It was' if n == 1 else 'They were'} left unchanged.")
        if s.legacy:
            n = len(s.legacy)
            text += (f" {_plural(n, 'file')} used the old format without tamper protection: "
                     f"encrypt {'it' if n == 1 else 'them'} again to upgrade.")
        self.result_title.setText(title)
        self.result_text.setText(text)

        self.card_done.set(n_done, "ok" if n_done else None)
        self.card_skipped.set(len(s.skipped), "warn" if s.skipped else None)
        self.card_failed.set(len(s.failed), "danger" if s.failed else None)
        self.card_legacy.set(len(s.legacy), "warn" if s.legacy else None)
        self.card_legacy.setVisible(not encrypting)

        self.details.clear()
        rows = [("Failed", "danger", p, why) for p, why in s.failed]
        rows += [("Skipped", "warn", p, why) for p, why in s.skipped]
        rows += [("Old format", "warn", p, "Decrypted. Encrypt it again to add tamper protection.")
                 for p in s.legacy]
        for kind, tone, path, why in rows:
            row = DetailRow(Path(path), kind, tone, why)
            item = QListWidgetItem()
            item.setToolTip(str(path))
            item.setData(Qt.AccessibleTextRole, row.accessibleName())
            width = max(self.details.viewport().width(), 420) - 8
            item.setSizeHint(QSize(1, row.layout().totalHeightForWidth(width)))
            self.details.addItem(item)
            self.details.setItemWidget(item, row)
        has_rows = bool(rows)
        self.details_label.setVisible(has_rows)
        self.details.setVisible(has_rows)
        self.result_spacer.setVisible(not has_rows)

        retry = s.bad_password and not n_done
        self.again.setText("Try another password" if retry else
                           ("Encrypt more files" if encrypting else "Decrypt more files"))
        self._retry_keeps_selection = bool(retry or s.cancelled)
        self.pages.setCurrentIndex(RESULT)
        self.again.setFocus()

    def reset_form(self) -> None:
        if not getattr(self, "_retry_keeps_selection", False):
            self.set_paths([])
        self._retry_keeps_selection = False
        self.password.clear()
        self.confirm.clear()
        self.pages.setCurrentIndex(FORM)
        self._validate()
        (self.password if self.paths() else self.drop.add_files).setFocus()

    # ------------------------------------------------------------------ window
    def closeEvent(self, event) -> None:  # noqa: N802
        if self._thread is not None:
            answer = QMessageBox.question(
                self, "Stop and quit?",
                "Styx is still working. Stop after the current file and quit?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self.cancel_job()
            self._thread.quit()
            self._thread.wait()
        event.accept()


class _ThemeWatcher(QObject):
    """Re-reads the system appearance whenever the app is brought to the front."""

    def __init__(self, window: MainWindow):
        super().__init__(window)
        self.window = window

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() == QEvent.ApplicationActivate:
            theme = current_theme()
            if theme != self.window.theme:
                self.window.apply_theme(theme)
        return False


def run(argv: list[str] | None = None, icon_path: str | None = None) -> int:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName("Styx")
    app.setStyle("Fusion")
    window = MainWindow(icon_path=icon_path)
    app.installEventFilter(_ThemeWatcher(window))
    window.show()
    return app.exec_()
