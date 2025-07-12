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
from typing import Any, Dict, cast, get_origin, get_args
import argparse
import dataclasses
import functools
import os
import re
import inspect

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal

try:
    from colorama import Fore, Style, init
    init(autoreset=True)  # Auto-reset after each print
    _HAS_COLORAMA = True
except ImportError:
    _HAS_COLORAMA = False
    # Fallback to ANSI codes
    class _MockStyle:
        RESET_ALL = "\033[0m"
        BRIGHT = "\033[1m"
    
    class _MockFore:
        CYAN = "\033[36m"
        GREEN = "\033[32m"
        YELLOW = "\033[33m"
        MAGENTA = "\033[35m"
        RED = "\033[31m"
        RESET = "\033[0m"
    
    Style = _MockStyle()
    Fore = _MockFore()


def _get_terminal_width() -> int:
    """Get terminal width from COLUMNS env var or default to 120."""
    try:
        return int(os.environ.get('COLUMNS', '120'))
    except ValueError:
        return 120


def _screen_length(text: str) -> int:
    """Calculate the visible screen length of text by removing ANSI/color codes."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return len(ansi_escape.sub('', text))


# ---------------------------------------------------------------------------
# Human-friendly colorful visualization (returns string, recursive & cached)
# ---------------------------------------------------------------------------
import traceback

class HumanFormatter:
    """Human-friendly colorful formatter with caching."""
    
    def __init__(self, skip_none_fields: bool = False, skip_single_literal_fields: bool = False) -> None:
        # Cache formatted objects by (id, column_budget) to avoid recomputation and cycles.
        self._cache: dict[tuple[int, int], str] = {}
        self.skip_none_fields = skip_none_fields
        self.skip_single_literal_fields = skip_single_literal_fields
    
    def _is_single_literal_field(self, obj: Any, field_name: str) -> bool:
        """Check if field type is a Literal with exactly one value."""
        # Get the actual type annotation from the class using inspect
        cls = obj.__class__
        annotations = inspect.get_annotations(cls, eval_str=True)
        field_type = annotations.get(field_name)
        
        
        # Check if it's a Literal type
        if get_origin(field_type) is Literal:
            args = get_args(field_type)
            return len(args) == 1
        
        return False
    
    def _colorize_leaf(self, value: Any) -> str:
        """Return *value* converted to string with color codes."""
        if isinstance(value, str):
            if value == "":
                return f"{Fore.GREEN}\"\"{Style.RESET_ALL}"
            return f"{Fore.GREEN}{value}{Style.RESET_ALL}"
        if isinstance(value, bool):
            if value:
                symbol = "✓"
                color = Fore.GREEN
            else:
                symbol = "✗"
                color = Fore.RED
            return f"{color}{symbol}{Style.RESET_ALL}"
        if isinstance(value, (int, float)):
            return f"{Fore.YELLOW}{value}{Style.RESET_ALL}"
        if value is None:
            return f"{Fore.CYAN}None{Style.RESET_ALL}"
        return str(value)

    def _format_obj_inner(self, obj: Any, column_budget: int = _get_terminal_width()) -> str:
        """Return colored representation of *obj* without any indentation.
        
        Args:
            obj: Object to format
            column_budget: Maximum width for inline formatting of lists
        """
        obj_id = id(obj)
        cache_key = (obj_id, column_budget)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Dataclass
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):  # type: ignore[arg-type]
            cls_name = obj.__class__.__name__
            
            # Render all fields first
            field_parts: list[str] = []
            for field in dataclasses.fields(obj):  # type: ignore[arg-type]
                field_name = field.name
                field_value = getattr(obj, field_name)
                
                # Skip None fields if requested
                if self.skip_none_fields and field_value is None:
                    continue
                
                # Skip single-literal fields if requested
                if self.skip_single_literal_fields and self._is_single_literal_field(obj, field_name):
                    continue
                    
                # Format the value without the key
                if dataclasses.is_dataclass(field_value) or isinstance(field_value, (dict, list, tuple)):  # type: ignore[arg-type]
                    value_formatted = self._format_obj_inner(field_value, column_budget)
                else:
                    value_formatted = self._colorize_leaf(field_value)
                field_parts.append(f"{field_name}: {value_formatted}")
            
            # Check if all fields are single-line and fit in budget
            all_single_line = all("\n" not in part for part in field_parts)
            if all_single_line:
                inline_str = f"{Style.BRIGHT}{Fore.MAGENTA}{cls_name}{Style.RESET_ALL}({', '.join(field_parts)})"
                if _screen_length(inline_str) <= column_budget:
                    result = f"{Style.BRIGHT}{Fore.MAGENTA}{cls_name}{Style.RESET_ALL}({', '.join(field_parts)})"
                    self._cache[cache_key] = result
                    return result
            
            # Multi-line format
            lines = [f"{Style.BRIGHT}{Fore.MAGENTA}{cls_name}{Style.RESET_ALL}:"]
            for field in dataclasses.fields(obj):  # type: ignore[arg-type]
                field_value = getattr(obj, field.name)
                
                # Skip None fields if requested
                if self.skip_none_fields and field_value is None:
                    continue
                
                # Skip single-literal fields if requested
                if self.skip_single_literal_fields and self._is_single_literal_field(obj, field.name):
                    continue
                    
                field_formatted = self._format_key_value(field.name, field_value, column_budget)
                # Indent each line of the field
                for line in field_formatted.splitlines():
                    lines.append("  " + line)
            result = "\n".join(lines)
            self._cache[cache_key] = result
            return result

        # Dict
        if isinstance(obj, dict):  # type: ignore[arg-type]
            # Empty dict
            if not obj:
                result = "{}"
                self._cache[cache_key] = result
                return result
            
            parts: list[str] = []
            for k, v in obj.items():  # type: ignore[arg-type]
                parts.append(self._format_key_value(str(k), v, column_budget))  # type: ignore[arg-type]
            result = "\n".join(parts)
            self._cache[cache_key] = result
            return result

        # List / tuple
        if isinstance(obj, (list, tuple)):
            # Render all items first
            rendered_items: list[str] = []
            for item in obj:  # type: ignore[arg-type]
                if dataclasses.is_dataclass(item) or isinstance(item, (dict, list, tuple)):  # type: ignore[arg-type]
                    rendered_items.append(self._format_obj_inner(item, column_budget))
                else:
                    rendered_items.append(self._colorize_leaf(item))
            
            # Check if all items are single-line and fit in budget
            all_single_line = all("\n" not in item for item in rendered_items)  # type: ignore[arg-type]
            if all_single_line:
                inline_str = "[" + ", ".join(rendered_items) + "]"  # type: ignore[arg-type]
                if _screen_length(inline_str) <= column_budget:
                    result = inline_str
                    self._cache[cache_key] = result
                    return result
            
            # Multi-line format
            parts: list[str] = []
            for rendered_item in rendered_items:  # type: ignore[assignment]
                lines = rendered_item.splitlines()  # type: ignore[attr-defined]
                if lines:
                    # First line goes after the dash
                    parts.append(f"- {lines[0]}")
                    # Subsequent lines align with the content (2 spaces for "- ")
                    for line in lines[1:]:
                        parts.append("  " + line)
                else:
                    parts.append("-")
            result = "\n".join(parts)
            self._cache[cache_key] = result
            return result

        # Primitive leaf
        leaf = self._colorize_leaf(obj)
        self._cache[cache_key] = leaf
        return leaf

    def _format_key_value(self, key: str, value: Any, column_budget: int = _get_terminal_width()) -> str:
        """Format *value* under *key* without any base indentation."""
        key_col = f"{Style.BRIGHT}{Fore.CYAN}{key}{Style.RESET_ALL}"

        # Complex value
        if dataclasses.is_dataclass(value) or isinstance(value, (dict, list, tuple)):  # type: ignore[arg-type]
            formatted = self._format_obj_inner(value, column_budget)
            
            # Use inline format if the representation has no newlines
            if "\n" not in formatted:
                return f"{key_col}: {formatted}"
            
            # Multi-line format
            lines = [f"{key_col}:"]
            for line in formatted.splitlines():
                # For lists/tuples that start with "- ", don't add extra indentation
                if isinstance(value, (list, tuple)) and line.startswith("- "):
                    lines.append(line)
                else:
                    lines.append("  " + line)
            return "\n".join(lines)

        # Multiline string
        if isinstance(value, str) and "\n" in value:
            split_lines = value.splitlines()
            first = self._colorize_leaf(split_lines[0]) if split_lines else ""
            out = [f"{key_col}: {first}"]
            align_pad = " " * (len(key) + 2)
            for ln in split_lines[1:]:
                out.append(f"{align_pad}{self._colorize_leaf(ln)}")
            return "\n".join(out)

        # Simple leaf
        return f"{key_col}: {self._colorize_leaf(value)}"

    def format(self, obj: Any) -> str:
        """Return a cached, human-friendly colored string representation of *obj*."""
        self._cache.clear()
        return self._format_obj_inner(obj, _get_terminal_width())


def human_format(obj: Any) -> str:
    """Return a cached, human-friendly colored string representation of *obj*."""
    formatter = HumanFormatter(skip_none_fields=True, skip_single_literal_fields=True)
    return formatter.format(obj)

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
