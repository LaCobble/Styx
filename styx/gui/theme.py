"""Colours, fonts and the Qt style sheet.

The palette takes its cue from the Styx itself: dark river water, bone-pale
text, and a single brass accent, the colour of the obol paid to cross.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PyQt5.QtGui import QColor, QFont, QFontDatabase, QPalette
from PyQt5.QtWidgets import QApplication

ASSETS = Path(__file__).resolve().parent / "assets"


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str  # window
    surface: str  # panels, inputs
    surface_alt: str  # hover, drop zone highlight
    border: str  # dividers and card outlines
    field_border: str  # input outlines (3:1 against the background, WCAG 1.4.11)
    text: str
    muted: str  # secondary text (meets WCAG AA on bg and surface)
    accent: str  # the brass
    on_accent: str  # text on the accent
    accent_soft: str  # accent tint for selected states
    ok: str
    danger: str
    warn: str

    @property
    def dark(self) -> bool:
        return self.name == "dark"


DARK = Theme(
    name="dark",
    bg="#12161D",
    surface="#1A1F29",
    surface_alt="#222936",
    border="#343C4C",
    field_border="#626C80",
    text="#ECE7DC",
    muted="#A3AAB7",
    accent="#D4AF6A",
    on_accent="#1B1407",
    accent_soft="#2E2B25",
    ok="#8FCAA6",
    danger="#F0907F",
    warn="#E6C27A",
)

LIGHT = Theme(
    name="light",
    bg="#E8ECF1",
    surface="#F8F9FB",
    surface_alt="#EEF1F6",
    border="#C3CAD5",
    field_border="#7A8494",
    text="#151A23",
    muted="#4E5766",
    accent="#7A561A",
    on_accent="#FFFFFF",
    accent_soft="#EFE6D6",
    ok="#226B44",
    danger="#AE2A20",
    warn="#7A561A",
)


def system_prefers_dark() -> bool:
    """Best-effort detection of the OS appearance (Qt 5 has no API for it)."""
    forced = os.environ.get("STYX_THEME", "").lower()
    if forced in ("dark", "light"):
        return forced == "dark"
    if sys.platform == "darwin":
        try:
            out = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, timeout=2,
            )
            return out.stdout.strip().lower() == "dark"
        except (OSError, subprocess.SubprocessError):
            return True
    if sys.platform.startswith("win"):
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0
        except OSError:
            return True
    # Linux and others: GTK/KDE themes usually reach Qt's default palette.
    app = QApplication.instance()
    if app is not None:
        return app.style().standardPalette().color(QPalette.Window).lightness() < 128
    return True


def current_theme() -> Theme:
    return DARK if system_prefers_dark() else LIGHT


_display_family: str | None = None


def display_family() -> str:
    """Family name of the bundled display face (Marcellus), loaded once."""
    global _display_family
    if _display_family is None:
        font_id = QFontDatabase.addApplicationFont(str(ASSETS / "Marcellus-Regular.ttf"))
        families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
        _display_family = families[0] if families else "Serif"
    return _display_family


def display_font(pixel_size: int) -> QFont:
    font = QFont(display_family())
    font.setPixelSize(pixel_size)
    font.setStyleStrategy(QFont.PreferAntialias)
    return font


def palette(t: Theme) -> QPalette:
    p = QPalette()
    for role, colour in (
        (QPalette.Window, t.bg),
        (QPalette.WindowText, t.text),
        (QPalette.Base, t.surface),
        (QPalette.AlternateBase, t.surface_alt),
        (QPalette.Text, t.text),
        (QPalette.Button, t.surface),
        (QPalette.ButtonText, t.text),
        (QPalette.Highlight, t.accent),
        (QPalette.HighlightedText, t.on_accent),
        (QPalette.ToolTipBase, t.surface),
        (QPalette.ToolTipText, t.text),
        (QPalette.PlaceholderText, t.muted),
        (QPalette.Link, t.accent),
    ):
        p.setColor(role, QColor(colour))
    p.setColor(QPalette.Disabled, QPalette.Text, QColor(t.muted))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(t.muted))
    p.setColor(QPalette.Disabled, QPalette.WindowText, QColor(t.muted))
    return p


def stylesheet(t: Theme) -> str:
    family = display_family()
    return f"""
QWidget {{
    color: {t.text};
    font-size: 14px;
}}
QMainWindow, #root {{ background: {t.bg}; }}
QToolTip {{
    background: {t.surface}; color: {t.text};
    border: 1px solid {t.border}; padding: 4px 6px;
}}

