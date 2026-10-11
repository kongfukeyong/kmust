#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SDK=${ANDROID_SDK_ROOT:-/opt/kust-study/build/android-sdk}
BT="$SDK/android-15"
PLATFORM="$SDK/android-35/android.jar"
BUILD="$ROOT/build"
mkdir -p "$BUILD/classes" "$BUILD/dex" "$BUILD/assets/site" "$BUILD/gen"
for item in index.html originals.html styles.css originals.css app.js originals.js icon.svg thumbs math-render.js math-media vendor fonts; do
  cp -R "$ROOT/../public/$item" "$BUILD/assets/site/"
done
mkdir -p "$BUILD/assets/site/data"
for item in resources.json questions.json extraction-report.json original-packages.json; do
  cp "$ROOT/../public/data/$item" "$BUILD/assets/site/data/$item"
done
# Downloaded APKs are never bundled recursively.
if [ -d "$BUILD/assets/site/downloads" ]; then find "$BUILD/assets/site/downloads" -name '*.apk' -delete; fi
"$BT/aapt" package -f -M "$ROOT/AndroidManifest.xml" -S "$ROOT/res" -A "$BUILD/assets" -I "$PLATFORM" -J "$BUILD/gen" -F "$BUILD/unsigned.apk"
javac -encoding UTF-8 -source 8 -target 8 -bootclasspath "$PLATFORM:$BT/core-lambda-stubs.jar" -d "$BUILD/classes" $(find "$ROOT/src" "$BUILD/gen" -name '*.java')
"$BT/d8" --lib "$PLATFORM" --min-api 26 --output "$BUILD/dex" $(find "$BUILD/classes" -name '*.class')
(cd "$BUILD/dex" && zip -q -u "$BUILD/unsigned.apk" classes.dex)
"$BT/zipalign" -f 4 "$BUILD/unsigned.apk" "$BUILD/aligned.apk"
SIGNING_DIR=${SIGNING_DIR:-/opt/kust-study/signing}
mkdir -p "$SIGNING_DIR"
chmod 700 "$SIGNING_DIR"
if [ ! -f "$SIGNING_DIR/release.p12" ]; then
  umask 077
  openssl rand -hex 24 > "$SIGNING_DIR/password"
  keytool -genkeypair -keystore "$SIGNING_DIR/release.p12" -storetype PKCS12 -storepass:file "$SIGNING_DIR/password" -alias kust-release -keyalg RSA -keysize 3072 -validity 10000 -dname "CN=KUST Study, O=Personal Study, C=CN"
fi
"$BT/apksigner" sign --ks "$SIGNING_DIR/release.p12" --ks-key-alias kust-release --ks-pass "file:$SIGNING_DIR/password" --out "$BUILD/kust-study.apk" "$BUILD/aligned.apk"
"$BT/apksigner" verify --verbose "$BUILD/kust-study.apk"
"$BT/aapt" dump badging "$BUILD/kust-study.apk" | head -8
sha256sum "$BUILD/kust-study.apk"
