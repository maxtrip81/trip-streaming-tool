"""Settings window (tabs: Main, Audio, Stream, Record, DSP, Advanced, Interface, Log)."""

from __future__ import annotations

import copy
import json

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QFrame, QColorDialog, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSlider, QSpinBox, QTabWidget, QVBoxLayout,
                               QWidget)

from trip_stream import config as config_mod
from trip_stream.audio import devices
from trip_stream.audio.dsp import EQ_BANDS, EQ_PRESETS
from trip_stream.encoders import AAC_PROFILES, BITRATES, CODECS, RECORD_CODECS, SAMPLERATES, STREAM_CODECS, find_ffmpeg
from trip_stream.gui.dialogs import IcyDialog, ServerDialog, show_about
from trip_stream.i18n import LANGUAGES, tr


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("hint")
    label.setWordWrap(True)
    return label


def _spin(lo, hi, value, step=1, decimals=None) -> QSpinBox | QDoubleSpinBox:
    spin = QDoubleSpinBox() if decimals is not None else QSpinBox()
    if decimals is not None:
        spin.setDecimals(decimals)
    spin.setRange(lo, hi)
    spin.setSingleStep(step)
    spin.setValue(value)
    return spin


def _check(text: str, value: bool) -> QCheckBox:
    box = QCheckBox(text)
    box.setChecked(bool(value))
    return box


def _combo(items, current) -> QComboBox:
    combo = QComboBox()
    for data, label in items:
        combo.addItem(label, data)
    idx = combo.findData(current)
    combo.setCurrentIndex(max(0, idx))
    return combo


