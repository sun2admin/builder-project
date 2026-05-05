"""Schema validation for build.json.

Loads the JSON Schema bundled at schema/build-input.schema.json and validates
input files. Returns process-style int codes (0=ok, non-zero=error) for CLI use.
"""

from __future__ import annotations

import json
import sys
from importlib import resources
from pathlib import Path

import jsonschema


def _load_schema() -> dict:
    with resources.files("build_stack.schema").joinpath("build-input.schema.json").open() as f:
        return json.load(f)


def validate_build_json(path: Path) -> int:
    if not path.exists():
        print(f"build-stack: {path} not found", file=sys.stderr)
        return 2

    try:
        with path.open() as f:
            doc = json.load(f)
    except json.JSONDecodeError as e:
        print(f"build-stack: {path} is not valid JSON: {e}", file=sys.stderr)
        return 2

    schema = _load_schema()
    try:
        jsonschema.validate(doc, schema)
    except jsonschema.ValidationError as e:
        print(f"build-stack: {path} fails schema validation:\n  {e.message}", file=sys.stderr)
        return 3

    print(f"build-stack: {path} ok", file=sys.stderr)
    return 0
