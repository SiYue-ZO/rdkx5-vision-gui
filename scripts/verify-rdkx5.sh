#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -gt 0 ]; then
  python_bin="$1"
else
  python_bin="$(printenv RDKX5_PYTHON || printf python3)"
fi
machine="$(uname -m)"
if [[ "$machine" != "aarch64" && "$machine" != "arm64" ]]; then
  echo "warning: target architecture is $machine; RDK X5 normally reports aarch64" >&2
fi

"$python_bin" - <<'PY'
import importlib
import sys

required = ("numpy", "cv2", "serial", "yaml", "PyQt5.QtWidgets")
optional = ("hbm_runtime", "hobot_dnn", "libsrcampy")
missing = []
for name in required:
    try:
        importlib.import_module(name)
    except Exception as exc:
        missing.append(f"{name}: {exc}")
if missing:
    print("Missing required board Python modules:", file=sys.stderr)
    print("\n".join(f"  - {item}" for item in missing), file=sys.stderr)
    print("Install matching BSP packages and python3-serial/python3-yaml.", file=sys.stderr)
    raise SystemExit(2)
available = []
for name in optional:
    try:
        importlib.import_module(name)
        available.append(name)
    except Exception:
        pass
print(f"Python {sys.version.split()[0]}: required GUI runtime OK")
print("RDK optional runtimes: " + (", ".join(available) if available else "none detected"))
PY

"$python_bin" -m app.tools.environment_probe

"$python_bin" - <<'PY'
from pathlib import Path

from app.common.config import ConfigManager
from app.inference import create_backend

inference = ConfigManager().load("app.yaml").get("inference", {})
backend_name = inference.get("backend", "mock")
model_path = Path(inference.get("model", ""))
print(f"Configured inference: backend={backend_name}, model={model_path}")

if backend_name != "rdk-hbm":
    raise SystemExit("Expected configs/app.yaml to select backend: rdk-hbm")
if not model_path.is_file():
    raise SystemExit(f"Configured .bin model is missing: {model_path.resolve()}")

backend = create_backend(inference)
try:
    backend.load(inference)
    print(
        "Verified RDK .bin load: "
        f"model_name={backend.model_name}, input={backend.input_name}, "
        f"outputs={backend.output_names}"
    )
finally:
    backend.close()
PY
