#!/usr/bin/env python3
"""Create a source bundle for an RDK X5 Linux target.

Native runtime components deliberately stay on the board because Qt, OpenCV,
and RDK BPU/MIPI libraries must match its BSP ABI.
"""

from __future__ import annotations

import argparse
import hashlib
import tarfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "dist" / "rdkx5-vision.tar.gz"
TOP_LEVEL_ITEMS = ("app", "configs", "models", "scripts", "main.py", "pyproject.toml")
SKIPPED_DIRECTORIES = {
    ".git", ".venv", ".agents", "__pycache__", ".pytest_cache", ".ruff_cache",
    "build", "dist", "logs", "recordings", "screenshots",
}


def should_include(path: Path, *, include_models: bool) -> bool:
    relative = path.relative_to(PROJECT_ROOT)
    if any(part in SKIPPED_DIRECTORIES for part in relative.parts):
        return False
    if not include_models and relative.parts and relative.parts[0] == "models":
        return False
    return path.suffix not in {".pyc", ".pyo"}


def iter_files(*, include_models: bool) -> list[Path]:
    files: list[Path] = []
    for item_name in TOP_LEVEL_ITEMS:
        item = PROJECT_ROOT / item_name
        if not item.exists():
            continue
        if item.is_file():
            if should_include(item, include_models=include_models):
                files.append(item)
            continue
        files.extend(
            path for path in item.rglob("*")
            if path.is_file() and should_include(path, include_models=include_models)
        )
    return sorted(files)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="output .tar.gz path")
    parser.add_argument("--no-models", action="store_true", help="do not include files under models/")
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    if output.suffixes[-2:] != [".tar", ".gz"]:
        parser.error("--output must end in .tar.gz")
    output.parent.mkdir(parents=True, exist_ok=True)

    files = iter_files(include_models=not args.no_models)
    if not files:
        raise RuntimeError("No project files found to package")
    with tarfile.open(output, "w:gz") as archive:
        for source in files:
            archive.add(source, arcname=f"rdkx5-vision/{source.relative_to(PROJECT_ROOT).as_posix()}")

    checksum_path = output.with_suffix(output.suffix + ".sha256")
    checksum_path.write_text(f"{sha256(output)}  {output.name}\n", encoding="utf-8")
    print(output)
    print(checksum_path)
    print(f"Packaged {len(files)} files ({output.stat().st_size / 1024 / 1024:.1f} MiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
