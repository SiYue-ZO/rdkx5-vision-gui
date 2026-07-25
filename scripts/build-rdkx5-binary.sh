#!/usr/bin/env bash
# Build an aarch64 executable bundle on an RDK X5 board.
#
# PyInstaller must run on the target architecture so that its embedded Python,
# Qt and OpenCV extensions match the board BSP. The resulting executable is
# binary-dist/rdkx5-vision/rdkx5-vision.
set -euo pipefail

if [ "$#" -gt 0 ]; then
  python_bin="$1"
else
  python_bin="$(printenv RDKX5_PYTHON || printf python3)"
fi

project_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$project_root"

if ! "$python_bin" -m PyInstaller --version >/dev/null 2>&1; then
  echo "PyInstaller is not installed for $python_bin." >&2
  echo "Install it on the board once, for example:" >&2
  echo "  $python_bin -m pip install --user 'pyinstaller>=6,<7'" >&2
  exit 3
fi

build_root="$project_root/.pyinstaller-build"
dist_root="$project_root/binary-dist"
args=(
  --noconfirm
  --clean
  --onedir
  --console
  --name rdkx5-vision
  --distpath "$dist_root"
  --workpath "$build_root/work"
  --specpath "$build_root/spec"
  --paths "$project_root"
  --add-data "$project_root/configs:configs"
  --add-data "$project_root/models:models"
  --collect-submodules app
  # list_ports chooses its Linux implementation dynamically; make it present in
  # the frozen bundle even when PyInstaller cannot infer that import.
  --collect-submodules serial
  --hidden-import serial.tools.list_ports_posix
)

# These imports are lazy in the application. Include an installed BSP module
# when present; this preserves BPU/MIPI support in the frozen executable.
for module in hbm_runtime hobot_dnn libsrcampy; do
  if "$python_bin" -c "import importlib; importlib.import_module('$module')" >/dev/null 2>&1; then
    args+=(--hidden-import "$module" --collect-all "$module")
  fi
done

"$python_bin" -m PyInstaller "${args[@]}" main.py

binary="$dist_root/rdkx5-vision/rdkx5-vision"
if [ ! -x "$binary" ]; then
  echo "PyInstaller completed but binary was not created: $binary" >&2
  exit 4
fi
echo "Binary bundle built: $binary"
