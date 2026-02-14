#!/usr/bin/env python3
"""RC-5 API Inventory - OpenAPI Drift Detection.

Checks for drift between actual FastAPI routes and OpenAPI schema.
Enforces hidden endpoint allowlist policy (S3).

Exit codes:
  0 = PASS (no drift, all hidden endpoints approved)
  1 = FAIL (drift detected or unapproved hidden endpoints)
  2 = ERROR (env/tooling issue)
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Add API path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

try:
    from dpp_api.main import app
except ImportError as e:
    print(f"[FAIL] ERROR: Cannot import FastAPI app: {e}", file=sys.stderr)
    sys.exit(2)


def load_hidden_endpoint_allowlist() -> Set[Tuple[str, str]]:
    """Load approved hidden endpoints from allowlist file.

    Returns:
        Set of (method, path) tuples
    """
    allowlist_path = Path(__file__).parent.parent / "docs" / "rc" / "rc5" / "RC5_HIDDEN_ENDPOINT_ALLOWLIST.txt"

    if not allowlist_path.exists():
        return set()

    allowlist = set()
    with open(allowlist_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                method, path = parts
                allowlist.add((method.upper(), path))

    return allowlist


def enumerate_actual_routes() -> Tuple[Set[Tuple[str, str]], Set[Tuple[str, str]], List[Dict]]:
    """Enumerate actual FastAPI routes.

    Returns:
        (public_exposed_routes, hidden_routes, all_routes_detail)
        - public_exposed_routes: set of (method, path) for include_in_schema=True
        - hidden_routes: set of (method, path) for include_in_schema=False
        - all_routes_detail: list of dicts with full route info
    """
    public_exposed = set()
    hidden = set()
    all_routes = []

    for route in app.routes:
        if not hasattr(route, "methods"):
            continue  # Skip non-HTTP routes (e.g., Mount)

        path = route.path
        methods = route.methods or set()

        # Check include_in_schema flag (default True)
        include_in_schema = getattr(route, "include_in_schema", True)

        for method in methods:
            if method in ["HEAD", "OPTIONS"]:
                continue  # Skip automatic HEAD/OPTIONS

            route_detail = {
                "method": method,
                "path": path,
                "name": getattr(route, "name", ""),
                "include_in_schema": include_in_schema,
            }
            all_routes.append(route_detail)

            if include_in_schema:
                public_exposed.add((method, path))
            else:
                hidden.add((method, path))

    return public_exposed, hidden, all_routes


def load_openapi_routes() -> Set[Tuple[str, str]]:
    """Load routes from OpenAPI schema.

    Returns:
        Set of (method, path) tuples from OpenAPI
    """
    openapi_routes = set()

    try:
        openapi = app.openapi()
        paths = openapi.get("paths", {})

        for path, path_item in paths.items():
            for method in path_item.keys():
                if method.upper() in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
                    openapi_routes.add((method.upper(), path))

    except Exception as e:
        print(f"[WARN]  WARNING: Error loading OpenAPI schema: {e}", file=sys.stderr)

    return openapi_routes


def generate_inventory_report(
    public_exposed: Set[Tuple[str, str]],
    hidden: Set[Tuple[str, str]],
    openapi_routes: Set[Tuple[str, str]],
    allowlist: Set[Tuple[str, str]],
    approved_hidden: Set[Tuple[str, str]],
    unapproved_hidden: Set[Tuple[str, str]],
    missing_in_openapi: Set[Tuple[str, str]],
    extra_in_openapi: Set[Tuple[str, str]],
    stale_allowlist: Set[Tuple[str, str]],
) -> None:
    """Generate RC5_API_INVENTORY.md report.

    Args:
        All the computed sets from drift analysis
    """
    repo_root = Path(__file__).parent.parent
    report_path = repo_root / "docs" / "rc" / "rc5" / "RC5_API_INVENTORY.md"

    commit_hash = os.popen("git rev-parse HEAD").read().strip()[:8]
    timestamp = datetime.now(timezone.utc).isoformat()

    with open(report_path, "w") as f:
        f.write("# RC-5 API Inventory Report\n\n")
        f.write(f"**Generated At:** {timestamp}  \n")
        f.write(f"**Commit:** `{commit_hash}`  \n")
        f.write(f"**App Entrypoint:** `dpp_api.main:app`  \n")
        f.write("\n---\n\n")

        # Drift Summary
        f.write("## Drift Summary\n\n")

        drift_status = "[OK] PASS" if (not missing_in_openapi and not extra_in_openapi) else "[FAIL] FAIL"
        f.write(f"**Status:** {drift_status}  \n")
        f.write(f"**Missing in OpenAPI:** {len(missing_in_openapi)}  \n")
        f.write(f"**Extra in OpenAPI:** {len(extra_in_openapi)}  \n")
        f.write(f"**Total Public Routes:** {len(public_exposed)}  \n")
        f.write(f"**Total Hidden Routes:** {len(hidden)}  \n")
        f.write("\n")

        # Drift Details
        if missing_in_openapi:
            f.write("### [FAIL] Missing in OpenAPI (FAIL)\n\n")
            f.write("These routes are exposed but not documented in OpenAPI:\n\n")
            for method, path in sorted(missing_in_openapi):
                f.write(f"- `{method} {path}`\n")
            f.write("\n")

        if extra_in_openapi:
            f.write("### [FAIL] Extra in OpenAPI (FAIL)\n\n")
            f.write("These routes are in OpenAPI but don't exist in app:\n\n")
            for method, path in sorted(extra_in_openapi):
                f.write(f"- `{method} {path}`\n")
            f.write("\n")

        # Hidden Endpoints
        if approved_hidden or unapproved_hidden:
            f.write("## Hidden Endpoints\n\n")

        if approved_hidden:
            f.write("### [OK] Intentionally Hidden (Approved)\n\n")
            for method, path in sorted(approved_hidden):
                f.write(f"- `{method} {path}`\n")
            f.write("\n")

        if unapproved_hidden:
            f.write("### [FAIL] Unapproved Hidden Endpoints (FAIL)\n\n")
            f.write("These routes have `include_in_schema=False` but are NOT in allowlist:\n\n")
            for method, path in sorted(unapproved_hidden):
                f.write(f"- `{method} {path}`\n")
            f.write("\n**Action Required:** Add to allowlist or set `include_in_schema=True`\n\n")

        # Warnings
        if stale_allowlist:
            f.write("## [WARN]  Warnings\n\n")
            f.write("### Stale Allowlist Entries\n\n")
            f.write("These entries are in allowlist but no longer exist:\n\n")
            for method, path in sorted(stale_allowlist):
                f.write(f"- `{method} {path}`\n")
            f.write("\n")

        f.write("---\n\n")
        f.write("*Generated by RC-5 API Inventory*\n")

    print(f"[OK] Generated: {report_path}")


def main() -> int:
    """Execute API inventory check.

    Returns:
        Exit code (0=PASS, 1=FAIL, 2=ERROR)
    """
    print("=" * 80)
    print("RC-5 API INVENTORY")
    print("=" * 80)
    print()

    # 1) Load allowlist
    print("[1/4] Loading hidden endpoint allowlist...")
    allowlist = load_hidden_endpoint_allowlist()
    print(f"  Loaded {len(allowlist)} approved hidden endpoint(s)")
    print()

    # 2) Enumerate actual routes
    print("[2/4] Enumerating actual FastAPI routes...")
    public_exposed, hidden, all_routes = enumerate_actual_routes()
    print(f"  Public exposed: {len(public_exposed)}")
    print(f"  Hidden: {len(hidden)}")
    print()

    # 3) Load OpenAPI routes
    print("[3/4] Loading OpenAPI schema routes...")
    openapi_routes = load_openapi_routes()
    print(f"  OpenAPI routes: {len(openapi_routes)}")
    print()

    # 4) Drift analysis
    print("[4/4] Analyzing drift...")

    # Apply allowlist to hidden routes
    approved_hidden = hidden & allowlist
    unapproved_hidden = hidden - allowlist

    # Check for stale allowlist entries
    all_actual = public_exposed | hidden
    stale_allowlist = allowlist - all_actual

    # Drift computation
    missing_in_openapi = public_exposed - openapi_routes
    extra_in_openapi = openapi_routes - public_exposed

    # Report
    if unapproved_hidden:
        print(f"[FAIL] {len(unapproved_hidden)} unapproved hidden endpoint(s):")
        for method, path in sorted(unapproved_hidden):
            print(f"  - {method} {path}")
        print()

    if missing_in_openapi:
        print(f"[FAIL] {len(missing_in_openapi)} route(s) missing in OpenAPI:")
        for method, path in sorted(missing_in_openapi):
            print(f"  - {method} {path}")
        print()

    if extra_in_openapi:
        print(f"[FAIL] {len(extra_in_openapi)} extra route(s) in OpenAPI:")
        for method, path in sorted(extra_in_openapi):
            print(f"  - {method} {path}")
        print()

    if stale_allowlist:
        print(f"[WARNING] {len(stale_allowlist)} stale allowlist entry(ies):")
        for method, path in sorted(stale_allowlist):
            print(f"  - {method} {path}")
        print()

    # Generate report
    generate_inventory_report(
        public_exposed=public_exposed,
        hidden=hidden,
        openapi_routes=openapi_routes,
        allowlist=allowlist,
        approved_hidden=approved_hidden,
        unapproved_hidden=unapproved_hidden,
        missing_in_openapi=missing_in_openapi,
        extra_in_openapi=extra_in_openapi,
        stale_allowlist=stale_allowlist,
    )

    print()
    print("=" * 80)

    # Determine pass/fail
    has_failures = bool(unapproved_hidden or missing_in_openapi or extra_in_openapi)

    if has_failures:
        print("RC-5 API INVENTORY: FAIL")
        print("=" * 80)
        return 1
    else:
        print("RC-5 API INVENTORY: PASS")
        print("=" * 80)
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[WARN]  Interrupted by user", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"[FAIL] ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(2)
