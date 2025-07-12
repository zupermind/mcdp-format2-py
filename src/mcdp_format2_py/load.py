#!/usr/bin/env python3
"""Load and validate MCDP Format2 files from various formats.

This module provides a command-line interface to load and validate MCDP Format2
files from JSON, YAML, or CBOR formats. It automatically detects the format based
on file extension and supports transparent gzip decompression.

Usage:
    python -m mcdp_format2_py.load <file1> [<file2> ...]

"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path
from typing import Any
from typing import cast

from .formatter import human_format
from .schemas import load_Root

# YAML: prefer ruamel.yaml for round-trip support; installed separately.
try:
    from ruamel.yaml import YAML

    _RUAMEL_YAML: Any = YAML(typ="safe")  # safe loader/dumper
except ModuleNotFoundError:  # pragma: no cover
    _RUAMEL_YAML = None

try:
    import cbor2
except ModuleNotFoundError:  # pragma: no cover
    cbor2 = None

from mcdp_format2_py import Root

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_bytes(path: Path) -> bytes:
    """Read *path* and transparently decompress if it looks gzip-compressed."""
    # Detect gzip either via extension or magic number.
    if path.suffix == ".gz" or path.name.endswith((".tgz", ".tz")):
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
    if any(ext in name for ext in (".yaml", ".yml")):
        return "yaml"
    if ".json" in name:
        return "json"
    if ".cbor" in name:
        return "cbor"
    raise ValueError(f"Cannot determine format for file '{path}'.")


def _parse_bytes(data: bytes, fmt: str) -> dict[str, Any]:
    """Parse *data* according to *fmt* and return a Python ``dict``."""
    if fmt == "json":
        return json.loads(data.decode("utf-8"))
    if fmt == "yaml":
        if _RUAMEL_YAML is None:
            raise RuntimeError("ruamel.yaml is required to parse YAML files. Install with 'pip install ruamel.yaml'.")
        # ruamel.yaml works with text streams/strings
        return cast(dict[str, Any], _RUAMEL_YAML.load(data.decode("utf-8")))
    if fmt == "cbor":
        if cbor2 is None:
            raise RuntimeError("cbor2 is required to parse CBOR files. Install with 'pip install cbor2'.")
        return cbor2.loads(data)
    # Should not happen.
    raise AssertionError(fmt)


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

DEFAULT_PATTERNS = [
    "*.json",
    "*.json.gz",
    "*.yaml",
    "*.yml",
    "*.yaml.gz",
    "*.yml.gz",
    "*.cbor",
    "*.cbor.gz",
]


def _iter_input_paths(paths: list[str], patterns: list[str] | None = None):
    """Yield file paths to process given *paths* (files or directories).

    If an element in *paths* is a directory, it is searched recursively for
    files whose names match any of the glob *patterns*. The default set covers
    typical JSON, YAML, CBOR (optionally gzip-compressed) files.
    """
    patterns = patterns or DEFAULT_PATTERNS
    seen: set[Path] = set()
    for p_str in paths:
        p = Path(p_str)
        if p.is_dir():
            for pattern in patterns:
                for candidate in p.rglob(pattern):
                    if candidate not in seen and candidate.is_file():
                        seen.add(candidate)
                        yield candidate
        else:
            yield p


def load(path: Path) -> Root:
    """Load a file and return a Root object."""
    raw = _read_bytes(path)
    fmt = _detect_format(path)
    data = _parse_bytes(raw, fmt)
    obj = load_Root(data)
    return obj


def _process_file(path: Path, *, verbose: bool = False) -> None:
    try:
        obj = load(path)

        obj_class = obj.__class__.__name__
        print(f"[ OK ] {path}: decoded as {obj_class} (kind={getattr(obj, 'kind', '?')})")

        if verbose:
            print(human_format(obj))

    except Exception as exc:
        print(f"[FAIL] {path}: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="python -m mcdp_format2_py.load",
        description="Load and validate MCDP Format2 files from JSON, YAML, or CBOR formats.",
    )
    parser.add_argument("paths", nargs="+", help="File or directory paths to load. Directories are searched recursively.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print the raw parsed data after successful decoding.")
    parser.add_argument(
        "-p",
        "--pattern",
        action="append",
        metavar="GLOB",
        help="Glob pattern(s) to use when searching directories (can be repeated). Defaults to typical JSON/YAML/CBOR patterns.",
    )

    args = parser.parse_args(argv)

    patterns = args.pattern if args.pattern else DEFAULT_PATTERNS

    for path in _iter_input_paths(args.paths, patterns):
        _process_file(path, verbose=args.verbose)


if __name__ == "__main__":
    main()
