#!/usr/bin/env python3
"""Load and validate MCDP Format2 files from various formats.

This module provides a command-line interface to load and validate MCDP Format2
files from JSON, YAML, or CBOR formats. It automatically detects the format based
on file extension and supports transparent gzip decompression.

Usage:
    python -m mcdp_format2_py.load <file1> [<file2> ...]
    
Example:
    python -m mcdp_format2_py.load schema.json
    python -m mcdp_format2_py.load config.yaml data.cbor.gz
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path
from typing import Any, Dict, cast

# YAML: prefer ruamel.yaml for round-trip support; installed separately.
try:
    from ruamel.yaml import YAML  # type: ignore

    _RUAMEL_YAML: Any = YAML(typ="safe")  # safe loader/dumper
except ModuleNotFoundError:  # pragma: no cover
    _RUAMEL_YAML = None

try:
    import cbor2  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    cbor2 = None  # type: ignore

from mcdp_format2_py import Root


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_bytes(path: Path) -> bytes:
    """Read *path* and transparently decompress if it looks gzip-compressed."""
    # Detect gzip either via extension or magic number.
    if path.suffix == ".gz" or path.name.endswith(('.tgz', '.tz')):
        with gzip.open(path, "rb") as fh:
            return fh.read()

    # Fallback: attempt to open normally; if it is actually gzipped this will
    # raise an OSError which we do *not* catch here.
    return path.read_bytes()


def _detect_format(path: Path) -> str:
    """Return the lowercase name of the serialization format for *path*.

    Possible return values: ``'json'``, ``'yaml'``, or ``'cbor'``.
    """
    name = path.name.lower()
    if any(ext in name for ext in ('.yaml', '.yml')):
        return 'yaml'
    if '.json' in name:
        return 'json'
    if '.cbor' in name:
        return 'cbor'
    raise ValueError(f"Cannot determine format for file '{path}'.")


def _parse_bytes(data: bytes, fmt: str) -> Dict[str, Any]:
    """Parse *data* according to *fmt* and return a Python ``dict``."""
    if fmt == 'json':
        return json.loads(data.decode('utf-8'))
    if fmt == 'yaml':
        if _RUAMEL_YAML is None:
            raise RuntimeError("ruamel.yaml is required to parse YAML files. Install with 'pip install ruamel.yaml'.")
        # ruamel.yaml works with text streams/strings
        return cast(Dict[str, Any], _RUAMEL_YAML.load(data.decode("utf-8")))
    if fmt == 'cbor':
        if cbor2 is None:
            raise RuntimeError("cbor2 is required to parse CBOR files. Install with 'pip install cbor2'.")
        return cbor2.loads(data)
    # Should not happen.
    raise AssertionError(fmt)


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def _process_file(path_str: str) -> None:
    path = Path(path_str)
    try:
        raw = _read_bytes(path)
        fmt = _detect_format(path)
        data = _parse_bytes(raw, fmt)

        obj = Root.from_dict(data)  # type: ignore[arg-type]
        obj_class = obj.__class__.__name__ if obj is not None else 'None'
        print(f"[ OK ] {path}: decoded as {obj_class} (kind={getattr(obj, 'kind', '?')})")
    except Exception as exc:
        raise
        print(f"[FAIL] {path}: {exc}")


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("Usage: python load.py <file1> [<file2> ...]")
        sys.exit(1)

    for p in argv:
        _process_file(p)


if __name__ == '__main__':
    main()
