#!/usr/bin/env python3

import json
import os
import sys
import time
from pathlib import Path

import synapseclient


def register_schema(path: Path) -> bool:
    """Dry-run register schema against Synapse API for validation."""
    print(f"\nValidating via dry-run registration: {path.name}")
    try:
        data = json.loads(path.read_text())
        body = json.dumps({"schema": data, "dryRun": True})

        syn = synapseclient.Synapse()
        auth_token = os.environ.get("SYNAPSE_AUTH_TOKEN")
        if not auth_token:
            raise ValueError("SYNAPSE_AUTH_TOKEN environment variable is required for validation")
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
        print(f"Exception validating {path.name}: {e}")
        return False


def main(argv: list[str]) -> int:
    args = [Path(arg) for arg in argv] or [Path("synapsemod.schema.json")]
    all_ok = True

    for path in args:
        if not path.exists():
            print(f"Missing schema file: {path}")
            all_ok = False
            continue
        all_ok = register_schema(path) and all_ok

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
