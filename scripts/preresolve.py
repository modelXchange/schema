#!/usr/bin/env python3
"""
preresolve.py — Generate pre-resolved (flat) variants of composed schemas.

For each schema that uses allOf with $ref entries pointing to locally registered
sub-schemas, this script resolves the refs and merges all sub-schema properties
(and required lists) into a single top-level properties object. The flat variant
is written alongside the source with "-flat" inserted before ".schema.json".

  modelcard.schema.json        -> modelcard-flat.schema.json

Usage:
    # Generate flat schemas (run before committing or registering)
    python scripts/preresolve.py [registered/]

    # Check that committed flat schemas are up to date (used in CI)
    python scripts/preresolve.py --check [registered/]
"""

import argparse
import json
import sys
from pathlib import Path

SYNAPSE_BASE = "https://repo-prod.prod.sagebase.org/repo/v1/schema/type/registered/"
FLAT_SUFFIX = "-flat"  # used in filenames only
FLAT_ID_SUFFIX = "flat"  # appended directly to the id segment (no hyphen) to stay within {org}-{id} format


def build_index(directory: Path) -> dict[str, dict]:
    """Index all schemas in directory by both full $id URI and short ID."""
    index: dict[str, dict] = {}
    for path in sorted(directory.rglob("*.schema.json")):
        data = json.loads(path.read_text())
        schema_id = data.get("$id", "")
        if not schema_id:
            continue
        index[schema_id] = data
        short_id = schema_id.removeprefix(SYNAPSE_BASE)
        if short_id != schema_id:
            index[short_id] = data
    return index


def preresolve(source: dict, index: dict[str, dict]) -> dict | None:
    """
    Resolve allOf/$ref entries and return a new flat schema, or None if source
    has no allOf to expand.
    """
    all_of = source.get("allOf")
    if not all_of:
        return None

    merged_properties: dict = {}
    merged_required: list = []
    seen_required: set = set()
    missing: list[str] = []

    for entry in all_of:
        ref = entry.get("$ref")
        if not ref:
            continue
        sub = index.get(ref)
        if sub is None:
            missing.append(ref)
            continue
        merged_properties.update(sub.get("properties", {}))
        for field in sub.get("required", []):
            if field not in seen_required:
                merged_required.append(field)
                seen_required.add(field)

    if missing:
        print(f"  WARNING: unresolved $refs (skipped): {missing}", file=sys.stderr)

    original_id = source.get("$id", "")
    short_original = original_id.removeprefix(SYNAPSE_BASE)

    flat: dict = {}
    if "$schema" in source:
        flat["$schema"] = source["$schema"]
    flat["$id"] = SYNAPSE_BASE + short_original + FLAT_ID_SUFFIX
    flat["title"] = source.get("title", "") + " (Flat)"
    flat["description"] = (
        f"Pre-resolved variant of {short_original}. "
        "All sub-schema properties are merged into a single top-level properties object "
        "for compatibility with tools that do not resolve $ref entries in allOf "
        "(e.g. the Synapse Python client and Synapse UI). "
        "Regenerate with: python scripts/preresolve.py"
    )
    flat["type"] = "object"
    flat["properties"] = merged_properties
    if merged_required:
        flat["required"] = merged_required

    return flat


def flat_path(source: Path) -> Path:
    """modelcard.schema.json -> modelcard-flat.schema.json"""
    name = source.name
    if name.endswith(".schema.json"):
        stem = name[: -len(".schema.json")]
        return source.with_name(f"{stem}{FLAT_SUFFIX}.schema.json")
    return source.with_suffix(f"{FLAT_SUFFIX}.json")


def process_file(source: Path, index: dict[str, dict], *, check: bool) -> bool:
    data = json.loads(source.read_text())
    flat = preresolve(data, index)
    if flat is None:
        return True  # not a composed schema, nothing to do

    out_path = flat_path(source)
    content = json.dumps(flat, indent=2) + "\n"

    if check:
        if not out_path.exists():
            print(f"MISSING:      {out_path.name}  (run preresolve.py)")
            return False
        if out_path.read_text() != content:
            print(f"OUT OF SYNC:  {out_path.name}  (run preresolve.py)")
            return False
        print(f"OK:           {out_path.name}")
        return True

    out_path.write_text(content)
    print(f"Written:      {out_path.name}")
    return True


def expand_paths(raw: list[Path]) -> list[Path]:
    result: list[Path] = []
    for p in raw:
        if p.is_dir():
            result.extend(sorted(p.rglob("*.schema.json")))
        else:
            result.append(p)
    return result


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify that flat schemas are up to date instead of writing them.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["registered"],
        help="Schema files or directories to process (default: registered/).",
    )
    args = parser.parse_args(argv)

    all_paths = expand_paths([Path(p) for p in args.paths])
    if not all_paths:
        print("No schema files found.")
        return 1

    # Build a shared index from the enclosing directory of the first path
    roots = {p.parent for p in all_paths if p.is_file()}
    index: dict[str, dict] = {}
    for root in roots:
        index.update(build_index(root))

    # Only process composed schemas; skip files that are themselves flat variants
    composed = [p for p in all_paths if p.is_file() and FLAT_SUFFIX not in p.name]

    all_ok = True
    for path in composed:
        ok = process_file(path, index, check=args.check)
        all_ok = all_ok and ok

    if args.check and not all_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
