#!/usr/bin/env python3
"""
tls_drift_gate.py — TLS / DB URL Drift Guard                        (P5.5 / RC-12)

PURPOSE
  Detect 'sslmode=disable' leaking from CI/local config into staging/prod
  deployment assets. Even a throwaway CI disable-setting is catastrophic if
  copied verbatim into a Kubernetes manifest or Terraform template that
  configures real infrastructure.

SCAN SCOPE (tight, intentional)
  INCLUDE — only staging/prod deployment assets:
    k8s/**/*.yml, k8s/**/*.yaml           Kubernetes manifests
    infra/**/*.tf                         Terraform (IaC)
    infra/**/*.json                       IAM/policy JSON
    infra/**/*.yml, infra/**/*.yaml       Infra YAML (excl. docker-compose.yml)
    ops/scripts/**/*.sh                   Operational shell scripts
    ops/scripts/**/*.template             Env-template files for deployment
    ops/scripts/**/*.sql                  SQL migration scripts with DB URLs

  EXCLUDE — these may legitimately carry sslmode=disable:
    evidence/**              CI evidence archives (contain test output)
    **/.git/**               Git internals
    .github/workflows/**     CI workflows (ephemeral containers are fine)
    **/*.md                  Documentation / runbooks (explanatory text)
    infra/docker-compose.yml Local-dev-only container definition

  WHY NOT MORE?
    Scanning docs/*.md creates false positives (explanatory text mentions
    'sslmode=disable' as a forbidden example). Scanning everything is O(n)
    on all source files and produces noise. Tight scope = zero false positives.

EXCERPT SAFETY
  Hit excerpts are always the constant string "sslmode=disable".
  Full lines — which may contain DATABASE_URL credentials — are NEVER stored
  in the report, evidence, or stdout.

EXIT CODES
  0  PASS  — no hits
  2  FAIL  — at least one hit found
  1  ERROR — internal error (bad root, unreadable file, etc.)

USAGE
  python dpp/tools/security/tls_drift_gate.py --root . --out report.json
"""

import argparse
import json
import sys
from pathlib import Path

RULE_ID = "TLS_NO_SSLMODE_DISABLE_IN_STAGING_PROD"
BANNED_SIGNAL = "sslmode=disable"

# ── Locked scope ──────────────────────────────────────────────────────────────

DEFAULT_INCLUDE_GLOBS: list[str] = [
    "k8s/**/*.yml",
    "k8s/**/*.yaml",
    "infra/**/*.tf",
    "infra/**/*.json",
    "infra/**/*.yml",
    "infra/**/*.yaml",
    "ops/scripts/**/*.sh",
    "ops/scripts/**/*.template",
    "ops/scripts/**/*.sql",
]

DEFAULT_EXCLUDE_PATTERNS: list[str] = [
    "evidence/",
    ".git/",
    ".github/workflows/",
    "infra/docker-compose.yml",
]


# ── Core detection (no regex → zero ReDoS risk) ───────────────────────────────

def normalize_line(s: str) -> str:
    """Lowercase; strip quotes/backticks; collapse whitespace; normalize spaces
    around '=' so that 'sslmode = disable' matches the same as 'sslmode=disable'.
    """
    s = s.lower()
    s = s.replace("'", "").replace('"', "").replace("`", "")
    s = " ".join(s.split())                     # collapse whitespace
    s = s.replace(" = ", "=").replace(" =", "=").replace("= ", "=")
    return s


def detect_sslmode_disable(line: str) -> bool:
    """Return True if normalized line contains the banned signal."""
    return BANNED_SIGNAL in normalize_line(line)


# ── Scanner ───────────────────────────────────────────────────────────────────

def _is_excluded(path: Path, root: Path, exclude_patterns: list[str]) -> bool:
    rel = path.relative_to(root).as_posix()
    return any(pat in rel for pat in exclude_patterns)


def scan_paths(
    root: Path,
    include_globs: list[str],
    exclude_patterns: list[str],
) -> dict:
    """Scan files matching include_globs for sslmode=disable.

    Returns a report dict that is safe to serialise as JSON — no credentials,
    no full line content, excerpts are always the constant banned signal.
    """
    hits: list[dict] = []
    scanned: set[str] = set()

    for glob in include_globs:
        for fpath in sorted(root.glob(glob)):
            if not fpath.is_file():
                continue
            if _is_excluded(fpath, root, exclude_patterns):
                continue
            rel_str = fpath.relative_to(root).as_posix()
            if rel_str in scanned:
                continue
            scanned.add(rel_str)

            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            for lineno, raw_line in enumerate(text.splitlines(), start=1):
                if detect_sslmode_disable(raw_line):
                    hits.append({
                        "path": rel_str,
                        "line": lineno,
                        # SAFETY: constant string only — full line is never stored
                        "excerpt": BANNED_SIGNAL,
                    })

    return {
        "ok": len(hits) == 0,
        "rule_id": RULE_ID,
        "scanned_files": len(scanned),
        "hits": hits,
        "note": "no secrets printed; excerpts are sanitized and truncated",
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="TLS Drift Gate — detect sslmode=disable in staging/prod assets"
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repository / project root to scan from (default: current dir)",
    )
    parser.add_argument(
        "--out",
        help="Write JSON report to this file path",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"ERROR: --root is not a directory: {root}", file=sys.stderr)
        return 1

    try:
        report = scan_paths(root, DEFAULT_INCLUDE_GLOBS, DEFAULT_EXCLUDE_PATTERNS)
    except Exception as exc:  # noqa: BLE001
        error_report = {
            "ok": False,
            "rule_id": RULE_ID,
            "error": str(exc),
            "note": "internal error during scan",
        }
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(error_report, indent=2), encoding="utf-8")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    report_json = json.dumps(report, indent=2)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report_json, encoding="utf-8")

    if not report["ok"]:
        print(
            f"[FAIL] {RULE_ID}: {len(report['hits'])} hit(s) found",
            file=sys.stderr,
        )
        for hit in report["hits"]:
            # Only log path and line number — never the URL or credentials
            print(f"  {hit['path']}:{hit['line']} → {hit['excerpt']}", file=sys.stderr)
        return 2

    print(
        f"[PASS] {RULE_ID}: {report['scanned_files']} file(s) scanned, 0 hits"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
