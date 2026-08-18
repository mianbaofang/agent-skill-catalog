"""Fetch and cache bounded public GitHub repository preview images."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import re
import tempfile
import time
from http.client import HTTPException, IncompleteRead
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.error import HTTPError
from urllib.parse import quote, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


SCRIPT_INTERFACE = "internal-module"
SCRIPT_INTERFACE_REASON = "Imported by build_catalog.py to isolate bounded GitHub preview retrieval."

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
IMAGE_SIGNATURES = {
    ".png": b"\x89PNG\r\n\x1a\n",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".gif": b"GIF8",
    ".webp": b"RIFF",
}
GITHUB_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+$")
GITHUB_IMAGE_HOSTS = {
    "github.com",
    "www.github.com",
    "raw.githubusercontent.com",
    "user-images.githubusercontent.com",
    "private-user-images.githubusercontent.com",
    "github-production-user-asset-6210df.s3.amazonaws.com",
    "opengraph.githubassets.com",
}
PREFERRED_IMAGE_TERMS = ("screenshot", "demo", "preview", "cover", "hero", "banner", "product", "gallery")
EXCLUDED_IMAGE_TERMS = ("qr", "qrcode", "wechat", "wx", "pay", "donate", "sponsor", "badge", "icon", "avatar")
CACHE_VERSION = "preview-v2"
MISSING_CACHE_STATUS = "github-missing"


class AllowedRedirectHandler(HTTPRedirectHandler):
    def __init__(self, allowed_hosts: set[str]) -> None:
        super().__init__()
        self.allowed_hosts = {host.lower() for host in allowed_hosts}

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        if parsed.scheme != "https" or parsed.netloc.lower() not in self.allowed_hosts:
            raise HTTPError(newurl, code, "redirect host is not allowed", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_allowed(request: Request, timeout: int, allowed_hosts: set[str]):
    return build_opener(AllowedRedirectHandler(allowed_hosts)).open(request, timeout=timeout)


def replace_with_retry(temporary: Path, path: Path) -> None:
    for attempt in range(10):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(min(0.1 * (attempt + 1), 1.0))


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False, suffix=".tmp") as handle:
        handle.write(content)
        temporary = Path(handle.name)
    replace_with_retry(temporary, path)


def github_repository(url: str) -> Tuple[str, str]:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        return "", ""
    parts = [part for part in parsed.path.split("/") if part]
    # Only a repository root is a valid preview source.  Paths such as
    # /tree, /blob, /archive, /issues, and /pull are references inside a
    # repository, not repository URLs themselves.
    if len(parts) != 2:
        return "", ""
    owner, repository = parts[0], parts[1].removesuffix(".git")
    if not GITHUB_REPOSITORY.fullmatch(owner) or not GITHUB_REPOSITORY.fullmatch(repository):
        return "", ""
    return owner, repository


def is_allowed_github_image_url(url: str) -> bool:
    parsed = urlparse(str(url or "").strip())
    return parsed.scheme == "https" and parsed.netloc.lower() in GITHUB_IMAGE_HOSTS


def image_extension_for_content_type(content_type: str, url: str) -> str:
    normalized = str(content_type or "").split(";", 1)[0].strip().lower()
    by_type = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/svg+xml": ".svg",
    }
    if normalized in by_type:
        return by_type[normalized]
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in IMAGE_EXTENSIONS else ""


def github_cache_key(repository_url: str) -> str:
    value = f"{CACHE_VERSION}:{repository_url.rstrip('/')}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def github_cache_status(path: Path) -> str:
    if ".github-repository." in path.name:
        return "github-repository"
    if ".github-social-preview." in path.name:
        return "github-social-preview"
    return ""


def github_cache_path(cache_dir: Path, cache_key: str, status: str, suffix: str) -> Path:
    return cache_dir / f"{cache_key}.{status}{suffix}"


def github_missing_cache_path(cache_dir: Path, cache_key: str) -> Path:
    return cache_dir / f"{cache_key}.{MISSING_CACHE_STATUS}.json"


def github_missing_cache_is_fresh(path: Path, ttl_seconds: int) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        fetched_at = float(payload.get("fetched_at", 0))
        return bool(fetched_at and (ttl_seconds == 0 or time.time() - fetched_at <= ttl_seconds))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return False


def image_data_uri_from_bytes(body: bytes, suffix: str, max_bytes: Optional[int] = None) -> str:
    if max_bytes and len(body) > max_bytes:
        return ""
    suffix = suffix.lower()
    if suffix == ".svg":
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            return ""
        if "<svg" not in text[:1024].lower():
            return ""
        return "data:image/svg+xml;utf8," + quote(text, safe="")
    signature = IMAGE_SIGNATURES.get(suffix)
    if not signature or not body.startswith(signature) or len(body) < len(signature):
        return ""
    if suffix == ".webp" and body[8:12] != b"WEBP":
        return ""
    media_type = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}[suffix]
    return f"data:{media_type};base64," + base64.b64encode(body).decode("ascii")


def image_data_uri(path: Path, max_bytes: Optional[int] = None) -> str:
    try:
        body = path.read_bytes()
    except OSError:
        return ""
    return image_data_uri_from_bytes(body, path.suffix.lower(), max_bytes)


def image_dimensions(body: bytes, suffix: str) -> Tuple[int, int]:
    suffix = suffix.lower()
    if suffix == ".png" and len(body) >= 24 and body.startswith(IMAGE_SIGNATURES[".png"]):
        return int.from_bytes(body[16:20], "big"), int.from_bytes(body[20:24], "big")
    if suffix == ".gif" and len(body) >= 10 and body.startswith(b"GIF8"):
        return int.from_bytes(body[6:8], "little"), int.from_bytes(body[8:10], "little")
    if suffix in {".jpg", ".jpeg"} and body.startswith(b"\xff\xd8"):
        offset = 2
        while offset + 9 < len(body):
            if body[offset] != 0xFF:
                offset += 1
                continue
            marker = body[offset + 1]
            offset += 2
            if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
                continue
            if offset + 2 > len(body):
                break
            length = int.from_bytes(body[offset:offset + 2], "big")
            if length < 2 or offset + length > len(body):
                break
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                return int.from_bytes(body[offset + 5:offset + 7], "big"), int.from_bytes(body[offset + 3:offset + 5], "big")
            offset += length
    if suffix == ".webp" and len(body) >= 30 and body.startswith(b"RIFF") and body[8:12] == b"WEBP":
        chunk = body[12:16]
        if chunk == b"VP8X":
            return int.from_bytes(body[24:27], "little") + 1, int.from_bytes(body[27:30], "little") + 1
        if chunk == b"VP8 " and body[23:26] == b"\x9d\x01\x2a":
            return int.from_bytes(body[26:28], "little") & 0x3FFF, int.from_bytes(body[28:30], "little") & 0x3FFF
        if chunk == b"VP8L" and body[20] == 0x2F:
            bits = int.from_bytes(body[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    return 0, 0


def image_meets_minimum(body: bytes, suffix: str, image_config: Dict[str, Any]) -> bool:
    minimum_width = max(0, int(image_config.get("github_min_image_width", 0) or 0))
    minimum_height = max(0, int(image_config.get("github_min_image_height", 0) or 0))
    if not minimum_width and not minimum_height:
        return True
    width, height = image_dimensions(body, suffix)
    return width >= minimum_width and height >= minimum_height


def github_image_candidate_score(url: str, index: int = 0) -> Optional[int]:
    normalized = html.unescape(str(url or "")).casefold()
    tokens = re.split(r"[^a-z0-9]+", normalized)
    if any(term in tokens for term in EXCLUDED_IMAGE_TERMS):
        return None
    score = sum(20 for term in PREFERRED_IMAGE_TERMS if term in tokens)
    return score - index


def github_readme_image_urls(repository_url: str, image_config: Dict[str, Any]) -> List[str]:
    owner, repository = github_repository(repository_url)
    if not owner or not repository:
        return []
    timeout = max(1, int(image_config.get("github_request_timeout_seconds", 15) or 15))
    limit = max(1, int(image_config.get("github_max_page_bytes", 1024 * 1024) or 1024 * 1024))
    request = Request(
        f"https://github.com/{owner}/{repository}",
        headers={"Accept": "text/html", "User-Agent": "agent-skill-catalog/0.3"},
    )
    try:
        with open_allowed(request, timeout, {"github.com", "www.github.com"}) as response:
            final_url = response.geturl()
            if github_repository(final_url) != (owner, repository):
                return []
            try:
                body = response.read(limit + 1)
            except IncompleteRead as exc:
                body = exc.partial
    except (OSError, HTTPException):
        return []
    if len(body) > limit:
        return []
    page = body.decode("utf-8", errors="replace")
    urls: List[str] = []
    for raw in re.findall(r'<(?:img|source)\b[^>]+\bsrc=["\']([^"\']+)', page, flags=re.I):
        candidate = html.unescape(urljoin(final_url, raw.strip()))
        if is_allowed_github_image_url(candidate) and candidate not in urls:
            urls.append(candidate)
    ranked = []
    for index, candidate in enumerate(urls):
        score = github_image_candidate_score(candidate, index)
        if score is not None:
            ranked.append((score, index, candidate))
    ranked.sort(key=lambda value: (-value[0], value[1]))
    return [candidate for _, _, candidate in ranked[: max(1, int(image_config.get("github_image_candidate_limit", 8) or 8))]]


def fetch_github_image(url: str, image_config: Dict[str, Any]) -> Tuple[bytes, str]:
    if not is_allowed_github_image_url(url):
        return b"", ""
    timeout = max(1, int(image_config.get("github_request_timeout_seconds", 15) or 15))
    limit = max(1, int(image_config.get("github_max_download_bytes", 2 * 1024 * 1024) or 2 * 1024 * 1024))
    request = Request(url, headers={"Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8", "User-Agent": "agent-skill-catalog/0.3"})
    try:
        with open_allowed(request, timeout, GITHUB_IMAGE_HOSTS) as response:
            final_url = response.geturl()
            if not is_allowed_github_image_url(final_url):
                return b"", ""
            body = response.read(limit + 1)
            content_type = response.headers.get("Content-Type", "")
    except (OSError, HTTPException):
        return b"", ""
    suffix = image_extension_for_content_type(content_type, final_url)
    if len(body) > limit or not suffix or suffix == ".svg":
        return b"", ""
    return body, suffix


def github_preview_image(
    repository_url: str,
    image_config: Dict[str, Any],
    cache_dir: Optional[Path],
    fetch_readme_urls: Callable[..., List[str]] = github_readme_image_urls,
    fetch_image: Callable[..., Tuple[bytes, str]] = fetch_github_image,
) -> Dict[str, Any]:
    if not image_config.get("github_repository_previews", True) or not github_repository(repository_url):
        return {}
    cache_key = github_cache_key(repository_url)
    ttl_seconds = max(0, int(float(image_config.get("github_image_cache_ttl_hours", 168) or 0) * 3600))
    max_bytes = int(image_config.get("max_embedded_bytes", 512 * 1024) or 0)
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        for cached in sorted(cache_dir.glob(cache_key + ".*")):
            cached_status = github_cache_status(cached)
            if not cached_status:
                continue
            try:
                cached_body = cached.read_bytes()
            except OSError:
                continue
            if not image_meets_minimum(cached_body, cached.suffix, image_config):
                continue
            data_uri = image_data_uri_from_bytes(cached_body, cached.suffix, max_bytes)
            if data_uri and (ttl_seconds == 0 or time.time() - cached.stat().st_mtime <= ttl_seconds):
                return {"status": cached_status, "source": "github-cache", "value": data_uri, "repository": repository_url, "missing_evidence": False}
        missing_cache = github_missing_cache_path(cache_dir, cache_key)
        if missing_cache.is_file() and github_missing_cache_is_fresh(missing_cache, ttl_seconds):
            return {}

    for candidate in fetch_readme_urls(repository_url, image_config):
        body, suffix = fetch_image(candidate, image_config)
        if body and not image_meets_minimum(body, suffix, image_config):
            continue
        data_uri = image_data_uri_from_bytes(body, suffix, max_bytes) if body else ""
        if not data_uri:
            continue
        if cache_dir:
            atomic_write_bytes(github_cache_path(cache_dir, cache_key, "github-repository", suffix), body)
        return {"status": "github-repository", "source": "github-readme", "value": data_uri, "repository": repository_url, "remote_source": candidate, "missing_evidence": False}

    owner, repository = github_repository(repository_url)
    if not owner or not repository:
        return {}
    fallback_url = f"https://opengraph.githubassets.com/{cache_key}/{owner}/{repository}"
    body, suffix = fetch_image(fallback_url, image_config)
    if body and not image_meets_minimum(body, suffix, image_config):
        return {}
    data_uri = image_data_uri_from_bytes(body, suffix, max_bytes) if body else ""
    if not data_uri:
        if cache_dir:
            atomic_write_bytes(
                github_missing_cache_path(cache_dir, cache_key),
                json.dumps({"fetched_at": time.time(), "repository": repository_url}, ensure_ascii=False).encode("utf-8"),
            )
        return {}
    if cache_dir:
        atomic_write_bytes(github_cache_path(cache_dir, cache_key, "github-social-preview", suffix), body)
    return {"status": "github-social-preview", "source": "github-opengraph", "value": data_uri, "repository": repository_url, "remote_source": fallback_url, "missing_evidence": False}
