import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")

from trip_stream import config, i18n  # noqa: E402
from trip_stream.controller import Controller  # noqa: E402


def test_runtime_language_switch(tmp_path):
    from PySide6.QtWidgets import QApplication
    from trip_stream.gui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    cfg = config.load(tmp_path / "c.json")
    cfg["gui"]["language"] = "it"
    cfg["audio"]["primary_device"] = "__tone__"
    cfg["advanced"]["remote_enabled"] = False
    i18n.set_language("it")
    controller = Controller(cfg, tmp_path / "c.json")
    controller.start()
    try:
        window = MainWindow(controller)
        assert "Impostazioni" in window.btn_settings.text()
        window.open_settings()
        settings = window.settings
        settings.language.setCurrentIndex(settings.language.findData("en"))
        app.processEvents()
        assert "Settings" in window.btn_settings.text()
        assert config.load(tmp_path / "c.json")["gui"]["language"] == "en"
        assert settings.tabs.tabText(3) == "Record"
        settings.save()
        window._really_quit = True
        window.close()
    finally:
        controller.shutdown()
        i18n.set_language("en")