#wordmark {{ color: {t.text}; font-family: "{family}"; font-size: 44px; }}
#pageTitle {{ color: {t.text}; font-family: "{family}"; font-size: 30px; }}
#statValue {{ color: {t.text}; font-size: 26px; font-weight: 600; }}
#detailName {{ font-weight: 600; }}
QLabel[tone="danger"] {{ color: {t.danger}; font-size: 13px; font-weight: 600; }}
QLabel[tone="warn"] {{ color: {t.warn}; font-size: 13px; font-weight: 600; }}
#progressFile {{ font-size: 15px; font-weight: 600; }}
#statValue[tone="ok"] {{ color: {t.ok}; }}
#statValue[tone="warn"] {{ color: {t.warn}; }}
#statValue[tone="danger"] {{ color: {t.danger}; }}
#tagline, QLabel[role="muted"] {{ color: {t.muted}; }}
QLabel[role="muted"] {{ font-size: 13px; }}
QLabel[role="section"] {{ font-weight: 600; }}
QLabel[role="ok"] {{ color: {t.ok}; font-size: 13px; }}
QLabel[role="danger"] {{ color: {t.danger}; font-size: 13px; }}
QLabel[role="warn"] {{ color: {t.warn}; font-size: 13px; }}

/* Mode switch */
#modeSwitch {{
    background: {t.surface};
    border: 1px solid {t.field_border};
    border-radius: 10px;
}}
#modeSwitch QPushButton {{
    background: transparent;
    border: none;
    border-radius: 7px;
    padding: 8px 18px;
    font-size: 14px;
    font-weight: 600;
    color: {t.muted};
}}
#modeSwitch QPushButton:hover {{ color: {t.text}; }}
#modeSwitch QPushButton:checked {{
    background: {t.accent_soft};
    color: {t.text};
    border: 1px solid {t.accent};
}}
#modeSwitch QPushButton:focus {{ outline: none; border: 2px solid {t.accent}; }}

/* Drop zone */
#dropZone {{
    background: {t.surface};
    border: 1.5px dashed {t.field_border};
    border-radius: 12px;
}}
#dropZone[dragActive="true"] {{
    background: {t.surface_alt};
    border: 1.5px solid {t.accent};
}}
#dropTitle {{ font-size: 15px; font-weight: 600; }}

QListWidget#itemList {{
    background: transparent;
    border: none;
    outline: none;
}}
QListWidget#itemList::item {{ border-radius: 6px; }}
QListWidget#itemList::item:selected,
QListWidget#itemList::item:hover {{ background: {t.surface_alt}; }}

/* Inputs */
QLineEdit {{
    background: {t.surface};
    border: 1px solid {t.field_border};
    border-radius: 8px;
    padding: 9px 40px 9px 12px;
    selection-background-color: {t.accent};
    selection-color: {t.on_accent};
    font-size: 15px;
}}
QLineEdit:focus {{ border: 2px solid {t.accent}; padding: 8px 39px 8px 11px; }}
QLineEdit[state="error"] {{ border: 2px solid {t.danger}; padding: 8px 39px 8px 11px; }}

/* Buttons */
QPushButton {{
    background: {t.surface};
    border: 1px solid {t.border};
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 500;
}}
QPushButton:hover {{ background: {t.surface_alt}; }}
QPushButton:focus {{ outline: none; border: 2px solid {t.accent}; padding: 6px 13px; }}
QPushButton:disabled {{ color: {t.muted}; }}
QPushButton#primary {{
    background: {t.accent};
    color: {t.on_accent};
    border: 1px solid {t.accent};
    font-size: 15px;
    font-weight: 600;
    padding: 11px 20px;
}}
QPushButton#primary:hover {{ background: {QColor(t.accent).lighter(108 if t.dark else 118).name()}; }}
QPushButton#primary:focus {{ border: 2px solid {t.text}; padding: 10px 19px; }}
QPushButton#primary:disabled {{
    background: {t.surface_alt};
    border: 1px solid {t.border};
    color: {t.muted};
}}
QToolButton {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 4px;
}}
QToolButton:hover {{ background: {t.surface_alt}; }}
QToolButton:focus {{ outline: none; border: 2px solid {t.accent}; padding: 2px; }}

/* Results */
QListWidget#details {{
    background: {t.surface};
    border: 1px solid {t.border};
    border-radius: 10px;
    padding: 4px;
    outline: none;
}}
QListWidget#details::item {{ border-bottom: 1px solid {t.surface_alt}; }}
QListWidget#details::item:selected {{ background: {t.surface_alt}; }}
QListWidget#details:focus {{ border: 2px solid {t.accent}; }}
#statCard {{
    background: {t.surface};
    border: 1px solid {t.border};
    border-radius: 10px;
}}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {t.border}; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
"""
