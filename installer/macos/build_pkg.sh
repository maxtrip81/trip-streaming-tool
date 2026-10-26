#!/bin/sh
# Builds a macOS installer package whose wizard lets the user pick the program language.
# Each language is an installer "choice"; the postinstall script writes language.ini.
set -e
cd "$(dirname "$0")/../.."
VERSION=$(python3 -c "import trip_stream; print(trip_stream.__version__)")
# the build is native for the machine it runs on: arm64 -> Apple Silicon, x86_64 -> Intel
if [ "$(uname -m)" = "arm64" ]; then ARCH=apple-silicon; HOST_ARCHS=arm64; else ARCH=intel; HOST_ARCHS="x86_64,arm64"; fi
APP="dist/TRIP streaming tool.app"
[ -d "$APP" ] || pyinstaller --noconfirm trip.spec
WORK=$(mktemp -d)
mkdir -p "$WORK/root/Applications" "$WORK/scripts-it" "$WORK/scripts-en" "$WORK/empty"
cp -R "$APP" "$WORK/root/Applications/"
pkgbuild --root "$WORK/root" --identifier it.maxtrip.tripstreamingtool --version "$VERSION" \
    --install-location / "$WORK/app.pkg"
for LANG_CODE in it en; do
  cat > "$WORK/scripts-$LANG_CODE/postinstall" <<SCRIPT
#!/bin/sh
printf '[TRIP]\nlanguage=$LANG_CODE\n' > "/Applications/TRIP streaming tool.app/Contents/MacOS/language.ini"
exit 0
SCRIPT
  chmod +x "$WORK/scripts-$LANG_CODE/postinstall"
  pkgbuild --nopayload --scripts "$WORK/scripts-$LANG_CODE" \
      --identifier "it.maxtrip.tripstreamingtool.lang.$LANG_CODE" --version "$VERSION" "$WORK/lang-$LANG_CODE.pkg"
done
cat > "$WORK/distribution.xml" <<XML
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
  <title>TRIP streaming tool $VERSION</title>
  <options customize="always" require-scripts="false" hostArchitectures="$HOST_ARCHS"/>
  <choices-outline>
    <line choice="app"/>
    <line choice="lang_it"/>
    <line choice="lang_en"/>
  </choices-outline>
  <choice id="app" title="TRIP streaming tool" enabled="false" selected="true">
    <pkg-ref id="it.maxtrip.tripstreamingtool"/>
  </choice>
  <choice id="lang_it" title="Lingua: Italiano" start_selected="true"
          selected="!choices['lang_en'].selected">
    <pkg-ref id="it.maxtrip.tripstreamingtool.lang.it"/>
  </choice>
  <choice id="lang_en" title="Language: English" start_selected="false"
          selected="!choices['lang_it'].selected">
    <pkg-ref id="it.maxtrip.tripstreamingtool.lang.en"/>
  </choice>
  <pkg-ref id="it.maxtrip.tripstreamingtool">app.pkg</pkg-ref>
  <pkg-ref id="it.maxtrip.tripstreamingtool.lang.it">lang-it.pkg</pkg-ref>
  <pkg-ref id="it.maxtrip.tripstreamingtool.lang.en">lang-en.pkg</pkg-ref>
</installer-gui-script>
XML
productbuild --distribution "$WORK/distribution.xml" --package-path "$WORK" \
    "dist/TRIP-streaming-tool-$VERSION-macos-$ARCH.pkg"
rm -rf "$WORK"
echo "dist/TRIP-streaming-tool-$VERSION-macos-$ARCH.pkg"
