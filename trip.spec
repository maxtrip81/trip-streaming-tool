# PyInstaller spec for TRIP streaming tool (Windows, macOS, Linux).
# Build:  pyinstaller trip.spec
import sys
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("imageio_ffmpeg", include_py_files=False)
binaries = []  # PortAudio for sounddevice is collected by pyinstaller-hooks-contrib

icon = "assets/icon.ico" if sys.platform.startswith("win") else "assets/icon.icns"

a = Analysis(
    ["trip_stream/__main__.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=["aiortc", "av", "scipy.signal"],
    excludes=["tkinter", "matplotlib", "PIL", "pytest", "PySide6.QtWebEngineCore", "PySide6.Qt3DCore"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="trip-streaming-tool", console=False, icon=icon,
          upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="trip-streaming-tool", upx=False)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="TRIP streaming tool.app",
        icon="assets/icon.icns",
        bundle_identifier="it.maxtrip.tripstreamingtool",
        info_plist={
            "CFBundleName": "TRIP streaming tool",
            "CFBundleShortVersionString": "1.0.2",
            "CFBundleDevelopmentRegion": "it",
            "CFBundleLocalizations": ["it", "en"],
            "NSMicrophoneUsageDescription":
                "TRIP streaming tool needs audio input to broadcast live. / "
                "TRIP streaming tool usa l'ingresso audio per trasmettere in diretta.",
            "NSHighResolutionCapable": True,
        },
    )
