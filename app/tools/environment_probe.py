from __future__ import annotations

import importlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any


def module_info(name: str) -> dict[str, Any]:
    try:
        module = importlib.import_module(name)
        return {
            "available": True,
            "version": getattr(module, "__version__", "unknown"),
            "path": getattr(module, "__file__", "built-in"),
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)}


def command_output(command: list[str]) -> str | None:
    try:
        return (
            subprocess.run(
                command, capture_output=True, text=True, timeout=5, check=False
            ).stdout.strip()
            or None
        )
    except (OSError, subprocess.SubprocessError):
        return None


def collect() -> dict[str, Any]:
    report: dict[str, Any] = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version,
        "display": os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"),
        "modules": {
            name: module_info(name)
            for name in (
                "PyQt5.QtCore",
                "cv2",
                "numpy",
                "serial",
                "yaml",
                "hbm_runtime",
                "hobot_dnn",
                "libsrcampy",
            )
        },
    }
    if sys.platform.startswith("linux"):
        report["kernel"] = command_output(["uname", "-a"])
        report["os_release"] = (
            Path("/etc/os-release").read_text(errors="replace")
            if Path("/etc/os-release").exists()
            else None
        )
        report["video_devices"] = [str(item) for item in Path("/dev").glob("video*")]
        report["serial_devices"] = [
            str(item)
            for pattern in ("ttyUSB*", "ttyACM*", "ttyS*", "ttyAMA*", "ttyTHS*", "ttyHS*")
            for item in Path("/dev").glob(pattern)
        ]
        report["hrt_model_exec"] = command_output(["hrt_model_exec", "--help"])
    return report


def main() -> int:
    report = collect()
    output = Path("environment-report.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n报告已保存至 {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
