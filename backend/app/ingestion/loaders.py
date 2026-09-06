import csv
import json
from pathlib import Path
from typing import Any


class UnsupportedFormatError(Exception):
    """Raised when a source file's extension has no registered loader."""


def load_json_records(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise UnsupportedFormatError(f"{path}: expected a JSON array or object, got {type(data).__name__}")
    return data


def load_csv_records(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


_LOADERS = {
    ".json": load_json_records,
    ".csv": load_csv_records,
}


def load_records(path: Path) -> list[dict[str, Any]]:
    """Dispatches by file extension so the ingestion layer can absorb
    whichever non-uniform export format a source shows up in (JSON today,
    CSV or others tomorrow) without touching the normalization logic."""
    loader = _LOADERS.get(path.suffix.lower())
    if loader is None:
        raise UnsupportedFormatError(f"{path}: unsupported file extension {path.suffix!r}")
    return loader(path)
