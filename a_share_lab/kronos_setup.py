"""Install the minimal pinned official Kronos inference source."""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.request import Request, urlopen

from .data import default_cache_dir
from .kronos_signal import KronosSignalConfig


OFFICIAL_FILE_HASHES = {
    "model/__init__.py": "f8f856ca3fedadcaac97e196be23d1aeda1c3c9ffe8903d66d43ea3bcac6240c",
    "model/kronos.py": "0a5f90282e2039c2de0771473419715c845def154896dbd0f5747837e6241032",
    "model/module.py": "a07edbadc0e96804c8158c021bbc6063bb7cc43b34d7fc470d5c8ff2005a409f",
}


def default_source_dir() -> Path:
    return default_cache_dir() / "vendor" / "Kronos-runtime"


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def verify_runtime_source(source: Path) -> None:
    """Refuse locally modified or incomplete model source at inference time."""
    for relative, expected_hash in OFFICIAL_FILE_HASHES.items():
        path = Path(source) / relative
        if not path.exists():
            raise FileNotFoundError(f"Kronos source file is missing: {path}")
        actual_hash = _sha256(path.read_bytes())
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"Kronos source hash mismatch for {relative}: {actual_hash}"
            )


def setup_runtime(target: Path | None = None, timeout: int = 120) -> Path:
    """Download three source files and verify their pinned content hashes."""
    destination = Path(target or default_source_dir())
    revision = KronosSignalConfig().source_revision
    base = f"https://raw.githubusercontent.com/shiyu-coder/Kronos/{revision}"
    for relative, expected_hash in OFFICIAL_FILE_HASHES.items():
        path = destination / relative
        if path.exists() and _sha256(path.read_bytes()) == expected_hash:
            continue
        request = Request(f"{base}/{relative}", headers={"User-Agent": "stocks-agent-research"})
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
        actual_hash = _sha256(payload)
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"Kronos source hash mismatch for {relative}: {actual_hash}"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(payload)
        temporary.replace(path)
    verify_runtime_source(destination)
    return destination


def main() -> None:
    print(setup_runtime())


if __name__ == "__main__":
    main()
