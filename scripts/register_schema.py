#!/usr/bin/env python3

import argparse
import json
import os
import sys
import time
from pathlib import Path

import synapseclient


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

    paths = expand_paths([Path(arg) for arg in args.paths])
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
