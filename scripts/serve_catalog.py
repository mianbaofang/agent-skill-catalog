#!/usr/bin/env python3
"""Serve one generated Agent Skill Catalog and allow a bounded same-origin refresh."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = PACKAGE_ROOT / "scripts" / "build_catalog.py"
DEFAULT_CONFIG = PACKAGE_ROOT / "references" / "catalog-config.json"


def config_root_specs(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    roots = payload.get("roots", []) if isinstance(payload, dict) else []
    values: list[dict[str, str]] = []
    source = roots if isinstance(roots, list) and roots else ["."]
    for index, entry in enumerate(source):
        if isinstance(entry, dict):
            raw = entry.get("path") or "."
            label = str(entry.get("label") or entry.get("source") or f"Root {index + 1}")
            kind = str(entry.get("kind") or "skill")
        else:
            raw = entry
            label = f"Root {index + 1}"
            kind = "skill"
        values.append({
            "path": str(Path(os.path.expandvars(os.path.expanduser(str(raw)))).resolve()),
            "label": label,
            "kind": kind,
        })
    return values


def cli_root_specs(root_paths: list[str]) -> list[dict[str, str]]:
    return [
        {"path": str(Path(value).expanduser().resolve()), "label": f"Root {index + 1}", "kind": "skill"}
        for index, value in enumerate(root_paths)
    ]


def config_root_paths(path: Path) -> list[str]:
    return [spec["path"] for spec in config_root_specs(path)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve one local Agent Skill Catalog with a bounded refresh endpoint.")
    parser.add_argument("--output-dir", required=True, help="Existing catalog directory to serve")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Confirmed catalog config used for refresh")
    parser.add_argument("--root", action="append", help="Explicit skill/plugin root used at startup; repeat for multiple roots")
    parser.add_argument("--curation", action="append", default=[], help="Optional confirmed curation JSON used at startup; repeat for multiple files")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: localhost only)")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on")
    parser.add_argument("--refresh-timeout", type=int, default=300, help="Maximum seconds for one refresh")
    return parser.parse_args()


def compact_summary(output_dir: Path) -> dict[str, Any]:
    catalog_path = output_dir / "catalog.json"
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"catalog": False}
    summary = catalog.get("summary") if isinstance(catalog, dict) else {}
    return {
        "catalog": True,
        "generated_at": catalog.get("generated_at"),
        "summary": summary if isinstance(summary, dict) else {},
    }


def make_handler(
    output_dir: Path,
    config_path: Path,
    startup_root_paths: list[str],
    curation_paths: list[str],
    refresh_timeout: int,
    startup_root_source: str,
):
    refresh_lock = threading.Lock()
    root_source = str(startup_root_source)

    class CatalogHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(output_dir), **kwargs)

        def log_message(self, format: str, *args: Any) -> None:
            # Keep request logging local and concise.
            sys.stderr.write("[agent-skill-catalog] " + format % args + "\n")

        def send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path.split("?", 1)[0] == "/api/health":
                self.send_json(HTTPStatus.OK, {"ok": True, **compact_summary(output_dir)})
                return
            super().do_GET()

        def do_POST(self) -> None:
            if self.path.split("?", 1)[0] != "/api/refresh":
                self.send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "unknown endpoint"})
                return
            if not refresh_lock.acquire(blocking=False):
                self.send_json(HTTPStatus.CONFLICT, {"ok": False, "error": "refresh already running"})
                return
            try:
                command = [
                    sys.executable,
                    str(BUILD_SCRIPT),
                    "--config",
                    str(config_path),
                    "--output-dir",
                    str(output_dir),
                    "--refresh",
                ]
                if root_source == "cli":
                    for root_path in startup_root_paths:
                        command.extend(["--root", root_path])
                for curation_path in curation_paths:
                    command.extend(["--curation", curation_path])
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=refresh_timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                self.send_json(HTTPStatus.GATEWAY_TIMEOUT, {"ok": False, "error": "refresh timed out"})
                return
            finally:
                refresh_lock.release()
            if result.returncode != 0:
                self.send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": "refresh failed", "details": result.stderr.strip()[-1200:]},
                )
                return
            self.send_json(HTTPStatus.OK, {"ok": True, **compact_summary(output_dir)})

    return CatalogHandler


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve()
    root_paths = [str(Path(value).expanduser().resolve()) for value in (args.root or [])]
    curation_paths = [str(Path(value).expanduser().resolve()) for value in (args.curation or [])]
    if not output_dir.is_dir() or not (output_dir / "index.html").is_file():
        print(f"Catalog output does not exist or has no index.html: {output_dir}", file=sys.stderr)
        return 2
    if not config_path.is_file():
        print(f"Config does not exist: {config_path}", file=sys.stderr)
        return 2
    for curation_path in curation_paths:
        if not Path(curation_path).is_file():
            print(f"Curation file does not exist: {curation_path}", file=sys.stderr)
            return 2
    try:
        catalog = json.loads((output_dir / "catalog.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        catalog = {}
    refresh_policy = catalog.get("refresh_policy") if isinstance(catalog, dict) else {}
    if not isinstance(refresh_policy, dict):
        print("Catalog has no refresh policy; rebuild it before serving refreshes.", file=sys.stderr)
        return 2
    expected_curations = int(refresh_policy.get("curation_count", 0) or 0) if isinstance(refresh_policy, dict) else 0
    startup_root_source = str(refresh_policy.get("startup_root_source") or "")
    if startup_root_source not in {"cli", "config"}:
        print("Catalog has no valid startup root source; rebuild it before serving refreshes.", file=sys.stderr)
        return 2
    if startup_root_source == "config" and root_paths:
        print("Config-root catalogs must be refreshed from their startup config; do not pass --root.", file=sys.stderr)
        return 2
    if startup_root_source == "cli" and not root_paths:
        print("Refresh requires the catalog startup roots; provide --root for CLI-root builds.", file=sys.stderr)
        return 2
    effective_specs: list[dict[str, str]]
    if startup_root_source == "config":
        try:
            effective_specs = config_root_specs(config_path)
        except (OSError, json.JSONDecodeError, TypeError):
            print("Cannot resolve startup roots from config.", file=sys.stderr)
            return 2
    else:
        effective_specs = cli_root_specs(root_paths)
    effective_root_paths = [spec["path"] for spec in effective_specs]
    if len(curation_paths) != expected_curations:
        print(f"Refresh requires {expected_curations} startup curation file(s); received {len(curation_paths)}.", file=sys.stderr)
        return 2
    expected_path_fingerprints = refresh_policy.get("startup_root_path_fingerprints") if isinstance(refresh_policy, dict) else None
    if not isinstance(expected_path_fingerprints, list):
        print("Catalog has no startup root identity; rebuild it before serving refreshes.", file=sys.stderr)
        return 2
    actual_path_fingerprints = [hashlib.sha256(str(Path(value).resolve()).encode("utf-8")).hexdigest() for value in effective_root_paths]
    if actual_path_fingerprints != expected_path_fingerprints:
        print("Refresh roots must exactly match the catalog startup roots.", file=sys.stderr)
        return 2
    expected_root_fingerprints = refresh_policy.get("startup_root_fingerprints")
    if not isinstance(expected_root_fingerprints, list):
        print("Catalog has no startup root contract; rebuild it before serving refreshes.", file=sys.stderr)
        return 2
    actual_root_fingerprints = [
        hashlib.sha256("\x1f".join((spec["path"], spec["label"], spec["kind"])).encode("utf-8")).hexdigest()
        for spec in effective_specs
    ]
    if actual_root_fingerprints != expected_root_fingerprints:
        print("Refresh root labels or kinds differ from the catalog startup roots.", file=sys.stderr)
        return 2
    expected_config_fingerprint = str(refresh_policy.get("startup_config_fingerprint") or "")
    try:
        actual_config_fingerprint = hashlib.sha256(config_path.read_bytes()).hexdigest()
    except OSError:
        print(f"Config does not exist: {config_path}", file=sys.stderr)
        return 2
    if not expected_config_fingerprint or actual_config_fingerprint != expected_config_fingerprint:
        print("Refresh config differs from the catalog startup config.", file=sys.stderr)
        return 2
    expected_curation_fingerprints = refresh_policy.get("startup_curation_fingerprints")
    if not isinstance(expected_curation_fingerprints, list):
        print("Catalog has no startup curation identity; rebuild it before serving refreshes.", file=sys.stderr)
        return 2
    actual_curation_fingerprints = []
    for curation_path in curation_paths:
        try:
            actual_curation_fingerprints.append(hashlib.sha256(Path(curation_path).read_bytes()).hexdigest())
        except OSError:
            print(f"Curation file does not exist: {curation_path}", file=sys.stderr)
            return 2
    if actual_curation_fingerprints != expected_curation_fingerprints:
        print("Refresh curation files differ from the catalog startup curation.", file=sys.stderr)
        return 2
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        print("Only localhost binding is supported", file=sys.stderr)
        return 2

    server = ThreadingHTTPServer(
        (args.host, args.port),
        make_handler(
            output_dir,
            config_path,
            effective_root_paths,
            curation_paths,
            args.refresh_timeout,
            startup_root_source,
        ),
    )
    print(f"Serving Agent Skill Catalog at http://{args.host}:{args.port}/index.html")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
