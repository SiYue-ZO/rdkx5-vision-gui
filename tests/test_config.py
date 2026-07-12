from pathlib import Path

from app.common.config import ConfigManager


def test_config_round_trip_and_merge():
    manager = ConfigManager(Path("tests/.runtime"))
    manager.save("test.yaml", {"nested": {"value": 2}, "text": "中文"})
    assert manager.load("test.yaml", {"nested": {"value": 1, "kept": True}}) == {
        "nested": {"value": 2, "kept": True},
        "text": "中文",
    }
