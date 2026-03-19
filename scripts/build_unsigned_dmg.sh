#!/bin/zsh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

APP_NAME="Talky"
APP_BUNDLE_ID="com.talky.app"
DIST_DIR="$PROJECT_DIR/dist"
BUILD_DIR="$PROJECT_DIR/build"
DMG_DIR="$PROJECT_DIR/release"
STAGE_DIR="$BUILD_DIR/dmg_stage"
ICON_PATH="$PROJECT_DIR/assets/app.icns"
ENTITLEMENTS_PATH="$BUILD_DIR/entitlements.plist"

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  VERSION="$(date +%Y.%m.%d)-$(git rev-parse --short HEAD 2>/dev/null || echo dev)"
fi

DMG_NAME="${APP_NAME}-${VERSION}-unsigned.dmg"
DMG_PATH="$DMG_DIR/$DMG_NAME"
TMP_DMG_PATH="$BUILD_DIR/${APP_NAME}-tmp.dmg"

echo "==> Building unsigned DMG for ${APP_NAME}"
echo "==> Version: ${VERSION}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required."
  exit 1
fi

if [[ ! -d ".venv" ]]; then
  echo "==> Creating virtual environment..."
  python3 -m venv .venv
fi
source ".venv/bin/activate"

echo "==> Installing runtime dependencies..."
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt >/dev/null

if ! python -m pip show pyinstaller >/dev/null 2>&1; then
  echo "==> Installing pyinstaller..."
  python -m pip install pyinstaller >/dev/null
fi

echo "==> Cleaning old artifacts..."
rm -rf "$BUILD_DIR" "$DIST_DIR"
mkdir -p "$DMG_DIR" "$STAGE_DIR"
export PYINSTALLER_CONFIG_DIR="$BUILD_DIR/pyinstaller-cache"

read -r MLX_LIB_DIR MLX_WHISPER_ASSETS_DIR <<< "$(
  python - <<'PY'
from pathlib import Path
import mlx, mlx_whisper

mlx_roots = list(getattr(mlx, "__path__", []))
mlx_lib = (Path(mlx_roots[0]).resolve() / "lib").as_posix() if mlx_roots else ""

whisper_roots = list(getattr(mlx_whisper, "__path__", []))
whisper_assets = (Path(whisper_roots[0]).resolve() / "assets").as_posix() if whisper_roots else ""

print(mlx_lib, whisper_assets)
PY
)"

EXTRA_PYI_ARGS=()
if [[ -d "$MLX_LIB_DIR" ]]; then
  EXTRA_PYI_ARGS+=(--add-data "${MLX_LIB_DIR}:mlx/lib")
fi
if [[ -d "$MLX_WHISPER_ASSETS_DIR" ]]; then
  EXTRA_PYI_ARGS+=(--add-data "${MLX_WHISPER_ASSETS_DIR}:mlx_whisper/assets")
fi
TRAY_ICON_DIR="$PROJECT_DIR/assets"
if [[ -f "$TRAY_ICON_DIR/tray_icon.png" ]]; then
  EXTRA_PYI_ARGS+=(--add-data "$TRAY_ICON_DIR/tray_icon.png:assets")
  EXTRA_PYI_ARGS+=(--add-data "$TRAY_ICON_DIR/tray_icon@2x.png:assets")
fi
if [[ -f "$TRAY_ICON_DIR/talky-logo.png" ]]; then
  EXTRA_PYI_ARGS+=(--add-data "$TRAY_ICON_DIR/talky-logo.png:assets")
fi

RUNTIME_HOOK="$PROJECT_DIR/scripts/pyinstaller_hooks/runtime_hook_stubs.py"

echo "==> Building ${APP_NAME}.app with PyInstaller..."
python -m PyInstaller \
  --noconfirm \
  --windowed \
  --specpath "$BUILD_DIR" \
  --name "$APP_NAME" \
  --icon "$ICON_PATH" \
  --hidden-import "mlx._reprlib_fix" \
  --hidden-import "AVFoundation" \
  --hidden-import "pyobjc-framework-AVFoundation" \
  --exclude-module torch \
  --exclude-module llvmlite \
  --exclude-module scipy \
  --exclude-module numba \
  --runtime-hook "$RUNTIME_HOOK" \
  "${EXTRA_PYI_ARGS[@]}" \
  main.py

