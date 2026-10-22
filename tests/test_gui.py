"""Tests for the desktop interface (run headless with Qt's offscreen platform)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STYX_THEME", "dark")

import pytest

pytest.importorskip("PyQt5")
pytest.importorskip("pytestqt")

from PyQt5.QtCore import QMimeData, QPoint, Qt, QUrl
from PyQt5.QtGui import QDropEvent

from styx import encrypt_file
from styx.gui import strength
from styx.gui.app import FORM, PROGRESS, RESULT, MainWindow
from styx.gui.jobs import DECRYPT, ENCRYPT, run_job
from styx.gui.theme import DARK, LIGHT

PASSWORD = "river ferry obol night"


@pytest.fixture
def window(qtbot):
    w = MainWindow(theme=DARK)
    qtbot.addWidget(w)
    w.show()
    return w


@pytest.fixture
def files(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"alpha")
    sub = tmp_path / "folder"
    sub.mkdir()
    (sub / "b.txt").write_bytes(b"bravo")
    (sub / "c.txt").write_bytes(b"charlie")
    return tmp_path


def run_to_result(qtbot, w):
    qtbot.mouseClick(w.start, Qt.LeftButton)
    qtbot.waitUntil(lambda: w.pages.currentIndex() == RESULT, timeout=30000)
    return w.last_summary


# --------------------------------------------------------------- pure helpers

def test_strength_scores():
    assert strength.estimate("").score == 0
    assert strength.estimate("password").score == 0
    assert strength.estimate("aaaaaaaaaaaa").score <= 1
    assert strength.estimate("abcdefgh").score <= 1
    assert strength.estimate(PASSWORD).score >= 3
    assert strength.estimate("Tr0ub4dor&3").score >= 2


def test_run_job_roundtrip_and_wrong_password(files):
    targets = [files / "a.txt", files / "folder"]
    events = []
    s = run_job(ENCRYPT, targets, PASSWORD, on_start=events.append)
    assert events == [3]
    assert len(s.done) == 3 and not s.failed
    assert (files / "a.txt").read_bytes().startswith(b"STYX")

    again = run_job(ENCRYPT, targets, PASSWORD)
    assert not again.done and len(again.skipped) == 3

    bad = run_job(DECRYPT, targets, "nope")
    assert len(bad.failed) == 3 and bad.bad_password == 3
    assert (files / "a.txt").read_bytes().startswith(b"STYX")  # left unchanged

    good = run_job(DECRYPT, targets, PASSWORD)
    assert len(good.done) == 3
    assert (files / "folder" / "c.txt").read_bytes() == b"charlie"


def test_run_job_cancel_and_missing(files):
    calls = []
    s = run_job(ENCRYPT, [files / "folder", files / "gone.txt"], PASSWORD,
                on_file=lambda i, p: calls.append(p), should_cancel=lambda: len(calls) >= 1)
    assert s.cancelled and len(s.done) == 1
    assert any("no longer exists" in why for _, why in s.skipped)


# --------------------------------------------------------------- window

def test_start_disabled_until_form_is_complete(window, files):
    w = window
    assert not w.start.isEnabled()
    assert "Add files" in w.hint.text()
    w.add_paths([str(files / "a.txt")])
    assert not w.start.isEnabled()
    w.password.setText(PASSWORD)
    assert not w.start.isEnabled()  # confirmation still missing
    w.confirm.setText(PASSWORD + "x")
    assert not w.start.isEnabled()
    assert "don't match" in w.match_label.text()
    w.confirm.setText(PASSWORD)
    assert w.start.isEnabled()
    assert w.start.text() == "Encrypt 1 file"


def test_strength_feedback_and_toggle(window):
    w = window
    w.password.setText("password")
    assert w.strength_label.text().startswith("Too weak")
    w.password.setText(PASSWORD)
    assert "strong" in w.strength_label.text().lower()
    w.password.toggle.click()
    assert w.password.echoMode() == w.password.Normal
    w.password.toggle.click()
    assert w.password.echoMode() == w.password.Password


def test_decrypt_mode_hides_confirmation(window, files):
    w = window
    w.decrypt_tab.click()
    assert w.mode == DECRYPT
    assert w.confirm_box.isHidden() and w.strength_box.isHidden()
    w.add_paths([str(files / "a.txt")])
    w.password.setText(PASSWORD)
    assert w.start.isEnabled()
    assert w.start.text() == "Decrypt 1 file"


def test_paths_are_deduplicated_and_removable(window, files):
    w = window
    a, folder = str(files / "a.txt"), str(files / "folder")
    w.add_paths([a, folder, a])
    assert w.paths() == [a, folder]
    w.remove_path(a)
    assert w.paths() == [folder]
    w.drop.clear.click()
    assert w.paths() == []


def test_drop_adds_files(window, files):
    w = window
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(files / "a.txt")), QUrl.fromLocalFile(str(files / "folder"))])
    event = QDropEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    w.drop.dropEvent(event)
    assert [os.path.basename(p) for p in w.paths()] == ["a.txt", "folder"]
    assert w.start.text() == "Encrypt 2 items"


def test_encrypt_then_decrypt_flow(qtbot, window, files):
    w = window
    w.add_paths([str(files / "a.txt"), str(files / "folder")])
    w.password.setText(PASSWORD)
    w.confirm.setText(PASSWORD)

    with qtbot.waitSignal(w.pages.currentChanged, timeout=5000):
        w.start.click()
    assert w.pages.currentIndex() in (PROGRESS, RESULT)
    assert w.password.text() == "" and w.confirm.text() == ""  # not kept around
    qtbot.waitUntil(lambda: w.pages.currentIndex() == RESULT, timeout=30000)
    s = w.last_summary
    assert len(s.done) == 3 and not s.failed
    assert w.result_title.text() == "3 files encrypted"
    assert (files / "folder" / "b.txt").read_bytes().startswith(b"STYX")

    w.again.click()
    assert w.pages.currentIndex() == FORM and w.paths() == []

    w.decrypt_tab.click()
    w.add_paths([str(files / "a.txt"), str(files / "folder")])
    w.password.setText(PASSWORD)
    s = run_to_result(qtbot, w)
    assert len(s.done) == 3
    assert (files / "a.txt").read_bytes() == b"alpha"


def test_wrong_password_is_explained_and_selection_kept(qtbot, window, tmp_path):
    w = window
    target = tmp_path / "secret.txt"
    target.write_bytes(b"secret")
    encrypt_file(target, PASSWORD)
    before = target.read_bytes()

    w.decrypt_tab.click()
    w.add_paths([str(target)])
    w.password.setText("not the password")
    s = run_to_result(qtbot, w)
    assert s.bad_password == 1
    assert w.result_title.text() == "Wrong password?"
    assert "left unchanged" in w.result_text.text()
    assert w.again.text() == "Try another password"
    assert target.read_bytes() == before

    w.again.click()
    assert w.pages.currentIndex() == FORM
    assert w.paths() == [str(target)]


def test_theme_switch(window):
    window.apply_theme(LIGHT)
    assert window.theme is LIGHT
    window.apply_theme(DARK)
    assert window.theme is DARK
