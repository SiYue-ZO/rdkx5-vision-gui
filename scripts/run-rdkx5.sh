#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
app_root="$(cd "$script_dir/.." && pwd)"
cd "$app_root"
python_bin="$(printenv RDKX5_PYTHON || printf python3)"
previous_pythonpath="$(printenv PYTHONPATH || true)"
if [ -n "$previous_pythonpath" ]; then
  export PYTHONPATH="$app_root:$previous_pythonpath"
else
  export PYTHONPATH="$app_root"
fi
exec "$python_bin" main.py "$@"