def _scroll(page: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(page)
    return area


def _row(*widgets) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    for w in widgets:
        if w == "stretch":
            layout.addStretch()
        else:
            layout.addWidget(w)
    return row


class SettingsDialog(QDialog):
    language_changed = Signal(str)
    applied = Signal()

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.work = copy.deepcopy(controller.cfg)
        self._log_serial = -1
        self.setMinimumSize(640, 600)
        self.root = QVBoxLayout(self)
        self.tabs = None
        self._build()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_log)
        self._timer.start(500)

    # ----------------------------------------------------------------- build
    def _build(self, tab_index: int = 0):
        while self.root.count():
            item = self.root.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.setWindowTitle(f"TRIP streaming tool – {tr('settings.title')}")
        self.tabs = QTabWidget()
        self.tabs.addTab(_scroll(self._tab_main()), tr("tab.main"))
        self.tabs.addTab(_scroll(self._tab_audio()), tr("tab.audio"))
        self.tabs.addTab(_scroll(self._tab_stream()), tr("tab.stream"))
        self.tabs.addTab(_scroll(self._tab_record()), tr("tab.record"))
        self.tabs.addTab(_scroll(self._tab_dsp()), tr("tab.dsp"))
        self.tabs.addTab(_scroll(self._tab_advanced()), tr("tab.advanced"))
        self.tabs.addTab(_scroll(self._tab_gui()), tr("tab.gui"))
        self.tabs.addTab(self._tab_log(), tr("tab.log"))
        self.tabs.setCurrentIndex(tab_index)
        self.root.addWidget(self.tabs)
        buttons = QHBoxLayout()
        about = QPushButton(tr("btn.about"))
        about.clicked.connect(lambda: show_about(self))
        buttons.addWidget(about)
        buttons.addStretch()
        save = QPushButton(tr("btn.save"))
        save.setDefault(True)
        save.clicked.connect(self.save)
        close = QPushButton(tr("btn.close"))
        close.clicked.connect(self.close)
        buttons.addWidget(save)
        buttons.addWidget(close)
        self.root.addLayout(buttons)
        self._log_serial = -1
        self._refresh_log()

    # ------------------------------------------------------------- main tab
    def _tab_main(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        group = QGroupBox(tr("main.servers"))
        g = QVBoxLayout(group)
        self.server_list = QListWidget()
        self._fill_servers()
        self.server_list.itemDoubleClicked.connect(lambda _: self._edit_server())
        g.addWidget(self.server_list)
        add, edit, delete = QPushButton(tr("btn.add")), QPushButton(tr("btn.edit")), QPushButton(tr("btn.delete"))
        add.clicked.connect(self._add_server)
        edit.clicked.connect(self._edit_server)
        delete.clicked.connect(self._delete_server)
        g.addWidget(_row(add, edit, delete, "stretch"))
        g.addWidget(_hint(tr("main.servers_hint")))
        layout.addWidget(group)

        icy = QGroupBox(tr("main.icy"))
        i = QVBoxLayout(icy)
        self.icy_summary = QLabel()
        self._update_icy_summary()
        icy_btn = QPushButton(tr("main.icy_edit"))
        icy_btn.clicked.connect(self._edit_icy)
        i.addWidget(self.icy_summary)
        i.addWidget(_row(icy_btn, "stretch"))
        layout.addWidget(icy)

        cfg_group = QGroupBox(tr("main.config"))
        c = QVBoxLayout(cfg_group)
        self.connect_startup = _check(tr("main.connect_startup"), self.work["stream"]["connect_at_startup"])
        imp, exp = QPushButton(tr("btn.import")), QPushButton(tr("btn.export"))
        imp.clicked.connect(self._import_config)
        exp.clicked.connect(self._export_config)
        c.addWidget(self.connect_startup)
        c.addWidget(_row(imp, exp, "stretch"))
        layout.addWidget(cfg_group)
        layout.addStretch()
        return page

    def _fill_servers(self):
        self.server_list.clear()
        types = {"icecast": "Icecast", "shoutcast": "SHOUTcast", "whip": "WebRTC/WHIP"}
        for server in self.work["servers"]:
            target = server["whip_url"] if server["type"] == "whip" else \
                f"{server['host']}:{server['port']}{server['mount'] if server['type'] == 'icecast' else ''}"
            item = QListWidgetItem(f"{server['name']}  —  {types[server['type']]}  {target}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if server.get("enabled", True) else Qt.CheckState.Unchecked)
            self.server_list.addItem(item)

    def _collect_server_checks(self):
        for row in range(self.server_list.count()):
            self.work["servers"][row]["enabled"] = \
                self.server_list.item(row).checkState() == Qt.CheckState.Checked

    def _add_server(self):
        self._collect_server_checks()
        dlg = ServerDialog(None, self)
        if dlg.exec():
            self.work["servers"].append(dlg.server)
            self._fill_servers()

    def _edit_server(self):
        row = self.server_list.currentRow()
        if row < 0:
            return
        self._collect_server_checks()
        dlg = ServerDialog(self.work["servers"][row], self)
        if dlg.exec():
            self.work["servers"][row] = dlg.server
            self._fill_servers()
            self.server_list.setCurrentRow(row)

    def _delete_server(self):
        row = self.server_list.currentRow()
        if row < 0:
            return
        name = self.work["servers"][row]["name"]
        if QMessageBox.question(self, tr("server.title"), tr("server.delete_confirm", name=name)) == \
                QMessageBox.StandardButton.Yes:
            self._collect_server_checks()
            del self.work["servers"][row]
            self._fill_servers()

    def _update_icy_summary(self):
        icy = self.work["icy"]
        self.icy_summary.setText(f"<b>{icy['name']}</b> · {icy['genre']}<br><span style='color:#8a9a96'>"
                                 f"{icy['description']}</span>")

    def _edit_icy(self):
        dlg = IcyDialog(self.work["icy"], self)
        if dlg.exec():
            self.work["icy"] = dlg.icy
            self._update_icy_summary()

    def _import_config(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("btn.import"), "", "TRIP config (*.json);;*")
        if not path:
            return
        self.work = config_mod.load(path)
        self.work["gui"]["language"] = self.controller.cfg["gui"]["language"]
        self.controller.log(("msg.config_imported", {"file": path}))
        self._build(self.tabs.currentIndex())

    def _export_config(self):
        self._collect()
        path, _ = QFileDialog.getSaveFileName(self, tr("btn.export"), "trip_stream.json", "TRIP config (*.json)")
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self.work, fh, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------ audio tab
    def _device_items(self, secondary: bool):
        items = [("", tr("audio.none") if secondary else tr("audio.default")),
                 (devices.TONE_DEVICE, tr("audio.tone"))]
        items += [(d["label"], d["label"]) for d in devices.list_input_devices()]
        return items

    def _tab_audio(self) -> QWidget:
        a = self.work["audio"]
        page = QWidget()
        layout = QVBoxLayout(page)

        self.dev = {}
        for which, title in (("primary", "audio.primary"), ("secondary", "audio.secondary")):
            group = QGroupBox(tr(title))
            form = QFormLayout(group)
            combo = QComboBox()
            items = self._device_items(which == "secondary")
            for data, label in items:
                combo.addItem(label, data)
            current = a[f"{which}_device"]
            if combo.findData(current) < 0:
                combo.addItem(f"{current} (?)", current)
            combo.setCurrentIndex(combo.findData(current))
            left, right = QComboBox(), QComboBox()
            form.addRow(tr("audio.device"), combo)
            form.addRow(tr("audio.left"), left)
            form.addRow(tr("audio.right"), right)
            self.dev[which] = (combo, left, right)
            combo.currentIndexChanged.connect(lambda _=0, w=which: self._fill_channels(w))
            self._fill_channels(which, a[f"{which}_left"], a[f"{which}_right"])
            layout.addWidget(group)
        refresh = QPushButton(tr("btn.refresh"))
        refresh.clicked.connect(self._refresh_devices)
        layout.addWidget(_row(refresh, "stretch"))

        fmt = QGroupBox(tr("audio.format"))
        form = QFormLayout(fmt)
        self.samplerate = _combo([(sr, f"{sr} Hz") for sr in SAMPLERATES], int(a["samplerate"]))
        self.channels = _combo([(1, tr("audio.mono")), (2, tr("audio.stereo"))], int(a["channels"]))
        self.buffer_ms = _spin(10, 500, int(a["buffer_ms"]), 10)
        form.addRow(tr("audio.samplerate"), self.samplerate)
        form.addRow(tr("audio.channels"), self.channels)
        form.addRow(tr("audio.buffer"), self.buffer_ms)
        layout.addWidget(fmt)
        layout.addWidget(_hint(tr("audio.routing_hint")))
        layout.addStretch()
        return page

    def _fill_channels(self, which, left=None, right=None):
        combo, lcombo, rcombo = self.dev[which]
        if left is None:
            left, right = lcombo.currentIndex(), rcombo.currentIndex()
        n = devices.device_channels(combo.currentData()) if combo.currentData() != "" or which == "primary" else 2
        for box, value in ((lcombo, left), (rcombo, right)):
            box.blockSignals(True)
            box.clear()
            for ch in range(n):
                box.addItem(tr("audio.channel_n", n=ch + 1), ch)
            box.setCurrentIndex(min(max(0, int(value)), n - 1))
            box.blockSignals(False)
        if n == 1:
            rcombo.setCurrentIndex(0)

    def _refresh_devices(self):
        self._collect()
        self._build(self.tabs.currentIndex())

    # ----------------------------------------------------------- stream tab
    def _tab_stream(self) -> QWidget:
        s = self.work["stream"]
        page = QWidget()
        layout = QVBoxLayout(page)
        codec = QGroupBox(tr("stream.codec"))
        form = QFormLayout(codec)
        self.st_codec = _combo([(c, CODECS[c]["label"]) for c in STREAM_CODECS], s["codec"])
        self.st_bitrate = _combo([(b, f"{b} kbit/s") for b in BITRATES], int(s["bitrate"]))
        self.st_aac = _combo(list(AAC_PROFILES.items()), s["aac_profile"])
        form.addRow(tr("stream.codec"), self.st_codec)
        form.addRow(tr("stream.bitrate"), self.st_bitrate)
        form.addRow(tr("stream.aac_profile"), self.st_aac)
        self.st_codec.currentIndexChanged.connect(
            lambda: self.st_aac.setEnabled(self.st_codec.currentData() == "aac"))
        self.st_aac.setEnabled(s["codec"] == "aac")
        layout.addWidget(codec)

        song = QGroupBox(tr("stream.song"))
        form = QFormLayout(song)
        self.song_file = QLineEdit(s["song_file"])
        browse = QPushButton(tr("btn.browse"))
        browse.clicked.connect(self._browse_song_file)
        self.song_line = _combo([("first", tr("stream.first_line")), ("last", tr("stream.last_line"))],
                                s["song_file_line"])
        self.song_app = _check(tr("stream.song_app"), s["song_from_app"])
        self.song_app.setToolTip(tr("stream.song_app_hint"))
        self.song_prefix = QLineEdit(s["song_prefix"])
        self.song_suffix = QLineEdit(s["song_suffix"])
        self.song_delay = _spin(0, 600, int(s["song_delay"]))
        form.addRow(tr("stream.song_file"), _row(self.song_file, browse))
        form.addRow(tr("stream.song_line"), self.song_line)
        form.addRow("", self.song_app)
        form.addRow("", _hint(tr("stream.song_app_hint")))
        form.addRow(tr("stream.prefix"), self.song_prefix)
        form.addRow(tr("stream.suffix"), self.song_suffix)
        form.addRow(tr("stream.delay"), self.song_delay)
        layout.addWidget(song)

        conn = QGroupBox(tr("stream.connection"))
        form = QFormLayout(conn)
        self.reconnect = _check(tr("stream.reconnect"), s["reconnect"])
        self.reconnect_delay = _spin(1, 3600, int(s["reconnect_delay"]))
        self.reconnect_max = _spin(0, 100000, int(s["reconnect_max"]))
        form.addRow("", self.reconnect)
        form.addRow(tr("stream.reconnect_delay"), self.reconnect_delay)
        form.addRow(tr("stream.reconnect_max"), self.reconnect_max)
        layout.addWidget(conn)

        det = QGroupBox(tr("stream.signal"))
        form = QFormLayout(det)
        self.threshold = _spin(-90, 0, float(self.work["detection"]["threshold_db"]), 1, 1)
        self.st_start_sig = _check(tr("stream.start_signal"), s["start_on_signal"])
        self.st_start_secs = _spin(1, 3600, int(s["start_signal_secs"]))
        self.st_stop_sil = _check(tr("stream.stop_silence"), s["stop_on_silence"])
        self.st_stop_secs = _spin(1, 36000, int(s["stop_silence_secs"]))
        form.addRow(tr("detect.threshold"), self.threshold)
        form.addRow(self.st_start_sig, self.st_start_secs)
        form.addRow(self.st_stop_sil, self.st_stop_secs)
        layout.addWidget(det)
        layout.addStretch()
        return page

    def _browse_song_file(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("stream.song_file"), "", "Text (*.txt);;*")
        if path:
            self.song_file.setText(path)

    # ----------------------------------------------------------- record tab
    def _tab_record(self) -> QWidget:
        r = self.work["record"]
        page = QWidget()
        layout = QVBoxLayout(page)
        group = QGroupBox(tr("record.codec"))
        form = QFormLayout(group)
        self.rec_codec = _combo([(c, CODECS[c]["label"].replace("Ogg/FLAC", "FLAC")) for c in RECORD_CODECS],
                                r["codec"])
        self.rec_bitrate = _combo([(b, f"{b} kbit/s") for b in BITRATES], int(r["bitrate"]))
        self.rec_codec.currentIndexChanged.connect(
            lambda: self.rec_bitrate.setEnabled(self.rec_codec.currentData() not in ("wav", "flac")))
        self.rec_bitrate.setEnabled(r["codec"] not in ("wav", "flac"))
        self.rec_folder = QLineEdit(r["folder"])
        self.rec_folder.setPlaceholderText(str(config_mod.default_record_folder()))
        browse = QPushButton(tr("btn.browse"))
        browse.clicked.connect(self._browse_folder)
        self.rec_filename = QLineEdit(r["filename"])
        form.addRow(tr("record.codec"), self.rec_codec)
        form.addRow(tr("stream.bitrate"), self.rec_bitrate)
        form.addRow(tr("record.folder"), _row(self.rec_folder, browse))
        form.addRow(tr("record.filename"), self.rec_filename)
        form.addRow("", _hint(tr("record.filename_hint")))
        layout.addWidget(group)

        auto = QGroupBox(tr("tab.record"))
        form = QFormLayout(auto)
        self.rec_split = _spin(0, 24 * 60, int(r["split_minutes"]))
        self.rec_sync = _check(tr("record.split_sync"), r["split_sync"])
        self.rec_start_conn = _check(tr("record.start_connect"), r["start_on_connect"])
        self.rec_stop_disc = _check(tr("record.stop_disconnect"), r["stop_on_disconnect"])
        self.rec_start_sig = _check(tr("record.start_signal"), r["start_on_signal"])
        self.rec_start_secs = _spin(1, 3600, int(r["start_signal_secs"]))
        self.rec_stop_sil = _check(tr("record.stop_silence"), r["stop_on_silence"])
        self.rec_stop_secs = _spin(1, 36000, int(r["stop_silence_secs"]))
        split_now = QPushButton(tr("btn.split"))
        split_now.clicked.connect(self.controller.split_record)
        form.addRow(tr("record.split"), self.rec_split)
        form.addRow("", self.rec_sync)
        form.addRow("", self.rec_start_conn)
        form.addRow("", self.rec_stop_disc)
        form.addRow(self.rec_start_sig, self.rec_start_secs)
        form.addRow(self.rec_stop_sil, self.rec_stop_secs)
        form.addRow("", _row(split_now, "stretch"))
        layout.addWidget(auto)
        layout.addStretch()
        return page

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, tr("record.choose_folder"),
                                                self.rec_folder.text() or str(config_mod.default_record_folder()))
        if path:
            self.rec_folder.setText(path)

    # -------------------------------------------------------------- DSP tab
    def _tab_dsp(self) -> QWidget:
        d = self.work["dsp"]
        page = QWidget()
        layout = QVBoxLayout(page)
        eq = QGroupBox(tr("dsp.eq"))
        e = QVBoxLayout(eq)
        self.eq_enabled = _check(tr("dsp.eq_enable"), d["eq_enabled"])
        presets = [(k, tr(f"preset.{k}")) for k in EQ_PRESETS] + [("custom", tr("preset.custom"))]
        self.eq_preset = _combo(presets, d["eq_preset"])
        e.addWidget(_row(self.eq_enabled, "stretch", QLabel(tr("dsp.preset")), self.eq_preset))
        grid = QGridLayout()
        self.eq_sliders, self.eq_values = [], []
        for i, freq in enumerate(EQ_BANDS):
            slider = QSlider(Qt.Orientation.Vertical)
            slider.setRange(-120, 120)
            slider.setValue(int(round(d["eq_gains"][i] * 10)))
            slider.setMinimumHeight(130)
            value = QLabel(f"{d['eq_gains'][i]:+.1f}")
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label = QLabel(f"{freq // 1000}k" if freq >= 1000 else str(freq))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(value, 0, i)
            grid.addWidget(slider, 1, i, Qt.AlignmentFlag.AlignHCenter)
            grid.addWidget(label, 2, i)
            slider.valueChanged.connect(lambda v, lab=value: (lab.setText(f"{v / 10:+.1f}"), self._eq_custom()))
            self.eq_sliders.append(slider)
            self.eq_values.append(value)
        e.addLayout(grid)
        self.eq_preset.currentIndexChanged.connect(self._apply_preset)
        layout.addWidget(eq)

        comp = QGroupBox(tr("dsp.comp"))
        form = QFormLayout(comp)
        self.comp_enabled = _check(tr("dsp.comp_enable"), d["comp_enabled"])
        self.comp_threshold = _spin(-60, 0, float(d["comp_threshold_db"]), 1, 1)
        self.comp_ratio = _spin(1, 20, float(d["comp_ratio"]), 0.5, 1)
        self.comp_attack = _spin(0.1, 500, float(d["comp_attack_ms"]), 1, 1)
        self.comp_release = _spin(1, 5000, float(d["comp_release_ms"]), 10, 0)
        self.comp_makeup = _spin(-12, 24, float(d["comp_makeup_db"]), 0.5, 1)
        form.addRow("", self.comp_enabled)
        form.addRow(tr("dsp.threshold"), self.comp_threshold)
        form.addRow(tr("dsp.ratio"), self.comp_ratio)
        form.addRow(tr("dsp.attack"), self.comp_attack)
        form.addRow(tr("dsp.release"), self.comp_release)
        form.addRow(tr("dsp.makeup"), self.comp_makeup)
        layout.addWidget(comp)
        self.dsp_stream = _check(tr("dsp.apply_stream"), d["apply_stream"])
        self.dsp_record = _check(tr("dsp.apply_record"), d["apply_record"])
        layout.addWidget(_row(self.dsp_stream, self.dsp_record, "stretch"))
        layout.addStretch()
        # live preview of DSP changes
        for widget in [self.eq_enabled, self.comp_enabled, self.dsp_stream, self.dsp_record]:
            widget.toggled.connect(self._live_dsp)
        for widget in [self.comp_threshold, self.comp_ratio, self.comp_attack, self.comp_release, self.comp_makeup]:
            widget.valueChanged.connect(self._live_dsp)
        for slider in self.eq_sliders:
            slider.valueChanged.connect(self._live_dsp)
        return page

    def _apply_preset(self):
        key = self.eq_preset.currentData()
        if key in EQ_PRESETS:
            for slider, gain in zip(self.eq_sliders, EQ_PRESETS[key]):
                slider.blockSignals(True)
                slider.setValue(int(gain * 10))
                slider.blockSignals(False)
            for label, gain in zip(self.eq_values, EQ_PRESETS[key]):
                label.setText(f"{gain:+.1f}")
            self._live_dsp()

    def _eq_custom(self):
        gains = [s.value() / 10 for s in self.eq_sliders]
        match = next((k for k, v in EQ_PRESETS.items() if [float(x) for x in v] == gains), "custom")
        self.eq_preset.blockSignals(True)
        self.eq_preset.setCurrentIndex(self.eq_preset.findData(match))
        self.eq_preset.blockSignals(False)

    def _collect_dsp(self) -> dict:
        return {
            "eq_enabled": self.eq_enabled.isChecked(), "eq_preset": self.eq_preset.currentData(),
            "eq_gains": [s.value() / 10 for s in self.eq_sliders],
            "comp_enabled": self.comp_enabled.isChecked(), "comp_threshold_db": self.comp_threshold.value(),
            "comp_ratio": self.comp_ratio.value(), "comp_attack_ms": self.comp_attack.value(),
            "comp_release_ms": self.comp_release.value(), "comp_makeup_db": self.comp_makeup.value(),
            "apply_stream": self.dsp_stream.isChecked(), "apply_record": self.dsp_record.isChecked(),
        }

    def _live_dsp(self, *_):
        self.controller.engine.apply_dsp(self._collect_dsp())

    # --------------------------------------------------------- advanced tab
    def _tab_advanced(self) -> QWidget:
        adv = self.work["advanced"]
        page = QWidget()
        layout = QVBoxLayout(page)
        group = QGroupBox("FFmpeg")
        form = QFormLayout(group)
        self.ffmpeg_path = QLineEdit(adv["ffmpeg_path"])
        browse = QPushButton(tr("btn.browse"))
        browse.clicked.connect(self._browse_ffmpeg)
        found = find_ffmpeg(adv["ffmpeg_path"])
        form.addRow(tr("adv.ffmpeg"), _row(self.ffmpeg_path, browse))
        form.addRow("", _hint(tr("adv.ffmpeg_found", path=found) if found else tr("adv.ffmpeg_missing")))
        layout.addWidget(group)

        remote = QGroupBox(tr("adv.remote"))
        form = QFormLayout(remote)
        self.remote_enabled = _check(tr("adv.remote_enable"), adv["remote_enabled"])
        self.remote_host = QLineEdit(adv["remote_host"])
        self.remote_port = _spin(1, 65535, int(adv["remote_port"]))
        form.addRow("", self.remote_enabled)
        form.addRow(tr("adv.remote_host"), self.remote_host)
        form.addRow(tr("adv.remote_port"), self.remote_port)
        form.addRow("", _hint("trip-streaming-tool -s | -d | -r | -t | -n | -u \"Artist - Title\" | -S | -q"))
        layout.addWidget(remote)

        logs = QGroupBox(tr("tab.log"))
        form = QFormLayout(logs)
        self.log_file = QLineEdit(adv["log_file"])
        form.addRow(tr("adv.log_file"), self.log_file)
        layout.addWidget(logs)
        layout.addStretch()
        return page

    def _browse_ffmpeg(self):
        path, _ = QFileDialog.getOpenFileName(self, "FFmpeg")
        if path:
            self.ffmpeg_path.setText(path)

    # -------------------------------------------------------------- GUI tab
    def _tab_gui(self) -> QWidget:
        g = self.work["gui"]
        page = QWidget()
        layout = QVBoxLayout(page)
        group = QGroupBox(tr("gui.language"))
        form = QFormLayout(group)
        self.language = _combo(list(LANGUAGES.items()), g["language"] or "en")
        self.language.currentIndexChanged.connect(self._language_changed)
        form.addRow(tr("gui.language"), self.language)
        form.addRow("", _hint(tr("gui.language_hint")))
        layout.addWidget(group)

        look = QGroupBox(tr("tab.gui"))
        form = QFormLayout(look)
        self.on_top = _check(tr("gui.on_top"), g["always_on_top"])
        self.start_min = _check(tr("gui.start_min"), g["start_minimized"])
        self.lcd_color = g["lcd_color"]
        self.lcd_btn = QPushButton("  ")
        self.lcd_btn.setStyleSheet(f"background: {self.lcd_color}; min-width: 60px;")
        self.lcd_btn.clicked.connect(self._pick_color)
        form.addRow("", self.on_top)
        form.addRow("", self.start_min)
        form.addRow(tr("gui.lcd_color"), _row(self.lcd_btn, "stretch"))
        layout.addWidget(look)
        layout.addStretch()
        return page

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self.lcd_color), self, tr("gui.lcd_color"))
        if color.isValid():
            self.lcd_color = color.name()
            self.lcd_btn.setStyleSheet(f"background: {self.lcd_color}; min-width: 60px;")

    def _language_changed(self):
        lang = self.language.currentData()
        self._collect()
        self.work["gui"]["language"] = lang
        # the language is applied and saved immediately
        self.controller.cfg["gui"]["language"] = lang
        self.controller.save_config()
        self.language_changed.emit(lang)
        self._build(self.tabs.currentIndex())

    # -------------------------------------------------------------- log tab
    def _tab_log(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        clear = QPushButton(tr("btn.clear_log"))
        clear.clicked.connect(self._clear_log)
        layout.addWidget(self.log_view)
        layout.addWidget(_row(clear, "stretch"))
        return page

    def _clear_log(self):
        self.controller.logs.clear()
        self.log_view.clear()

    def _refresh_log(self):
        if self.controller.log_serial != self._log_serial:
            self._log_serial = self.controller.log_serial
            self.log_view.setPlainText("\n".join(self.controller.logs))
            self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    # ---------------------------------------------------------------- apply
    def _collect(self) -> None:
        w = self.work
        self._collect_server_checks()
        w["stream"]["connect_at_startup"] = self.connect_startup.isChecked()
        a = w["audio"]
        for which in ("primary", "secondary"):
            combo, left, right = self.dev[which]
            a[f"{which}_device"] = combo.currentData()
            a[f"{which}_left"] = max(0, left.currentIndex())
            a[f"{which}_right"] = max(0, right.currentIndex())
        a["samplerate"] = self.samplerate.currentData()
        a["channels"] = self.channels.currentData()
        a["buffer_ms"] = self.buffer_ms.value()
        s = w["stream"]
        s.update({
            "codec": self.st_codec.currentData(), "bitrate": self.st_bitrate.currentData(),
            "aac_profile": self.st_aac.currentData(), "song_file": self.song_file.text().strip(),
            "song_file_line": self.song_line.currentData(), "song_from_app": self.song_app.isChecked(),
            "song_prefix": self.song_prefix.text(), "song_suffix": self.song_suffix.text(),
            "song_delay": self.song_delay.value(), "reconnect": self.reconnect.isChecked(),
            "reconnect_delay": self.reconnect_delay.value(), "reconnect_max": self.reconnect_max.value(),
            "start_on_signal": self.st_start_sig.isChecked(), "start_signal_secs": self.st_start_secs.value(),
            "stop_on_silence": self.st_stop_sil.isChecked(), "stop_silence_secs": self.st_stop_secs.value(),
        })
        w["detection"]["threshold_db"] = self.threshold.value()
        w["record"].update({
            "codec": self.rec_codec.currentData(), "bitrate": self.rec_bitrate.currentData(),
            "folder": self.rec_folder.text().strip(), "filename": self.rec_filename.text().strip() or "rec_%Y%m%d",
            "split_minutes": self.rec_split.value(), "split_sync": self.rec_sync.isChecked(),
            "start_on_connect": self.rec_start_conn.isChecked(), "stop_on_disconnect": self.rec_stop_disc.isChecked(),
            "start_on_signal": self.rec_start_sig.isChecked(), "start_signal_secs": self.rec_start_secs.value(),
            "stop_on_silence": self.rec_stop_sil.isChecked(), "stop_silence_secs": self.rec_stop_secs.value(),
        })
        w["dsp"] = self._collect_dsp()
        w["advanced"].update({
            "ffmpeg_path": self.ffmpeg_path.text().strip(), "remote_enabled": self.remote_enabled.isChecked(),
            "remote_host": self.remote_host.text().strip() or "127.0.0.1", "remote_port": self.remote_port.value(),
            "log_file": self.log_file.text().strip(),
        })
        w["gui"].update({
            "language": self.language.currentData(), "always_on_top": self.on_top.isChecked(),
            "start_minimized": self.start_min.isChecked(), "lcd_color": self.lcd_color,
        })

    def save(self) -> None:
        self._collect()
        # values edited from the main window meanwhile (song, mixer) stay as they are now
        self.work["mixer"] = copy.deepcopy(self.controller.cfg["mixer"])
        self.work["stream"]["song"] = self.controller.cfg["stream"]["song"]
        self.work["gui"]["geometry"] = self.controller.cfg["gui"]["geometry"]
        self.controller.apply_config(self.work)
        self.controller.save_config()
        self.controller.log(("msg.config_saved", {}))
        self.work = copy.deepcopy(self.controller.cfg)
        self.applied.emit()

    def closeEvent(self, event):
        # discard unsaved DSP previews
        self.controller.engine.apply_dsp(self.controller.cfg["dsp"])
        super().closeEvent(event)
