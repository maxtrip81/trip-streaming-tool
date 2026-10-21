#!/bin/sh
# TRIP streaming tool – Linux installer / installazione per Linux
# Usage: ./install.sh [--lang it|en] [--prefix DIR]     (system-wide when run as root)
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
LANG_CHOICE=""
PREFIX=""
while [ $# -gt 0 ]; do
  case "$1" in
    --lang) LANG_CHOICE="$2"; shift 2 ;;
    --prefix) PREFIX="$2"; shift 2 ;;
    *) echo "unknown option $1"; exit 1 ;;
  esac
done

if [ -z "$LANG_CHOICE" ]; then
  echo "TRIP streaming tool – Max Trip"
  echo ""
  echo "Scegli la lingua / Choose the language:"
  echo "  1) Italiano"
  echo "  2) English"
  printf "> "
  read -r answer
  case "$answer" in
    2|en|EN|e|E) LANG_CHOICE=en ;;
    *) LANG_CHOICE=it ;;
  esac
fi

if [ "$(id -u)" = "0" ]; then
  PREFIX=${PREFIX:-/opt/trip-streaming-tool}
  BIN=/usr/local/bin
  APPS=/usr/share/applications
  ICONS=/usr/share/icons/hicolor/512x512/apps
else
  PREFIX=${PREFIX:-$HOME/.local/opt/trip-streaming-tool}
  BIN=$HOME/.local/bin
  APPS=$HOME/.local/share/applications
  ICONS=$HOME/.local/share/icons/hicolor/512x512/apps
fi

if [ "$LANG_CHOICE" = "it" ]; then
  echo "Installazione in $PREFIX …"
else
  echo "Installing to $PREFIX …"
fi
rm -rf "$PREFIX"
mkdir -p "$PREFIX" "$BIN" "$APPS" "$ICONS"
cp -R "$HERE/trip-streaming-tool/." "$PREFIX/"
printf '[TRIP]\nlanguage=%s\n' "$LANG_CHOICE" > "$PREFIX/language.ini"
ln -sf "$PREFIX/trip-streaming-tool" "$BIN/trip-streaming-tool"
cp "$HERE/icon.png" "$ICONS/trip-streaming-tool.png"
sed "s#@EXEC@#$PREFIX/trip-streaming-tool#" "$HERE/trip-streaming-tool.desktop" > "$APPS/trip-streaming-tool.desktop"
# store the choice for the current user too
if [ "$(id -u)" != "0" ]; then
  "$PREFIX/trip-streaming-tool" --set-language "$LANG_CHOICE" || true
fi
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" >/dev/null 2>&1 || true

if [ "$LANG_CHOICE" = "it" ]; then
  echo "Fatto! Avvia \"TRIP streaming tool\" dal menu delle applicazioni o con: trip-streaming-tool"
  echo "Disinstallazione: $PREFIX/uninstall.sh"
else
  echo "Done! Start \"TRIP streaming tool\" from the applications menu or run: trip-streaming-tool"
  echo "Uninstall: $PREFIX/uninstall.sh"
fi
cat > "$PREFIX/uninstall.sh" <<UNINSTALL
#!/bin/sh
rm -f "$BIN/trip-streaming-tool" "$APPS/trip-streaming-tool.desktop" "$ICONS/trip-streaming-tool.png"
rm -rf "$PREFIX"
echo "TRIP streaming tool removed / rimosso"
UNINSTALL
chmod +x "$PREFIX/uninstall.sh"
