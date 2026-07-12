from __future__ import annotations

import importlib

from app.inference.rdk_hbm_backend import RdkHbmBackend


class RdkLegacyBackend(RdkHbmBackend):
    name = "rdk-legacy"

    @property
    def available(self) -> bool:
        return importlib.util.find_spec("hobot_dnn") is not None

    def load(self, config: dict) -> None:
        runner = config.get("runner")
        if not runner:
            raise RuntimeError("旧版 hobot_dnn API 因 BSP 差异需要通过 config['runner'] 注入适配器")
        super().load(config)
