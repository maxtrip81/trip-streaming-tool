#!/bin/sh
# Packages the PyInstaller build into TRIP-streaming-tool-<version>-linux-x86_64.tar.gz
set -e
cd "$(dirname "$0")/../.."
VERSION=$(python3 -c "import trip_stream; print(trip_stream.__version__)")
[ -d dist/trip-streaming-tool ] || pyinstaller --noconfirm trip.spec
NAME="TRIP-streaming-tool-$VERSION-linux-$(uname -m)"
STAGE="dist/$NAME"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R dist/trip-streaming-tool "$STAGE/"
cp installer/linux/install.sh installer/linux/trip-streaming-tool.desktop assets/icon.png LICENSE README.md "$STAGE/"
chmod +x "$STAGE/install.sh"
tar -C dist -czf "dist/$NAME.tar.gz" "$NAME"
echo "dist/$NAME.tar.gz"
