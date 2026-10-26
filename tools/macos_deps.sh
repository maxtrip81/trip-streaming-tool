#!/bin/sh
# Install the build dependencies using only wheels made for macOS $1 (e.g. 12.0) or older, so that the
# app also runs on that macOS version; pip would otherwise pick wheels for the build machine's macOS.
set -e
MIN=${1:-12.0}
TAG="macosx_$(echo "$MIN" | tr . _)_$(uname -m)"
PYV=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
python3 -m pip download --only-binary=:all: --platform "$TAG" --python-version "$PYV" -d wheelhouse \
    -r requirements.txt pyinstaller pillow
python3 -m pip install --no-index --find-links wheelhouse -r requirements.txt pyinstaller pillow
python3 -m pip list | grep -iE "pyside6|shiboken6|numpy|scipy|^av |aiortc|imageio"
