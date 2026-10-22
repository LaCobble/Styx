# Projet : Styx
# Author:
#      __          ___      _     _     _
#     / /  __ _   / __\___ | |__ | |__ | | ___
#    / /  / _` | / /  / _ \| '_ \| '_ \| |/ _ \
#   / /__| (_| |/ /__| (_) | |_) | |_) | |  __/
#   \____/\__,_|\____/\___/|_.__/|_.__/|_|\___|
#
#
"""Entry point of the Styx desktop app (also the PyInstaller entry point)."""

import os
import sys

from styx.gui import run


def resource_path(relative_path):
    """Get the absolute path to a bundled resource, in development and under PyInstaller."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


if __name__ == "__main__":
    sys.exit(run(icon_path=resource_path("Styx_icon.png")))
