"""Entry point: GUI, headless mode and command-line remote control of a running instance."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time

from trip_stream import APP_NAME, AUTHOR, __version__
from trip_stream import config as config_mod
from trip_stream.i18n import set_language

CLIENT_FLAGS = [
    ("connect", "-s", "--connect", "connect to the enabled servers / avvia lo streaming"),
    ("disconnect", "-d", "--disconnect", "disconnect / ferma lo streaming"),
    ("record_start", "-r", "--record", "start recording / avvia la registrazione"),
    ("record_stop", "-t", "--stop-record", "stop recording / ferma la registrazione"),
    ("split", "-n", "--split", "split the recording file / dividi il file di registrazione"),
    ("status", "-S", "--status", "print status as JSON / mostra lo stato in JSON"),
    ("quit", "-q", "--quit", "quit the running instance / chiudi l'istanza in esecuzione"),
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trip-streaming-tool",
        description=f"{APP_NAME} {__version__} – {AUTHOR}",
        epilog="Without client options the graphical interface starts. / Senza opzioni client si avvia "
               "l'interfaccia grafica.")
    parser.add_argument("-c", "--config", help="configuration file / file di configurazione")
    parser.add_argument("-L", "--language", choices=["it", "en"], help="interface language (saved) / lingua")
    parser.add_argument("--set-language", choices=["it", "en"],
                        help="save the language and exit (used by installers) / salva la lingua ed esci")
    parser.add_argument("-H", "--headless", action="store_true",
                        help="run without GUI, controlled by remote commands / esegui senza interfaccia")
    parser.add_argument("--list-devices", action="store_true", help="list audio inputs / elenca ingressi audio")
    parser.add_argument("-V", "--version", action="version", version=f"{APP_NAME} {__version__}")
    client = parser.add_argument_group("remote control of a running instance / controllo remoto")
    for command, short, long, text in CLIENT_FLAGS:
        client.add_argument(short, long, dest=f"cmd_{command}", action="store_true", help=text)
    client.add_argument("-u", "--song", metavar="TEXT", help="update song title / aggiorna il titolo del brano")
    client.add_argument("-a", "--address", default=None, help="remote address (default 127.0.0.1)")
    client.add_argument("-p", "--port", type=int, default=None, help="remote port (default 1256)")
    return parser


def run_client(args, cfg) -> int:
    from trip_stream.remote import send_command
    host = args.address or cfg["advanced"]["remote_host"] or "127.0.0.1"
    port = args.port or int(cfg["advanced"]["remote_port"])
    commands = [c for c, *_ in CLIENT_FLAGS if getattr(args, f"cmd_{c}")]
    if args.song is not None:
        commands.insert(0, "song")
    rc = 0
    for command in commands:
        try:
            reply = send_command(host, port, command, args.song if command == "song" else "")
        except OSError as exc:
            print(f"{APP_NAME}: cannot reach {host}:{port} ({exc})", file=sys.stderr)
            return 2
        if command == "status":
            print(json.dumps(reply.get("result"), indent=2, ensure_ascii=False))
        elif not reply.get("ok"):
            print(reply.get("error"), file=sys.stderr)
            rc = 1
    return rc


def run_headless(controller) -> int:
    stop = {"flag": False}

    def handler(*_):
        stop["flag"] = True
    signal.signal(signal.SIGINT, handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handler)
    controller.start()
    printed = 0
    try:
        while not stop["flag"] and not controller.quit_requested:
            logs = list(controller.logs)
            for line in logs[printed:] if len(logs) >= printed else logs:
                print(line, flush=True)
            printed = len(logs)
            time.sleep(0.25)
    finally:
        controller.shutdown()
        for line in list(controller.logs)[printed:]:
            print(line, flush=True)
    return 0


def run_gui(controller, cfg) -> int:
    from PySide6.QtWidgets import QApplication
    from trip_stream.gui.dialogs import LanguageDialog
    from trip_stream.gui.main_window import MainWindow
    from trip_stream.gui.theme import STYLE
    from trip_stream.gui.widgets import app_icon

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("Max Trip")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setWindowIcon(app_icon())
    if not config_mod.resolve_language(cfg):
        dlg = LanguageDialog()
        dlg.exec()
        cfg["gui"]["language"] = dlg.language
        controller.save_config()
    set_language(config_mod.resolve_language(cfg) or "en")
    controller.start()
    window = MainWindow(controller)
    if cfg["gui"]["start_minimized"]:
        window.showMinimized()
    else:
        window.show()
    try:
        return app.exec()
    finally:
        controller.shutdown()


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    cfg_path = args.config
    cfg = config_mod.load(cfg_path)

    if args.set_language:
        cfg["gui"]["language"] = args.set_language
        config_mod.save(cfg, cfg_path)
        return 0
    if args.language:
        cfg["gui"]["language"] = args.language
        config_mod.save(cfg, cfg_path)
    set_language(config_mod.resolve_language(cfg) or config_mod.system_language())

    if args.list_devices:
        from trip_stream.audio import devices
        for dev in devices.list_input_devices():
            print(f"{dev['index']:3d}  {dev['label']}  ({dev['channels']} ch, {dev['samplerate']} Hz)")
        return 0
    if args.song is not None or any(getattr(args, f"cmd_{c}") for c, *_ in CLIENT_FLAGS):
        return run_client(args, cfg)

    from trip_stream.controller import Controller
    controller = Controller(cfg, cfg_path)
    if args.headless:
        return run_headless(controller)
    return run_gui(controller, cfg)


if __name__ == "__main__":
    raise SystemExit(main())
