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
import argparse
import dataclasses
import functools

# ---------------------------------------------------------------------------
# Human-friendly colorful visualization (returns string, recursive & cached)
# ---------------------------------------------------------------------------

_RESET = "\033[0m"
_BOLD = "\033[1m"
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_MAGENTA = "\033[35m"


# Cache formatted objects by id to avoid recomputation and cycles.
_VIS_CACHE: dict[int, str] = {}


def _colorize_leaf(value: Any) -> str:
    """Return *value* converted to string with ANSI color codes."""
    if isinstance(value, str):
        return f"{_GREEN}{value}{_RESET}"
    if isinstance(value, (int, float)):
        return f"{_YELLOW}{value}{_RESET}"
    if isinstance(value, bool):
        return f"{_MAGENTA}{value}{_RESET}"
    if value is None:
        return f"{_CYAN}null{_RESET}"
    return str(value)


# Internal recursive formatter (use *_inner* suffix)


def _format_obj_inner(obj: Any) -> str:
    """Return colored representation of *obj* without any indentation."""
    obj_id = id(obj)
    if obj_id in _VIS_CACHE:
        return _VIS_CACHE[obj_id]

    # Dataclass
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):  # type: ignore[arg-type]
        cls_name = obj.__class__.__name__
        lines = [f"{_BOLD}{_MAGENTA}{cls_name}{_RESET}:"]
        for field in dataclasses.fields(obj):  # type: ignore[arg-type]
            field_formatted = _format_key_value(field.name, getattr(obj, field.name))
            # Indent each line of the field
            for line in field_formatted.splitlines():
                lines.append("  " + line)
        result = "\n".join(lines)
        _VIS_CACHE[obj_id] = result
        return result

    # Dict
    if isinstance(obj, dict):  # type: ignore[arg-type]
        parts: list[str] = []
        for k, v in obj.items():  # type: ignore[arg-type]
            parts.append(_format_key_value(str(k), v))  # type: ignore[arg-type]
        result = "\n".join(parts)
        _VIS_CACHE[obj_id] = result
        return result

    # List / tuple
    if isinstance(obj, (list, tuple)):
        parts: list[str] = []
        for item in obj:  # type: ignore[arg-type]
            if dataclasses.is_dataclass(item) or isinstance(item, (dict, list, tuple)):  # type: ignore[arg-type]
                parts.append("-")
                item_formatted = _format_obj_inner(item)
                for line in item_formatted.splitlines():
                    parts.append("  " + line)
            else:
                parts.append(f"- {_colorize_leaf(item)}")
        result = "\n".join(parts)
        _VIS_CACHE[obj_id] = result
        return result

    # Primitive leaf
    leaf = _colorize_leaf(obj)
    _VIS_CACHE[obj_id] = leaf
    return leaf


def _format_key_value(key: str, value: Any) -> str:
    """Format *value* under *key* without any base indentation."""
    key_col = f"{_BOLD}{_CYAN}{key}{_RESET}"

    # Complex value
    if dataclasses.is_dataclass(value) or isinstance(value, (dict, list, tuple)):  # type: ignore[arg-type]
        formatted = _format_obj_inner(value)
        lines = [f"{key_col}:"]
        for line in formatted.splitlines():
            lines.append("  " + line)
        return "\n".join(lines)

    # Multiline string
    if isinstance(value, str) and "\n" in value:
        split_lines = value.splitlines()
        first = _colorize_leaf(split_lines[0]) if split_lines else ""
        out = [f"{key_col}: {first}"]
        align_pad = " " * (len(key) + 2)
        for ln in split_lines[1:]:
            out.append(f"{align_pad}{_colorize_leaf(ln)}")
        return "\n".join(out)

    # Simple leaf
    return f"{key_col}: {_colorize_leaf(value)}"


# Public API: takes only *obj* argument.


def _format_obj(obj: Any) -> str:
    """Return colored representation of *obj* (wrapper, single argument)."""
    return _format_obj_inner(obj)


def human_format(obj: Any) -> str:
    """Return a cached, human-friendly colored string representation of *obj*."""
    _VIS_CACHE.clear()
    return _format_obj(obj)

from mcdp_format2_py.schemas import load_Root

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

DEFAULT_PATTERNS = [
    '*.json', '*.json.gz',
    '*.yaml', '*.yml', '*.yaml.gz', '*.yml.gz',
    '*.cbor', '*.cbor.gz',
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


def _process_file(path: Path, *, verbose: bool = False) -> None:
    try:
        raw = _read_bytes(path)
        fmt = _detect_format(path)
        data = _parse_bytes(raw, fmt)
        obj = load_Root(data)
        obj_class = obj.__class__.__name__ if obj is not None else 'None'
        print(f"[ OK ] {path}: decoded as {obj_class} (kind={getattr(obj, 'kind', '?')})")
        
        if verbose:
            print(human_format(obj))

        
    except Exception as exc:
        print(f"[FAIL] {path}: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="python -m mcdp_format2_py.load",
        description="Load and validate MCDP Format2 files from JSON, YAML, or CBOR formats."
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="File or directory paths to load. Directories are searched recursively."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print the raw parsed data after successful decoding."
    )
    parser.add_argument(
        "-p", "--pattern",
        action="append",
        metavar="GLOB",
        help="Glob pattern(s) to use when searching directories (can be repeated). Defaults to typical JSON/YAML/CBOR patterns."
    )

    args = parser.parse_args(argv)

    patterns = args.pattern if args.pattern else DEFAULT_PATTERNS

    for path in _iter_input_paths(args.paths, patterns):
        _process_file(path, verbose=args.verbose)


if __name__ == '__main__':
    main()
