#!/usr/bin/env python3

import argparse
import json
import os
import sys
import time
from collections import deque
from pathlib import Path

import synapseclient

SYNAPSE_REGISTERED_BASE = "https://repo-prod.prod.sagebase.org/repo/v1/schema/type/registered/"


def register_schema(path: Path, *, dry_run: bool) -> bool:
    """Register schema against Synapse API, optionally as a dry run."""
    action = "Validating via dry-run registration" if dry_run else "Registering"
    print(f"\n{action}: {path.name}")
    try:
        data = json.loads(path.read_text())
        body = json.dumps({"schema": data, "dryRun": dry_run})

        syn = synapseclient.Synapse()
        auth_token = os.environ.get("SYNAPSE_AUTH_TOKEN")
        if not auth_token:
            raise ValueError("SYNAPSE_AUTH_TOKEN environment variable is required for registration")
        syn.login(authToken=auth_token, silent=True)

        resp = syn.restPOST("/schema/type/create/async/start", body)
        token = resp["token"]

        status = syn.restGET(f"/asynchronous/job/{token}")
        while status["jobState"] == "PROCESSING":
            time.sleep(1)
            status = syn.restGET(f"/asynchronous/job/{token}")

        if status["jobState"] == "FAILED":
            print(f"FAILED: {path.name}: {status.get('errorMessage')}")
            return False

        print(f"OK: {path.name}")
        return True
    except Exception as e:
        print(f"Exception processing {path.name}: {e}")
        return False


def _collect_refs(obj: object) -> set[str]:
    """Recursively collect Synapse-registered $ref values (full URI or short ID) from a JSON object."""
    refs: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "$ref" and isinstance(v, str):
                refs.add(v)
            else:
                refs |= _collect_refs(v)
    elif isinstance(obj, list):
        for item in obj:
            refs |= _collect_refs(item)
    return refs


def sort_by_dependencies(paths: list[Path]) -> list[Path]:
    """Return paths in topological dependency order (dependencies first)."""
    path_data: dict[Path, dict] = {p: json.loads(p.read_text()) for p in paths}
    # Index by both full URI $id and short ID (last path segment) for ref matching
    id_to_path: dict[str, Path] = {}
    for p, d in path_data.items():
        schema_id = d.get("$id", "")
        if schema_id:
            id_to_path[schema_id] = p
            short_id = schema_id.removeprefix(SYNAPSE_REGISTERED_BASE)
            if short_id != schema_id:
                id_to_path[short_id] = p

    # dependents[A] = set of paths that depend on A (must come after A)
    dependents: dict[Path, set[Path]] = {p: set() for p in paths}
    in_degree: dict[Path, int] = {p: 0 for p in paths}

    for path, data in path_data.items():
        for ref in _collect_refs(data):
            dep = id_to_path.get(ref)
            if dep and dep != path:
                dependents[dep].add(path)
                in_degree[path] += 1

    queue: deque[Path] = deque(p for p in paths if in_degree[p] == 0)
    sorted_paths: list[Path] = []
    while queue:
        node = queue.popleft()
        sorted_paths.append(node)
        for dependent in sorted(dependents[node]):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(sorted_paths) != len(paths):
        print("WARNING: Cycle detected in schema dependencies; using original order.", file=sys.stderr)
        return paths

    return sorted_paths


def expand_paths(paths: list[Path]) -> list[Path]:
    expanded: list[Path] = []
    for path in paths:
        if path.is_dir():
            expanded.extend(sorted(p for p in path.rglob("*.json") if p.is_file()))
        else:
            expanded.append(path)
    return expanded


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Register Synapse schemas, optionally as a dry run.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate schemas with a dry-run registration request instead of storing them.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["registered"],
        help="Schema files or directories to process. Directories are searched recursively for *.json files.",
    )
    args = parser.parse_args(argv)

    paths = sort_by_dependencies(expand_paths([Path(arg) for arg in args.paths]))
    all_ok = True

    if not paths:
        print("No schema files found.")
        return 1

    for path in paths:
        if not path.exists():
            print(f"Missing schema file: {path}")
            all_ok = False
            continue
        all_ok = register_schema(path, dry_run=args.dry_run) and all_ok

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
