"""Minimal JSON Schema (draft 2020-12 subset) validator — Python stdlib only.

Supported keywords: type, enum, const, required, properties, additionalProperties,
items, minItems, maxItems, uniqueItems, minimum, maximum, exclusiveMinimum,
exclusiveMaximum, minLength, maxLength, pattern, $ref (local "#/$defs/..."),
allOf, anyOf, oneOf, not.

Why: the editor machine may not have `jsonschema` installed and the skill pack must
not add heavy dependencies. If `jsonschema` IS installed, tests cross-check with it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, List

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
}


def _resolve(root: dict, ref: str) -> dict:
    if not ref.startswith("#/"):
        raise ValueError(f"Only local $ref supported, got {ref!r}")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    return node


def _validate(inst: Any, schema: Any, root: dict, path: str, errors: List[str]) -> None:
    if schema is True:
        return
    if schema is False:
        errors.append(f"{path}: not allowed")
        return
    if "$ref" in schema:
        _validate(inst, _resolve(root, schema["$ref"]), root, path, errors)
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_TYPES[x](inst) for x in types):
            errors.append(f"{path}: expected type {t}, got {type(inst).__name__}")
            return
    if "const" in schema and inst != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and inst not in schema["enum"]:
        errors.append(f"{path}: {inst!r} not in enum {schema['enum']}")
    if isinstance(inst, (int, float)) and not isinstance(inst, bool):
        if "minimum" in schema and inst < schema["minimum"]:
            errors.append(f"{path}: {inst} < minimum {schema['minimum']}")
        if "maximum" in schema and inst > schema["maximum"]:
            errors.append(f"{path}: {inst} > maximum {schema['maximum']}")
        if "exclusiveMinimum" in schema and inst <= schema["exclusiveMinimum"]:
            errors.append(f"{path}: {inst} <= exclusiveMinimum {schema['exclusiveMinimum']}")
        if "exclusiveMaximum" in schema and inst >= schema["exclusiveMaximum"]:
            errors.append(f"{path}: {inst} >= exclusiveMaximum {schema['exclusiveMaximum']}")
    if isinstance(inst, str):
        if "minLength" in schema and len(inst) < schema["minLength"]:
            errors.append(f"{path}: shorter than {schema['minLength']}")
        if "maxLength" in schema and len(inst) > schema["maxLength"]:
            errors.append(f"{path}: longer than {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], inst):
            errors.append(f"{path}: does not match pattern {schema['pattern']}")
    if isinstance(inst, list):
        if "minItems" in schema and len(inst) < schema["minItems"]:
            errors.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(inst) > schema["maxItems"]:
            errors.append(f"{path}: more than {schema['maxItems']} items")
        if schema.get("uniqueItems"):
            seen = [json.dumps(x, sort_keys=True) for x in inst]
            if len(seen) != len(set(seen)):
                errors.append(f"{path}: items not unique")
        if "items" in schema:
            for i, item in enumerate(inst):
                _validate(item, schema["items"], root, f"{path}[{i}]", errors)
    if isinstance(inst, dict):
        for key in schema.get("required", []):
            if key not in inst:
                errors.append(f"{path}: missing required '{key}'")
        props = schema.get("properties", {})
        for key, val in inst.items():
            if key in props:
                _validate(val, props[key], root, f"{path}.{key}", errors)
            else:
                ap = schema.get("additionalProperties", True)
                if ap is False:
                    errors.append(f"{path}: unexpected property '{key}'")
                elif isinstance(ap, dict):
                    _validate(val, ap, root, f"{path}.{key}", errors)
    for sub in schema.get("allOf", []):
        _validate(inst, sub, root, path, errors)
    if "anyOf" in schema:
        if not any(not _errs(inst, s, root, path) for s in schema["anyOf"]):
            errors.append(f"{path}: does not match anyOf")
    if "oneOf" in schema:
        n = sum(1 for s in schema["oneOf"] if not _errs(inst, s, root, path))
        if n != 1:
            errors.append(f"{path}: matches {n} oneOf branches (need exactly 1)")
    if "not" in schema and not _errs(inst, schema["not"], root, path):
        errors.append(f"{path}: must not match 'not' schema")


def _errs(inst, schema, root, path) -> List[str]:
    out: List[str] = []
    _validate(inst, schema, root, path, out)
    return out


def validate(instance: Any, schema: dict) -> List[str]:
    """Return a list of error strings (empty list == valid)."""
    return _errs(instance, schema, schema, "$")


def load_json(path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_file(instance_path, schema_path) -> List[str]:
    return validate(load_json(instance_path), load_json(schema_path))


if __name__ == "__main__":  # python sae_schema.py instance.json schema.json
    import sys

    errs = validate_file(sys.argv[1], sys.argv[2])
    print("VALID" if not errs else "INVALID\n" + "\n".join(errs))
    sys.exit(1 if errs else 0)