if [[ ! -d "$DIST_DIR/${APP_NAME}.app" ]]; then
  echo "Error: expected app bundle not found at $DIST_DIR/${APP_NAME}.app"
  exit 1
fi

APP_PLIST="$DIST_DIR/${APP_NAME}.app/Contents/Info.plist"
if [[ -f "$APP_PLIST" ]]; then
  echo "==> Injecting macOS privacy usage descriptions..."
  /usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier $APP_BUNDLE_ID" "$APP_PLIST" \
    || /usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string $APP_BUNDLE_ID" "$APP_PLIST"
  /usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "$APP_PLIST" \
    || /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string $VERSION" "$APP_PLIST"
  /usr/libexec/PlistBuddy -c "Set :NSMicrophoneUsageDescription Talky needs microphone access for hold-to-talk recording." "$APP_PLIST" \
    || /usr/libexec/PlistBuddy -c "Add :NSMicrophoneUsageDescription string Talky needs microphone access for hold-to-talk recording." "$APP_PLIST"
  /usr/libexec/PlistBuddy -c "Set :NSInputMonitoringUsageDescription Talky needs input monitoring to listen for global hotkeys." "$APP_PLIST" \
    || /usr/libexec/PlistBuddy -c "Add :NSInputMonitoringUsageDescription string Talky needs input monitoring to listen for global hotkeys." "$APP_PLIST"
  /usr/libexec/PlistBuddy -c "Set :NSSupportsAutomaticTermination false" "$APP_PLIST" \
    || /usr/libexec/PlistBuddy -c "Add :NSSupportsAutomaticTermination bool false" "$APP_PLIST"
  /usr/libexec/PlistBuddy -c "Set :NSSupportsSuddenTermination false" "$APP_PLIST" \
    || /usr/libexec/PlistBuddy -c "Add :NSSupportsSuddenTermination bool false" "$APP_PLIST"
fi

echo "==> Creating entitlements for audio-input access..."
mkdir -p "$(dirname "$ENTITLEMENTS_PATH")"
cat > "$ENTITLEMENTS_PATH" <<'ENTEOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.device.audio-input</key>
    <true/>
</dict>
</plist>
ENTEOF

echo "==> Re-signing app bundle (ad-hoc) with entitlements..."
codesign --force --deep --sign - \
  --identifier "$APP_BUNDLE_ID" \
  --entitlements "$ENTITLEMENTS_PATH" \
  "$DIST_DIR/${APP_NAME}.app"

echo "==> Verifying code signature..."
codesign --verify --verbose=2 "$DIST_DIR/${APP_NAME}.app"
SIGNED_ID=$(codesign -dvvv "$DIST_DIR/${APP_NAME}.app" 2>&1 | grep '^Identifier=' | cut -d= -f2)
echo "    Identifier: $SIGNED_ID"
if [[ "$SIGNED_ID" != "$APP_BUNDLE_ID" ]]; then
  echo "Error: signed identifier '$SIGNED_ID' does not match expected '$APP_BUNDLE_ID'"
  exit 1
fi

echo "==> Preparing DMG stage..."
cp -R "$DIST_DIR/${APP_NAME}.app" "$STAGE_DIR/"
ln -sfn "/Applications" "$STAGE_DIR/Applications"

echo "==> Creating DMG..."
rm -f "$TMP_DMG_PATH" "$DMG_PATH"
hdiutil create \
  -volname "$APP_NAME Installer" \
  -srcfolder "$STAGE_DIR" \
  -ov \
  -format UDRW \
  "$TMP_DMG_PATH" >/dev/null

hdiutil convert \
  "$TMP_DMG_PATH" \
  -format UDZO \
  -o "$DMG_PATH" >/dev/null

rm -f "$TMP_DMG_PATH"

echo "==> Done"
echo "DMG: $DMG_PATH"
echo "Note: this DMG is unsigned and not notarized."
