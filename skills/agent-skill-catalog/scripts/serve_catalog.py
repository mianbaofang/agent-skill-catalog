#!/usr/bin/env python3
"""Serve one generated Agent Skill Catalog and allow a bounded same-origin refresh."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
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
ALLOWED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}
MAX_UPLOAD_BYTES = 2 * 1024 * 1024


def config_root_specs(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    roots = payload.get("roots", []) if isinstance(payload, dict) else []
    values: list[dict[str, str]] = []
    source = roots if isinstance(roots, list) and roots else ["."]
    for index, entry in enumerate(source):
        if isinstance(entry, dict):
            raw = entry.get("path") or "."
            label = str(entry.get("label") or entry.get("source") or f"Root {index + 1}")
            kind = str(entry.get("kind") or "skill")
            allow_delete = bool(entry.get("allow_delete", False))
        else:
            raw = entry
            label = f"Root {index + 1}"
            kind = "skill"
            allow_delete = False
        values.append({
            "path": str(Path(os.path.expandvars(os.path.expanduser(str(raw)))).resolve()),
            "label": label,
            "kind": kind,
            "allow_delete": allow_delete,
        })
    return values


def cli_root_specs(root_paths: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "path": str(Path(value).expanduser().resolve()),
            "label": f"Root {index + 1}",
            "kind": "skill",
            "allow_delete": False,
        }
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
    parser.add_argument(
        "--require-complete-descriptions",
        action="store_true",
        help="Fail refreshes while the Agent-owned Chinese description queue is incomplete",
    )
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


def output_curation_path(output_dir: Path) -> Path:
    return output_dir / "catalog-curation.json"


def load_output_curation(output_dir: Path) -> dict[str, Any]:
    path = output_curation_path(output_dir)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    for key, fallback in (
        ("description_overrides", {}),
        ("category_overrides", []),
        ("github_overrides", {}),
        ("family_overrides", {}),
        ("image_overrides", {}),
    ):
        if not isinstance(payload.get(key), type(fallback)):
            payload[key] = fallback
    return payload


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def remove_output_image_override(output_dir: Path, relative_path: str) -> None:
    curation = load_output_curation(output_dir)
    image_path = str(curation["image_overrides"].pop(relative_path, "") or "")
    if image_path:
        candidate = Path(image_path)
        curated_root = (output_dir / "curated-images").resolve()
        try:
            candidate.resolve().relative_to(curated_root)
        except ValueError:
            pass
        else:
            candidate.unlink(missing_ok=True)
    atomic_write_json(output_curation_path(output_dir), curation)


def image_extension(content_type: str) -> str:
    return ALLOWED_IMAGE_TYPES.get(str(content_type or "").split(";", 1)[0].strip().lower(), "")


def valid_image_data(body: bytes, suffix: str) -> bool:
    if suffix == ".png":
        return body.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix == ".jpg":
        return body.startswith(b"\xff\xd8\xff")
    if suffix == ".gif":
        return body.startswith(b"GIF8")
    if suffix == ".webp":
        return body.startswith(b"RIFF") and body[8:12] == b"WEBP"
    if suffix == ".svg":
        return b"<svg" in body[:1024].lower()
    return False


def root_id(path: str) -> str:
    return hashlib.sha256(str(Path(path).resolve()).encode("utf-8")).hexdigest()


def root_contract_fingerprint(spec: dict[str, Any]) -> str:
    value = "\x1f".join((
        str(spec.get("path") or ""),
        str(spec.get("label") or ""),
        str(spec.get("kind") or ""),
        "1" if spec.get("allow_delete") else "0",
    ))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def is_reparse_point(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", lambda: False)
    return path.is_symlink() or bool(is_junction())


def ensure_plain_tree(target: Path, root: Path) -> None:
    current = target
    while True:
        if is_reparse_point(current):
            raise PermissionError("Skill directory contains a symlink or junction")
        if current == root:
            break
        if current.parent == current:
            raise PermissionError("Skill directory is outside its configured root")
        current = current.parent
    for current_dir, dirs, files in os.walk(target, topdown=True, followlinks=False):
        for name in [*dirs, *files]:
            if is_reparse_point(Path(current_dir) / name):
                raise PermissionError("Skill directory contains a symlink or junction")


def delete_catalog_skill(output_dir: Path, specs: list[dict[str, Any]], payload: dict[str, Any]) -> Path:
    try:
        catalog = json.loads((output_dir / "catalog.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FileNotFoundError("Current catalog cannot be read") from exc
    items = catalog.get("items", []) if isinstance(catalog, dict) else []
    item_id = str(payload.get("id") or "")
    matches = [item for item in items if isinstance(item, dict) and str(item.get("id") or "") == item_id]
    if len(matches) != 1:
        raise FileNotFoundError("Skill is not present in the current catalog")
    item = matches[0]
    name = str(item.get("name") or "")
    relative_path = str(item.get("relative_path") or "").replace("\\", "/")
    if str(payload.get("name") or "") != name or str(payload.get("confirmation") or "") != name:
        raise ValueError("Skill name confirmation does not match")
    if str(payload.get("relative_path") or "").replace("\\", "/") != relative_path:
        raise ValueError("Skill path does not match the current catalog")
    if item.get("kind") != "skill" or int(item.get("family_size", 0) or 0) != 1:
        raise PermissionError("Only an independent Skill can be deleted")
    parts = Path(relative_path).parts
    if len(parts) != 2 or parts[1].casefold() != "skill.md" or parts[0] in {"", ".", ".."}:
        raise PermissionError("Only a top-level Skill directory can be deleted")
    item_root_id = str(item.get("root_id") or "")
    candidates = [spec for spec in specs if root_id(str(spec.get("path") or "")) == item_root_id]
    if len(candidates) != 1:
        raise PermissionError("Skill root is not part of the server startup contract")
    spec = candidates[0]
    if spec.get("kind") != "skill" or not spec.get("allow_delete") or not item.get("allow_delete"):
        raise PermissionError("Deletion is disabled for this Skill root")
    root = Path(str(spec["path"])).resolve()
    target = root / parts[0]
    skill_file = target / parts[1]
    if target.parent.resolve() != root or is_reparse_point(target) or not skill_file.is_file():
        raise PermissionError("Resolved Skill directory is not a valid top-level package")
    ensure_plain_tree(target, root)
    shutil.rmtree(target)
    remove_output_image_override(output_dir, relative_path)
    return target


def make_handler(
    output_dir: Path,
    config_path: Path,
    startup_root_specs: list[dict[str, Any]],
    curation_paths: list[str],
    refresh_timeout: int,
    startup_root_source: str,
    require_complete_descriptions: bool,
):
    refresh_lock = threading.Lock()
    root_source = str(startup_root_source)
    startup_root_paths = [str(spec["path"]) for spec in startup_root_specs]

    def run_refresh() -> tuple[bool, str]:
        command = [
            sys.executable,
            str(BUILD_SCRIPT),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
            "--refresh",
        ]
        if require_complete_descriptions:
            command.append("--require-complete-descriptions")
        if root_source == "cli":
            for root_path in startup_root_paths:
                command.extend(["--root", root_path])
        for curation_path in curation_paths:
            command.extend(["--curation", curation_path])
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=refresh_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return False, "refresh timed out"
        if result.returncode != 0:
            return False, result.stderr.strip()[-1200:] or "refresh failed"
        return True, ""

    class CatalogHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(output_dir), **kwargs)

        def log_message(self, format: str, *args: Any) -> None:
            # Keep request logging local and concise.
            try:
                sys.stderr.write("[agent-skill-catalog] " + format % args + "\n")
            except OSError:
                pass

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
            route = self.path.split("?", 1)[0]
            if route == "/api/image":
                self.save_image_override()
                return
            if route == "/api/delete":
                self.delete_skill()
                return
            if route != "/api/refresh":
                self.send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "unknown endpoint"})
                return
            if not refresh_lock.acquire(blocking=False):
                self.send_json(HTTPStatus.CONFLICT, {"ok": False, "error": "refresh already running"})
                return
            try:
                ok, error = run_refresh()
            finally:
                refresh_lock.release()
            if not ok:
                self.send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": "refresh failed", "details": error},
                )
                return
            self.send_json(HTTPStatus.OK, {"ok": True, **compact_summary(output_dir)})

        def delete_skill(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0 or length > 64 * 1024 or "application/json" not in self.headers.get("Content-Type", ""):
                self.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "delete request must be a small JSON object"})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "delete request contains invalid JSON"})
                return
            if not isinstance(payload, dict):
                self.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "delete request must be a JSON object"})
                return
            if not refresh_lock.acquire(blocking=False):
                self.send_json(HTTPStatus.CONFLICT, {"ok": False, "error": "refresh already running"})
                return
            try:
                deleted = delete_catalog_skill(output_dir, startup_root_specs, payload)
                ok, error = run_refresh()
            except PermissionError as exc:
                self.send_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": str(exc)})
                return
            except ValueError as exc:
                self.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            except FileNotFoundError as exc:
                self.send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": str(exc)})
                return
            finally:
                refresh_lock.release()
            if not ok:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "Skill deleted but catalog refresh failed", "details": error})
                return
            self.send_json(HTTPStatus.OK, {"ok": True, "deleted": deleted.name, **compact_summary(output_dir)})

        def do_DELETE(self) -> None:
            if self.path.split("?", 1)[0] != "/api/image":
                self.send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "unknown endpoint"})
                return
            self.remove_image_override()

        def save_image_override(self) -> None:
            content_type = self.headers.get("Content-Type", "")
            length_text = self.headers.get("Content-Length", "0")
            try:
                length = int(length_text)
            except ValueError:
                length = 0
            suffix = image_extension(content_type)
            if not suffix or length <= 0 or length > MAX_UPLOAD_BYTES:
                self.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "upload must be a supported image no larger than 2 MiB"})
                return
            body = self.rfile.read(length)
            if len(body) != length or not valid_image_data(body, suffix):
                self.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "uploaded file is not a valid supported image"})
                return
            name = self.headers.get("X-Catalog-Skill-Name", "").strip()
            relative_path = self.headers.get("X-Catalog-Relative-Path", "").strip().replace("\\", "/")
            if not name or not relative_path or Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
                self.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "missing or invalid Skill identity"})
                return
            asset_dir = output_dir / "curated-images"
            asset_dir.mkdir(parents=True, exist_ok=True)
            key = hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:20]
            target = asset_dir / f"{key}{suffix}"
            previous = [path for path in asset_dir.glob(key + ".*") if path != target and path.suffix != ".tmp"]
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_bytes(body)
            temporary.replace(target)
            for path in previous:
                path.unlink(missing_ok=True)
            curation = load_output_curation(output_dir)
            curation["image_overrides"][relative_path] = str(target.resolve())
            atomic_write_json(output_curation_path(output_dir), curation)
            if not refresh_lock.acquire(blocking=False):
                self.send_json(HTTPStatus.CONFLICT, {"ok": False, "error": "refresh already running"})
                return
            try:
                ok, error = run_refresh()
            finally:
                refresh_lock.release()
            if not ok:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "image saved but refresh failed", "details": error})
                return
            self.send_json(HTTPStatus.OK, {"ok": True, "name": name, "relative_path": relative_path, **compact_summary(output_dir)})

        def remove_image_override(self) -> None:
            relative_path = self.headers.get("X-Catalog-Relative-Path", "").strip().replace("\\", "/")
            if not relative_path or Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
                self.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "missing or invalid Skill identity"})
                return
            remove_output_image_override(output_dir, relative_path)
            if not refresh_lock.acquire(blocking=False):
                self.send_json(HTTPStatus.CONFLICT, {"ok": False, "error": "refresh already running"})
                return
            try:
                ok, error = run_refresh()
            finally:
                refresh_lock.release()
            if not ok:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "preview override removed but refresh failed", "details": error})
                return
            self.send_json(HTTPStatus.OK, {"ok": True, "relative_path": relative_path, **compact_summary(output_dir)})

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
    effective_specs: list[dict[str, Any]]
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
    actual_root_fingerprints = [root_contract_fingerprint(spec) for spec in effective_specs]
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
            effective_specs,
            curation_paths,
            args.refresh_timeout,
            startup_root_source,
            args.require_complete_descriptions,
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
