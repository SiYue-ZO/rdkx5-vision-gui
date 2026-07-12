from __future__ import annotations

from app.algorithms.base import VisionAlgorithm


class AlgorithmRegistry:
    """算法类注册表；主窗口只依赖它发现插件，不直接引用具体算法。"""

    def __init__(self) -> None:
        self._classes: dict[str, type[VisionAlgorithm]] = {}

    def register(self, algorithm: type[VisionAlgorithm]) -> type[VisionAlgorithm]:
        """注册算法类，也可作为装饰器使用；同名注册会替换旧实现。"""
        if not algorithm.name or algorithm.name == "base":
            raise ValueError("算法必须声明唯一 name")
        self._classes[algorithm.name] = algorithm
        return algorithm

    def create(self, name: str) -> VisionAlgorithm:
        """为一次视频管线创建独立算法实例。"""
        try:
            return self._classes[name]()
        except KeyError as exc:
            raise KeyError(f"未知算法: {name}") from exc

    def available(self) -> list[tuple[str, str]]:
        return [(name, cls.display_name) for name, cls in self._classes.items()]


def create_default_registry() -> AlgorithmRegistry:
    """在此导入并注册内置/用户算法；新增插件通常只需修改本函数。"""
    from app.algorithms.plugins.basic import EdgeAlgorithm, HsvTargetAlgorithm, PassthroughAlgorithm
    from app.algorithms.plugins.yolo import YoloAlgorithm

    registry = AlgorithmRegistry()
    for item in (PassthroughAlgorithm, EdgeAlgorithm, HsvTargetAlgorithm, YoloAlgorithm):
        registry.register(item)
    return registry
