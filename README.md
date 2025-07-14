# mcdp-format2-py

Python library for loading and validating MCDP Format 2 files from JSON, YAML, and CBOR formats.

## Installation

```bash
pip install mcdp-format2-py
```

## Python API

The primary use of this library is to load and validate MCDP Format 2 files programmatically:

```python
from mcdp_format2_py import load, human_format
from mcdp_format2_py.schemas import DP, MonotoneMap


# Load and validate a file
fn = 'model.ndp.mcdp2.yaml'
root = load(fn)

# Display the contents
print(human_format(obj))

# Process the various subtypes
match root:
    DP(): 
        ...
    MonotoneMap():
        ...

 
```

## Demo Command Line Tool

The package includes a demo command-line tool `mcdp-format2-py-load` for exploring and validating MCDP Format2 files from various formats (JSON, YAML, CBOR) with optional gzip compression.

### Basic Usage

```bash
# Load a single file
mcdp-format2-py-load uncertain2.dpc.mcdp2.yaml

# Load all supported files from a directory recursively
mcdp-format2-py-load path/to/directory/
```

### Options

#### `--verbose` / `-v`
Display the parsed data in a human-friendly, colorized format after successful validation.

```bash
mcdp-format2-py-load --verbose uncertain2.dpc.mcdp2.yaml
```

The verbose output features:
- **Color-coded values**: Strings in green, numbers in yellow, booleans as ✓/✗ in green/red
- **Smart formatting**: Automatic inline vs multi-line layout decisions
- **Clean display**: Skips None fields and single-value Literal type fields
- **Proper indentation**: Lists and nested structures with consistent alignment

#### `--pattern` / `-p`
Specify custom glob patterns when searching directories (can be used multiple times).

```bash
# Only process JSON files
mcdp-format2-py-load --pattern "*.json" /path/to/directory/

# Process JSON and YAML files
mcdp-format2-py-load --pattern "*.json" --pattern "*.yaml" /path/to/directory/
```

**Default patterns:**
- `*.json`, `*.json.gz`
- `*.yaml`, `*.yml`, `*.yaml.gz`, `*.yml.gz`
- `*.cbor`, `*.cbor.gz`

### Supported Formats

The tool automatically detects file format based on extension:

| Format | Extensions | Compression |
|--------|------------|-------------|
| JSON   | `.json`    | `.json.gz`  |
| YAML   | `.yaml`, `.yml` | `.yaml.gz`, `.yml.gz` |
| CBOR   | `.cbor`    | `.cbor.gz`  |

### Examples

```bash
# Validate a single schema file
mcdp-format2-py-load schema.json

# Validate and display contents of a compressed YAML file
mcdp-format2-py-load --verbose config.yaml.gz

# Process all MCDP files in a project directory
mcdp-format2-py-load --verbose ./project/schemas/

# Process only JSON files in a directory
mcdp-format2-py-load --pattern "*.json" ./data/

# Validate multiple specific files
mcdp-format2-py-load schema.json config.yaml data.cbor
```

### Output

The tool provides status messages:

```
[ OK ] schema.json: decoded as MySchema (kind=schema)
[ OK ] config.yaml: decoded as Config (kind=config)
[FAIL] invalid.json: Validation error: missing required field 'name'
```

With `--verbose`, you'll also see the formatted content:

```
[ OK ] schema.json: decoded as MySchema (kind=schema)
MySchema:
  name: example-schema
  version: 1.0.0
  fields:
  - name: id
    type: string
    required: ✓
  - name: count
    type: integer
    default: 42
```
 

## Development

Install in development mode:

```bash
pip install -e ".[test]"
```

## License

MIT
