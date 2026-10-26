"""Check the minimum macOS version required by every Mach-O binary in a built app (or any folder).

Wheels sometimes contain binaries built for a newer macOS than their platform tag says (e.g. PySide6 6.12
binaries need macOS 26). macOS refuses to load such a library, so the app would not start on older systems.

Usage: python tools/check_macos_minos.py "dist/TRIP streaming tool.app" 12.3
Exit code 1 when a binary requires a newer macOS than the given maximum.
"""
import os
import struct
import sys


def _ver(v):
    return (v >> 16, (v >> 8) & 0xFF)


def _thin(data, off=0):
    magic = struct.unpack_from("<I", data, off)[0]
    if magic not in (0xFEEDFACF, 0xFEEDFACE):
        return []
    ncmds = struct.unpack_from("<I", data, off + 16)[0]
    p = off + (32 if magic == 0xFEEDFACF else 28)
    found = []
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", data, p)
        if cmd == 0x32:  # LC_BUILD_VERSION: platform, minos, sdk
            found.append(struct.unpack_from("<I", data, p + 12)[0])
        elif cmd == 0x24:  # LC_VERSION_MIN_MACOSX: version, sdk
            found.append(struct.unpack_from("<I", data, p + 8)[0])
        p += size
    return found


def minimum_versions(data):
    if len(data) < 32:
        return []
    if struct.unpack_from(">I", data, 0)[0] == 0xCAFEBABE:  # universal binary
        count = struct.unpack_from(">I", data, 4)[0]
        if count > 20:  # Java class files share the magic number
            return []
        found = []
        for i in range(count):
            offset = struct.unpack_from(">I", data, 8 + i * 20 + 8)[0]
            found += _thin(data, offset)
        return found
    return _thin(data)


def main():
    root, limit = sys.argv[1], tuple(int(x) for x in sys.argv[2].split("."))
    results = []
    for folder, _, files in os.walk(root):
        for name in files:
            path = os.path.join(folder, name)
            if os.path.islink(path):
                continue
            with open(path, "rb") as fh:
                head = fh.read(4)
                if head not in (b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe"):
                    continue
                data = head + fh.read()
            versions = minimum_versions(data)
            if versions:
                results.append((max(_ver(v) for v in versions), os.path.relpath(path, root)))
    results.sort(reverse=True)
    newest = results[0][0] if results else (0, 0)
    print(f"{len(results)} binaries, highest minimum macOS: {newest[0]}.{newest[1]}")
    too_new = [(v, p) for v, p in results if v > limit]
    for v, p in too_new[:20]:
        print(f"  requires macOS {v[0]}.{v[1]}: {p}")
    if too_new:
        print(f"::error title=macOS compatibility::{len(too_new)} binaries require a macOS newer than "
              f"{sys.argv[2]} (first: {too_new[0][1]} needs {too_new[0][0][0]}.{too_new[0][0][1]})")
        sys.exit(1)
    print(f"::notice title=macOS minimum::the app runs on macOS {newest[0]}.{newest[1]} or newer")


if __name__ == "__main__":
    main()
