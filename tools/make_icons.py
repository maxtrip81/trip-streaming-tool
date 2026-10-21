"""Render the application icon to assets/ (PNG, Windows .ico, macOS .icns). Requires PySide6 and Pillow."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from trip_stream.gui.widgets import icon_pixmap  # noqa: E402

app = QGuiApplication([])
assets = ROOT / "assets"
assets.mkdir(exist_ok=True)
icon_pixmap(1024).save(str(assets / "icon.png"))
img = Image.open(assets / "icon.png")
img.save(assets / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
img.save(assets / "icon.icns")
print("icons written to", assets)
