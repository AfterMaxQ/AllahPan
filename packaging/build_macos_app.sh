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

if [[ ! -f "$ROOT/build/AllahPan.icns" ]]; then
  echo ">>> 提示: 无 build/AllahPan.icns，将使用默认图标。可用图标编辑器把 图标.png 转为 icns 后放入 build/。"
fi

echo ">>> 开始 PyInstaller …"
$PYTHON -m PyInstaller "$ROOT/AllahPan-macOS.spec" "$@"

echo ">>> 完成: $ROOT/dist/AllahPan.app"
echo "    首次运行若被拦截: xattr -cr dist/AllahPan.app"
