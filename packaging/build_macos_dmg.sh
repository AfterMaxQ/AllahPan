#!/usr/bin/env bash
# 从 dist/AllahPan.app 生成可发布的 .dmg（内含 Applications 替身，便于拖放安装）
# 用法：先 ./packaging/build_macos_app.sh，再：
#   chmod +x packaging/build_macos_dmg.sh
#   ./packaging/build_macos_dmg.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "错误：必须在 macOS 上运行。" >&2
  exit 1
fi

APP="$ROOT/dist/AllahPan.app"
if [[ ! -d "$APP" ]]; then
  echo "错误：未找到 $APP，请先执行 ./packaging/build_macos_app.sh" >&2
  exit 1
fi

VER="$("$ROOT/.venv/bin/python" -c "from version import __version__; print(__version__)" 2>/dev/null || python3 -c "from version import __version__; print(__version__)" 2>/dev/null || echo "1.0.0")"
VOLNAME="AllahPan ${VER}"
DMG_NAME="AllahPan-${VER}.dmg"
DMG_PATH="$ROOT/dist/${DMG_NAME}"

STAGE="$(mktemp -d "${TMPDIR:-/tmp}/allahpan-dmg.XXXXXX")"
cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

cp -R "$APP" "$STAGE/"
# 标准安装体验：用户把 .app 拖到「应用程序」
ln -sf /Applications "$STAGE/Applications"

rm -f "$DMG_PATH"
# UDZO：压缩只读映像，体积较小
hdiutil create -volname "$VOLNAME" -srcfolder "$STAGE" -ov -format UDZO -fs HFS+ "$DMG_PATH"

echo ">>> 已生成: $DMG_PATH"
echo "    挂载后应看到: AllahPan.app 与 Applications（文件夹替身）"
