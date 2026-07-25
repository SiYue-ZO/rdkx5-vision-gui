from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from app.common.runtime_paths import bundled_path


class ConfigError(RuntimeError):
    pass


class ConfigManager:
    def __init__(self, root: str | Path = "configs") -> None:
        self.root = Path(root)
        # PyInstaller puts --add-data files under sys._MEIPASS (normally
        # ``_internal`` for an onedir bundle), not beside the executable.
        # Keep any saved settings in the working directory while using the
        # immutable bundled configuration as the first-run fallback.
        self.bundled_root = bundled_path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    def load(self, name: str, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.root / name
        data = deepcopy(defaults or {})
        source = path
        if not source.exists() and self.bundled_root is not None:
            bundled = self.bundled_root / name
            if bundled.exists():
                source = bundled
        if not source.exists():
            if defaults is not None:
                self.save(name, data)
            return data
        try:
            loaded = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise ConfigError(f"无法加载配置 {source}: {exc}") from exc
        if not isinstance(loaded, dict):
            raise ConfigError(f"配置根节点必须是映射: {source}")
        return _deep_merge(data, loaded)

    def save(self, name: str, data: dict[str, Any]) -> Path:
        path = self.root / name
        temp = path.with_suffix(path.suffix + ".tmp")
        try:
            temp.write_text(
                yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            temp.replace(path)
        except OSError as exc:
            raise ConfigError(f"无法保存配置 {path}: {exc}") from exc
        return path


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base
