import sys
from pathlib import Path

from app.common.config import ConfigManager
from app.common.runtime_paths import resolve_data_file


def test_frozen_bundle_config_is_used_when_working_copy_is_missing(monkeypatch):
    test_root = Path("tests/.runtime/frozen_bundle_config").resolve()
    bundle = test_root / "_internal"
    (bundle / "configs").mkdir(parents=True, exist_ok=True)
    (bundle / "configs" / "app.yaml").write_text("inference:\n  backend: rdk-hbm\n", encoding="utf-8")
    working_directory = test_root / "working"
    working_directory.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(working_directory)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)

    assert ConfigManager().load("app.yaml")["inference"]["backend"] == "rdk-hbm"


def test_frozen_bundle_model_is_used_when_working_copy_is_missing(monkeypatch):
    bundle = Path("tests/.runtime/frozen_bundle_model/_internal").resolve()
    model = bundle / "models" / "detector.bin"
    model.parent.mkdir(parents=True, exist_ok=True)
    model.write_bytes(b"model")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)

    assert resolve_data_file("models/detector.bin") == model.resolve()
