#!/bin/sh
# Prints the minimum macOS version required by the binaries of an app bundle (highest "minos" found).
find "$1" -type f \( -name "*.so" -o -name "*.dylib" -o -perm -u+x \) -print0 2>/dev/null \
  | xargs -0 otool -l 2>/dev/null \
  | awk '/LC_BUILD_VERSION/{b=1} b&&/minos/{print $2; b=0} /LC_VERSION_MIN_MACOSX/{v=1} v&&/ version/{print $2; v=0}' \
  | sort -t. -k1,1n -k2,2n | tail -1
