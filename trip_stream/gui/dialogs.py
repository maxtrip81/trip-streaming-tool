"""Small dialogs: server editor, stream (ICY) info, first-run language choice, about."""

from __future__ import annotations

import copy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from trip_stream import __version__, config
from trip_stream.i18n import LANGUAGES, tr
from trip_stream.gui.widgets import icon_pixmap


def _buttons(dialog: QDialog) -> QDialogButtonBox:
    box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    box.button(QDialogButtonBox.StandardButton.Ok).setText(tr("btn.ok"))
    box.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("btn.cancel"))
    box.accepted.connect(dialog.accept)
    box.rejected.connect(dialog.reject)
    return box


class ServerDialog(QDialog):
    TYPES = [("icecast", "Icecast"), ("shoutcast", "SHOUTcast"), ("whip", "WebRTC (WHIP)")]

    def __init__(self, server: dict | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("server.title"))
        self.server = config.normalize_server(copy.deepcopy(server or {}))
        s = self.server
        form = QFormLayout()
        self.name = QLineEdit(s["name"])
        self.type = QComboBox()
        for key, label in self.TYPES:
            self.type.addItem(label, key)
        self.type.setCurrentIndex([k for k, _ in self.TYPES].index(s["type"]))
        self.host = QLineEdit(s["host"])
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(int(s["port"]))
        self.password = QLineEdit(s["password"])
        self.password.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.mount = QLineEdit(s["mount"])
        self.user = QLineEdit(s["user"])
        self.tls = QCheckBox(tr("server.tls"))
        self.tls.setChecked(bool(s["tls"]))
        self.tls_verify = QCheckBox(tr("server.tls_verify"))
        self.tls_verify.setChecked(bool(s["tls_verify"]))
        self.protocol = QComboBox()
        self.protocol.addItem(tr("server.protocol_put"), "put")
        self.protocol.addItem(tr("server.protocol_source"), "source")
        self.protocol.setCurrentIndex(0 if s["icecast_protocol"] == "put" else 1)
        self.sid = QSpinBox()
        self.sid.setRange(1, 999)
        self.sid.setValue(int(s["sc_sid"]))
        self.whip_url = QLineEdit(s["whip_url"])
        self.whip_url.setPlaceholderText("https://example.com/whip/endpoint")
        self.whip_token = QLineEdit(s["whip_token"])
        self.whip_token.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.whip_hint = QLabel(tr("server.whip_hint"))
        self.whip_hint.setObjectName("hint")
        self.whip_hint.setWordWrap(True)

        self._rows = {}
        for key, label, widget in [
            ("name", "server.name", self.name), ("type", "server.type", self.type),
            ("host", "server.host", self.host), ("port", "server.port", self.port),
            ("password", "server.password", self.password), ("mount", "server.mount", self.mount),
            ("user", "server.user", self.user), ("protocol", "server.protocol", self.protocol),
            ("sid", "server.sid", self.sid), ("whip_url", "server.whip_url", self.whip_url),
            ("whip_token", "server.whip_token", self.whip_token),
        ]:
            lab = QLabel(tr(label))
            form.addRow(lab, widget)
            self._rows[key] = (lab, widget)
        tls_row = QWidget()
        tls_layout = QHBoxLayout(tls_row)
        tls_layout.setContentsMargins(0, 0, 0, 0)
        tls_layout.addWidget(self.tls)
        tls_layout.addWidget(self.tls_verify)
        tls_layout.addStretch()
        form.addRow("", tls_row)
        self._rows["tls"] = (None, tls_row)
        form.addRow("", self.whip_hint)
        self._rows["whip_hint"] = (None, self.whip_hint)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(_buttons(self))
        self.type.currentIndexChanged.connect(self._update_visibility)
        self._update_visibility()
        self.setMinimumWidth(420)

    def _update_visibility(self):
        kind = self.type.currentData()
        show = {
            "icecast": {"host", "port", "password", "mount", "user", "protocol", "tls"},
            "shoutcast": {"host", "port", "password", "sid", "tls"},
            "whip": {"whip_url", "whip_token", "whip_hint"},
        }[kind]
        for key, (label, widget) in self._rows.items():
            if key in ("name", "type"):
                continue
            visible = key in show
            widget.setVisible(visible)
            if label is not None:
                label.setVisible(visible)

    def accept(self):
        if not self.name.text().strip():
            QMessageBox.warning(self, tr("server.title"), tr("server.name_required"))
            return
        self.server.update({
            "name": self.name.text().strip(), "type": self.type.currentData(), "host": self.host.text().strip(),
            "port": self.port.value(), "password": self.password.text(), "mount": self.mount.text().strip(),
            "user": self.user.text().strip() or "source", "tls": self.tls.isChecked(),
            "tls_verify": self.tls_verify.isChecked(), "icecast_protocol": self.protocol.currentData(),
            "sc_sid": self.sid.value(), "whip_url": self.whip_url.text().strip(),
            "whip_token": self.whip_token.text().strip(),
        })
        super().accept()


class IcyDialog(QDialog):
    FIELDS = ["name", "description", "genre", "url", "irc", "icq", "aim"]

    def __init__(self, icy: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("icy.title"))
        self.icy = dict(icy)
        form = QFormLayout()
        self.edits = {}
        for field in self.FIELDS:
            edit = QLineEdit(str(self.icy.get(field, "")))
            form.addRow(tr(f"icy.{field}"), edit)
            self.edits[field] = edit
        self.public = QCheckBox(tr("icy.public"))
        self.public.setChecked(bool(self.icy.get("public")))
        form.addRow("", self.public)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(_buttons(self))
        self.setMinimumWidth(420)

    def accept(self):
        for field, edit in self.edits.items():
            self.icy[field] = edit.text().strip()
        self.icy["public"] = self.public.isChecked()
        super().accept()


class LanguageDialog(QDialog):
    """Shown on first start when the installer did not set a language."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TRIP streaming tool")
        self.language = "en"
        layout = QVBoxLayout(self)
        logo = QLabel()
        logo.setPixmap(icon_pixmap(72))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)
        title = QLabel("<h3>Scegli la lingua · Choose your language</h3>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        hint = QLabel("Potrai cambiarla in seguito da Impostazioni → Interfaccia.<br>"
                      "You can change it later in Settings → Interface.")
        hint.setObjectName("hint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)
        row = QHBoxLayout()
        for code, label in [("it", "🇮🇹  Italiano"), ("en", "🇬🇧  English")]:
            btn = QPushButton(label)
            btn.setMinimumHeight(44)
            btn.clicked.connect(lambda _=False, c=code: self._choose(c))
            row.addWidget(btn)
        layout.addLayout(row)

    def _choose(self, code: str):
        self.language = code
        self.accept()


def show_about(parent):
    box = QMessageBox(parent)
    box.setWindowTitle(tr("about.title"))
    box.setIconPixmap(icon_pixmap(64))
    box.setTextFormat(Qt.TextFormat.RichText)
    box.setText(tr("about.text", version=__version__))
    box.exec()


def language_items():
    return list(LANGUAGES.items())
