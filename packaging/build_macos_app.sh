#!/usr/bin/env bash
# 在 macOS 上生成 dist/AllahPan.app（PyInstaller BUNDLE 仅支持 Darwin）
# 用法：在项目根目录执行
#   chmod +x packaging/build_macos_app.sh
#   ./packaging/build_macos_app.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "错误：必须在 macOS 上运行才能生成 AllahPan.app（当前: $(uname -s)）。" >&2
  echo "请把仓库拷到 Apple 芯片或 Intel 的 Mac 上再执行本脚本。" >&2
  exit 1
fi

PYTHON="${PYTHON:-python3.12}"
if ! command -v "$PYTHON" &>/dev/null; then
  PYTHON="python3"
fi

VENV="$ROOT/.venv"
if [[ -f "$VENV/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$VENV/bin/activate"
fi

echo ">>> 使用解释器: $($PYTHON -c 'import sys; print(sys.executable)')"
$PYTHON -m pip install -q -U pip
$PYTHON -m pip install -q "PyInstaller>=6.0" || $PYTHON -m pip install -q PyInstaller

# spec 只认 build/AllahPan.icns；若你把 icns 放在 packaging/ 可自动拷贝过去
if [[ ! -f "$ROOT/build/AllahPan.icns" ]] && [[ -f "$ROOT/packaging/AllahPan.icns" ]]; then
  mkdir -p "$ROOT/build"
  cp "$ROOT/packaging/AllahPan.icns" "$ROOT/build/AllahPan.icns"
  echo ">>> 已使用 packaging/AllahPan.icns"
fi

# 仅有 图标.png 时：用 sips + iconutil 生成 build/AllahPan.icns（PyInstaller 只认 .icns，不认 .png）
if [[ ! -f "$ROOT/build/AllahPan.icns" ]] && [[ -f "$ROOT/图标.png" ]]; then
  echo ">>> 从 图标.png 生成 build/AllahPan.icns …"
  mkdir -p "$ROOT/build"
  _SQ="$ROOT/build/_icon_square.png"
  _M="$ROOT/build/_icon_master.png"
  _IS="$ROOT/build/AllahPan.iconset"
  rm -rf "$_IS"
  mkdir -p "$_IS"
  # 原图 1530×1616：居中裁成正方形再缩到 1024，避免非正方形图标在 iconutil 下报错
  sips -c 1530 1530 --cropOffset 43 0 "$ROOT/图标.png" --out "$_SQ" >/dev/null
  sips -Z 1024 "$_SQ" --out "$_M" >/dev/null
  sips -z 16 16     "$_M" --out "$_IS/icon_16x16.png" >/dev/null
  sips -z 32 32     "$_M" --out "$_IS/icon_16x16@2x.png" >/dev/null
  sips -z 32 32     "$_M" --out "$_IS/icon_32x32.png" >/dev/null
  sips -z 64 64     "$_M" --out "$_IS/icon_32x32@2x.png" >/dev/null
  sips -z 128 128   "$_M" --out "$_IS/icon_128x128.png" >/dev/null
  sips -z 256 256   "$_M" --out "$_IS/icon_128x128@2x.png" >/dev/null
  sips -z 256 256   "$_M" --out "$_IS/icon_256x256.png" >/dev/null
  sips -z 512 512   "$_M" --out "$_IS/icon_256x256@2x.png" >/dev/null
  sips -z 512 512   "$_M" --out "$_IS/icon_512x512.png" >/dev/null
  sips -z 1024 1024 "$_M" --out "$_IS/icon_512x512@2x.png" >/dev/null
  iconutil -c icns "$_IS" -o "$ROOT/build/AllahPan.icns"
  rm -rf "$_IS" "$_SQ" "$_M"
  echo ">>> 已生成 build/AllahPan.icns"
fi

if [[ ! -f "$ROOT/build/AllahPan.icns" ]]; then
  echo ">>> 提示: 无 build/AllahPan.icns，将使用默认图标。可将 图标.png 放在项目根目录后重新执行本脚本以自动生成。"
fi

echo ">>> 开始 PyInstaller …"
# -y：dist 目录非空时直接覆盖，避免「The output directory is not empty」中断
$PYTHON -m PyInstaller -y "$ROOT/AllahPan-macOS.spec" "$@"

# PyInstaller 6.x .app：bootloader 仍会在「可执行文件目录/_internal」下加载 libpython，
# 但 BUNDLE 将二进制放在 Contents/Frameworks 且未必生成 _internal，导致
# 「Failed to load Python shared library .../MacOS/_internal/libpython*.dylib」。
# 将 MacOS/_internal 指向 Frameworks 后，与 Resources 侧已通过符号链接对齐的数据布局一致。
fix_macos_meipass_symlink() {
  local bundle="$1"
  local macos_dir="$bundle/Contents/MacOS"
  [[ -d "$macos_dir" ]] || return 0
  if [[ -d "$macos_dir/_internal" ]] && [[ ! -L "$macos_dir/_internal" ]]; then
    return 0
  fi
  ln -sfn ../Frameworks "$macos_dir/_internal"
  echo ">>> 已创建 $bundle/Contents/MacOS/_internal -> ../Frameworks（兼容 bootloader 路径）"
}
for _bundle in "$ROOT/dist/AllahPan.app" "$ROOT/dist/AllahPan"; do
  if [[ -d "$_bundle/Contents" ]]; then
    fix_macos_meipass_symlink "$_bundle"
  fi
done

echo ">>> 完成: $ROOT/dist/AllahPan.app 或 $ROOT/dist/AllahPan（与 BUNDLE name 一致）"
echo "    首次运行若被拦截: xattr -cr dist/AllahPan.app  # 或 dist/AllahPan"
