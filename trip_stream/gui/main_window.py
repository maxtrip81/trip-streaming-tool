"""Main window: LCD, VU meter, transport buttons, song field and mixer."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QApplication, QCheckBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QMainWindow, QMessageBox, QPushButton, QSlider, QToolButton, QVBoxLayout, QWidget)

from trip_stream import APP_NAME, __version__
from trip_stream.encoders import CODECS
from trip_stream.gui.settings import SettingsDialog
from trip_stream.gui.widgets import LcdDisplay, VuMeter, app_icon
from trip_stream.i18n import set_language, tr
from trip_stream.stream import CONNECTED, CONNECTING, FAILED, RECONNECTING


def fmt_time(secs: int) -> str:
    h, rem = divmod(int(secs), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


class MainWindow(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.settings: SettingsDialog | None = None
        self.setWindowIcon(app_icon())
        self._build()
        self._apply_window_flags()
        if controller.cfg["gui"]["geometry"]:
            try:
                self.restoreGeometry(bytes.fromhex(controller.cfg["gui"]["geometry"]))
            except ValueError:
                pass
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(50)

    # ----------------------------------------------------------------- build
    def _build(self):
        cfg = self.controller.cfg
        self.setWindowTitle(APP_NAME)
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        header = QHBoxLayout()
        brand = QLabel("TRIP")
        brand.setObjectName("brand")
        sub = QLabel(f"streaming tool  ·  {tr('app.tagline')}")
        sub.setObjectName("hint")
        header.addWidget(brand)
        header.addWidget(sub)
        header.addStretch()
        root.addLayout(header)

        self.lcd = LcdDisplay()
        self.lcd.set_color(cfg["gui"]["lcd_color"])
        root.addWidget(self.lcd)
        self.vu = VuMeter()
        self.vu.setToolTip(tr("main.vu_tooltip"))
        root.addWidget(self.vu)

        buttons = QHBoxLayout()
        self.btn_connect = self._transport("▶", tr("btn.connect"), self._connect)
        self.btn_stop = self._transport("■", tr("btn.disconnect"), self.controller.disconnect)
        self.btn_record = self._transport("●", tr("btn.record"), self.controller.toggle_record, checkable=True)
        self.btn_record.setObjectName("record")
        self.btn_connect.setCheckable(True)
        for b in (self.btn_connect, self.btn_stop, self.btn_record):
            buttons.addWidget(b)
        buttons.addStretch()
        self.btn_mixer = QPushButton(tr("btn.mixer"))
        self.btn_mixer.setCheckable(True)
        self.btn_mixer.toggled.connect(lambda on: self.mixer.setVisible(on))
        self.btn_settings = QPushButton("⚙ " + tr("btn.settings"))
        self.btn_settings.clicked.connect(self.open_settings)
        buttons.addWidget(self.btn_mixer)
        buttons.addWidget(self.btn_settings)
        root.addLayout(buttons)

        song_row = QHBoxLayout()
        song_label = QLabel(tr("main.song") + ":")
        self.song_edit = QLineEdit(cfg["stream"]["song"])
        self.song_edit.setPlaceholderText(tr("main.song_placeholder"))
        self.song_edit.returnPressed.connect(self._update_song)
        song_btn = QPushButton(tr("btn.update_song"))
        song_btn.clicked.connect(self._update_song)
        song_row.addWidget(song_label)
        song_row.addWidget(self.song_edit, 1)
        song_row.addWidget(song_btn)
        root.addLayout(song_row)

        self.mixer = self._build_mixer()
        self.mixer.setVisible(self.btn_mixer.isChecked())
        root.addWidget(self.mixer)
        self.setCentralWidget(central)
        self.statusBar().showMessage(f"{APP_NAME} {__version__} – Max Trip")

    def _transport(self, symbol, tooltip, slot, checkable=False) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName("transport")
        btn.setText(symbol)
        btn.setToolTip(tooltip)
        btn.setCheckable(checkable)
        btn.clicked.connect(lambda *_: slot())
        return btn

    def _build_mixer(self) -> QGroupBox:
        mixer = self.controller.cfg["mixer"]
        group = QGroupBox(tr("btn.mixer"))
        grid = QGridLayout(group)
        self.mix_controls = {}
        rows = [("primary", "main.primary"), ("secondary", "main.secondary"), ("master", "main.master")]
        for row, (key, label) in enumerate(rows):
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(-600, 120)  # tenths of dB
            slider.setValue(int(mixer[f"{key}_gain_db"] * 10))
            value = QLabel(f"{mixer[f'{key}_gain_db']:+.1f} dB")
            value.setMinimumWidth(64)
            grid.addWidget(QLabel(tr(label)), row, 0)
            grid.addWidget(slider, row, 1)
            grid.addWidget(value, row, 2)
            mute = None
            if key != "master":
                mute = QCheckBox(tr("btn.mute"))
                mute.setChecked(bool(mixer[f"{key}_mute"]))
                mute.toggled.connect(lambda on, k=key: self._mixer_changed(k, mute=on))
                grid.addWidget(mute, row, 3)
            slider.valueChanged.connect(lambda v, k=key, lab=value: (lab.setText(f"{v / 10:+.1f} dB"),
                                                                       self._mixer_changed(k, gain=v / 10)))
            slider.mouseDoubleClickEvent = lambda e, s=slider: s.setValue(0)
            self.mix_controls[key] = (slider, value, mute)
        return group

    def _mixer_changed(self, key, gain=None, mute=None):
        mixer = self.controller.cfg["mixer"]
        if gain is not None:
            mixer[f"{key}_gain_db"] = gain
        if mute is not None:
            mixer[f"{key}_mute"] = mute
        self.controller.apply_mixer()

    def _apply_window_flags(self):
        on_top = bool(self.controller.cfg["gui"]["always_on_top"])
        if bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint) != on_top:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on_top)
            self.show()

    def retranslate(self, lang: str):
        set_language(lang)
        mixer_visible = self.btn_mixer.isChecked()
        self._build()
        self.btn_mixer.setChecked(mixer_visible)

    # --------------------------------------------------------------- actions
    def _connect(self):
        if not self.controller.connect():
            self.btn_connect.setChecked(False)
            self.statusBar().showMessage(self.controller.logs[-1] if self.controller.logs else "", 8000)

    def _update_song(self):
        self.controller.update_song(self.song_edit.text().strip())

    def open_settings(self):
        if self.settings is None:
            self.settings = SettingsDialog(self.controller, self)
            self.settings.language_changed.connect(self.retranslate)
            self.settings.applied.connect(self._settings_applied)
            self.settings.finished.connect(lambda *_: setattr(self, "settings", None))
            self.settings.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.settings.show()
        self.settings.raise_()
        self.settings.activateWindow()

    def _settings_applied(self):
        self.lcd.set_color(self.controller.cfg["gui"]["lcd_color"])
        self._apply_window_flags()

    # --------------------------------------------------------------- refresh
    def _refresh(self):
        c = self.controller
        if c.quit_requested:
            c.quit_requested = False
            self._really_quit = True
            self.close()
            return
        st = c.status()
        self.vu.set_levels(st["peak_db"])
        sessions = st["sessions"]
        states = [s["state"] for s in sessions]
        if CONNECTED in states:
            state = tr("lcd.connected")
        elif CONNECTING in states:
            state = tr("lcd.connecting")
        elif RECONNECTING in states:
            state = tr("lcd.reconnecting")
        elif FAILED in states:
            state = tr("lcd.error")
        else:
            state = tr("lcd.idle")
        uptime = max([s["uptime"] for s in sessions] or [0])
        line1 = f"{state.upper():<16} {fmt_time(uptime)}" if st["streaming"] else f"{state.upper()}"
        codec = CODECS[st["codec"]]["label"]
        sent = sum(s["bytes_sent"] for s in sessions)
        kbps = sum(s["kbps"] for s in sessions)
        n_conn = sum(1 for s in sessions if s["state"] == CONNECTED)
        if st["streaming"]:
            line2 = (f"{codec} {st['bitrate']}k · {st['samplerate']} Hz · {tr('lcd.sent')} {fmt_bytes(sent)} · "
                     f"{kbps:.0f} kbit/s · {n_conn}/{len(sessions)}")
        else:
            servers = [s for s in c.cfg["servers"] if s.get("enabled", True)]
            target = tr("lcd.servers", n=len(servers)) if servers else tr("lcd.no_server")
            line2 = f"{codec} {st['bitrate']}k · {st['samplerate']} Hz · {st['channels']} ch · {target}"
        if st["audio_error"]:
            line2 = tr("msg.audio_error", err=st["audio_error"])
        if st["recording"]:
            rec_codec = CODECS[c.cfg["record"]["codec"]]["label"]
            line3 = f"● {tr('lcd.recording').upper()} {fmt_time(st['record_seconds'])} · {rec_codec} · " \
                    f"{fmt_bytes(st['record_bytes'])}"
        else:
            line3 = ""
        line4 = f"♪ {st['song']}" if st["song"] else ""
        self.lcd.set_lines([line1, line2, line3, line4])
        self.btn_connect.setChecked(st["streaming"])
        self.btn_record.setChecked(st["recording"])
        self.setWindowTitle(f"{APP_NAME} – {state}" if st["streaming"] else APP_NAME)

    # ------------------------------------------------------------------ quit
    def closeEvent(self, event):
        c = self.controller
        if (c.is_streaming or c.recorder.active) and not getattr(self, "_really_quit", False):
            answer = QMessageBox.question(self, APP_NAME, tr("msg.quit_confirm"))
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        c.cfg["gui"]["geometry"] = bytes(self.saveGeometry()).hex()
        c.cfg["stream"]["song"] = self.song_edit.text().strip()
        c.save_config()
        if self.settings is not None:
            self.settings.close()
        event.accept()
        QApplication.instance().quit()
