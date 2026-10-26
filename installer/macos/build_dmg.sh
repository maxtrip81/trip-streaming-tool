#!/bin/sh
# Builds "TRIP-streaming-tool-<version>-macos.dmg" from the PyInstaller app bundle.
# The language (Italiano / English) is chosen in the first-start dialog, which is the
# installation step on macOS, and can be changed later in Settings -> Interface.
# A localized installer package (.pkg) with language choice can be built with build_pkg.sh.
set -e
cd "$(dirname "$0")/../.."
VERSION=$(python3 -c "import trip_stream; print(trip_stream.__version__)")
# the build is native for the machine it runs on: arm64 -> Apple Silicon, x86_64 -> Intel
if [ "$(uname -m)" = "arm64" ]; then ARCH=apple-silicon; HOST_ARCHS=arm64; else ARCH=intel; HOST_ARCHS="x86_64,arm64"; fi
APP="dist/TRIP streaming tool.app"
[ -d "$APP" ] || pyinstaller --noconfirm trip.spec
STAGE=$(mktemp -d)
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
cp installer/macos/LEGGIMI-README.txt "$STAGE/"
hdiutil create -volname "TRIP streaming tool" -srcfolder "$STAGE" -ov -format UDZO \
    "dist/TRIP-streaming-tool-$VERSION-macos-$ARCH.dmg"
rm -rf "$STAGE"
echo "dist/TRIP-streaming-tool-$VERSION-macos-$ARCH.dmg"
