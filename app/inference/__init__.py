from typing import Any

from app.inference.base import InferenceBackend
from app.inference.mock_backend import MockBackend


def create_backend(config: dict[str, Any]) -> InferenceBackend:
    name = config.get("backend", "mock")
    if name == "mock":
        return MockBackend()
    if name == "onnxruntime":
        from app.inference.onnx_backend import OnnxBackend

        return OnnxBackend()
    if name == "rdk-hbm":
        from app.inference.rdk_hbm_backend import RdkHbmBackend

        return RdkHbmBackend()
    if name == "rdk-legacy":
        from app.inference.rdk_legacy_backend import RdkLegacyBackend

        return RdkLegacyBackend()
    raise ValueError(f"未知推理后端: {name}")


__all__ = ["InferenceBackend", "MockBackend", "create_backend"]
