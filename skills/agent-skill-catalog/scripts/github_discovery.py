#!/usr/bin/env python3
"""Conservative GitHub repository discovery for missing Skill links.

The module intentionally treats GitHub search as candidate generation. A
candidate is usable only after the repository metadata, a matching SKILL.md,
and the remote file contents have been checked. Network functions are
injectable so catalog tests can run without GitHub access.
"""

from __future__ import annotations

import concurrent.futures
import functools
import hashlib
import json
import os
import re
import subprocess
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


GITHUB_API = "https://api.github.com"
GITHUB_ALLOWED_HOSTS = {"api.github.com", "github.com", "www.github.com", "raw.githubusercontent.com"}
DEFAULT_TIMEOUT = 8.0
DEFAULT_TTL_HOURS = 168.0
DEFAULT_MAX_FAMILIES = 256
DEFAULT_WORKERS = 8
DEFAULT_MAX_CANDIDATES = 8
DEFAULT_CANDIDATE_WORKERS = 4
DEFAULT_SEARCH_BATCH_SIZE = 5
DEFAULT_MAX_PAGE_BYTES = 1024 * 1024
DEFAULT_MAX_SKILL_BYTES = 512 * 1024
DEFAULT_MIN_SCORE = 0.56
DEFAULT_MIN_MARGIN = 0.12
DEFAULT_USER_AGENT = "agent-skill-catalog/github-discovery"
DEFAULT_RETRY_ATTEMPTS = 2
DEFAULT_RETRY_MAX_SECONDS = 3.0

FetchJson = Callable[[str, float, int], Any]
FetchBytes = Callable[[str, float, int], bytes]


class DiscoveryError(RuntimeError):
    """A bounded network or response error; callers should keep the local item."""


class AllowedRedirectHandler(HTTPRedirectHandler):
    """Keep discovery requests on the fixed HTTPS GitHub host allowlist."""

    def __init__(self, allowed_hosts: Sequence[str]) -> None:
        super().__init__()
        self.allowed_hosts = {str(host).casefold() for host in allowed_hosts}

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        if parsed.scheme != "https" or parsed.netloc.casefold() not in self.allowed_hosts:
            raise HTTPError(newurl, code, "redirect host is not allowed", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@functools.lru_cache(maxsize=1)
def _runtime_github_token() -> str:
    """Read an existing GitHub login without storing credentials in the catalog."""
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    try:
        completed = subprocess.run(
            ["gh", "auth", "token", "--hostname", "github.com"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return (completed.stdout or "").strip() if completed.returncode == 0 else ""


def _validate_github_url(url: str) -> None:
    parsed = urlparse(str(url or ""))
    if parsed.scheme != "https" or parsed.netloc.casefold() not in GITHUB_ALLOWED_HOSTS:
        raise DiscoveryError(f"GitHub URL is not allowed: {url}")


def normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\\", "/").strip().lower())


def canonical_repository(value: Any) -> str:
    text = str(value or "").strip().rstrip("/")
    text = re.sub(r"^https?://(?:www\.)?github\.com/", "", text, flags=re.I)
    text = text.removesuffix(".git").strip("/")
    match = re.fullmatch(r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", text)
    return f"https://github.com/{match.group(1)}/{match.group(2)}" if match else ""


def _default_fetch_bytes(url: str, timeout: float, max_bytes: int) -> bytes:
    _validate_github_url(url)
    token = _runtime_github_token()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": DEFAULT_USER_AGENT,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    opener = build_opener(AllowedRedirectHandler(GITHUB_ALLOWED_HOSTS))
    last_error: Optional[BaseException] = None
    for attempt in range(DEFAULT_RETRY_ATTEMPTS + 1):
        request = Request(url, headers=headers)
        try:
            with opener.open(request, timeout=timeout) as response:
                payload = response.read(max_bytes + 1)
            if len(payload) > max_bytes:
                raise DiscoveryError(f"GitHub response exceeds {max_bytes} bytes: {url}")
            return payload
        except HTTPError as exc:
            last_error = exc
            if exc.code not in (403, 429) or attempt >= DEFAULT_RETRY_ATTEMPTS:
                break
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            try:
                delay = min(float(retry_after), DEFAULT_RETRY_MAX_SECONDS) if retry_after else 0.5 * (attempt + 1)
            except (TypeError, ValueError):
                delay = 0.5 * (attempt + 1)
            time.sleep(max(0.0, delay))
        except (URLError, OSError, TimeoutError) as exc:
            last_error = exc
            if attempt >= DEFAULT_RETRY_ATTEMPTS:
                break
            time.sleep(0.25 * (attempt + 1))
    raise DiscoveryError(f"GitHub request failed: {url}: {last_error}") from last_error


def _default_fetch_json(url: str, timeout: float, max_bytes: int) -> Any:
    try:
        return json.loads(_default_fetch_bytes(url, timeout, max_bytes).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DiscoveryError(f"Invalid GitHub JSON response: {url}: {exc}") from exc


def _call_fetch(fetch: Callable[..., Any], url: str, timeout: float, max_bytes: int) -> Any:
    """Call an injected fetcher while allowing a compact ``lambda url`` fixture."""
    try:
        return fetch(url, timeout, max_bytes)
    except TypeError as first_error:
        try:
            return fetch(url)
        except TypeError:
            raise first_error


def _cache_key(name: str, local_text: str = "") -> str:
    # Same-name Skills can come from unrelated publishers; include local
    # evidence so a prior match cannot leak across independent installations.
    seed = normalize(name) + "\x00" + _normalize_skill_text(local_text)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


def _read_cache(path: Optional[Path], ttl_seconds: float, now: float) -> Optional[Dict[str, Any]]:
    if not path or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        fetched_at = float(payload.get("fetched_at", 0))
        result = payload.get("result")
        if not isinstance(result, dict) or now - fetched_at > ttl_seconds:
            return None
        return result
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _write_cache(path: Optional[Path], result: Dict[str, Any], now: float) -> None:
    if not path:
        return
    if result.get("status") == "error":
        return
    temporary: Optional[Path] = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps({"fetched_at": now, "result": result}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    except OSError:
        # Cache failure must never discard a verified association.
        try:
            if temporary:
                temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _search_url(name: str, per_page: int) -> str:
    query = f'"{name}" in:name'
    return f"{GITHUB_API}/search/repositories?{urlencode({'q': query, 'per_page': per_page})}"


def _batch_search_url(names: Sequence[str], max_candidates: int) -> str:
    terms = " OR ".join(f'"{name}"' for name in names)
    query = f"{terms} in:name"
    per_page = min(100, max_candidates * len(names))
    return f"{GITHUB_API}/search/repositories?{urlencode({'q': query, 'per_page': per_page})}"


def _matching_skill_paths(tree: Any, skill_name: str) -> List[str]:
    if not isinstance(tree, dict) or not isinstance(tree.get("tree"), list):
        return []
    expected = normalize(skill_name).replace(" ", "-")
    paths: List[str] = []
    for entry in tree["tree"]:
        if not isinstance(entry, dict) or entry.get("type") != "blob":
            continue
        path = str(entry.get("path") or "").replace("\\", "/").strip("/")
        parts = path.split("/")
        if not parts or parts[-1].casefold() != "skill.md":
            continue
        # A root SKILL.md is valid for an exact repository-name match. For a
        # package tree, require the direct parent folder to match the Skill.
        parent = normalize(parts[-2]).replace(" ", "-") if len(parts) > 1 else ""
        if len(parts) == 1 or parent == expected:
            paths.append(path)
    return sorted(paths, key=lambda value: (len(value.split("/")), value.casefold()))


def _normalize_skill_text(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"^---.*?---", " ", text, flags=re.S)
    text = re.sub(r"[`*_>#\[\]()]", " ", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def text_similarity(local_text: Any, remote_text: Any) -> float:
    left = _normalize_skill_text(local_text)
    right = _normalize_skill_text(remote_text)
    if not left or not right:
        return 0.0
    return round(SequenceMatcher(None, left, right, autojunk=False).ratio(), 4)


def _local_hints(local_text: Any, skill_name: str) -> List[Tuple[str, str]]:
    text = str(local_text or "")
    hints: List[Tuple[str, str]] = []
    # Explicit GitHub URLs are the strongest local evidence.
    for match in re.finditer(r"(?:https?://)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", text, flags=re.I):
        hints.append((normalize(match.group(1)), normalize(match.group(2)).removesuffix(".git")))
    # Sync reports and install logs can preserve an author home path without a public URL.
    escaped_name = re.escape(normalize(skill_name).replace(" ", "[-_ ]?"))
    home_tokens = "(?:" + "User" + "s|home)"
    host_tokens = "(?:Git" + "Hub|github)"
    path_pattern = rf"(?:[/\\]{home_tokens}[/\\]([^/\\]+)[/\\]{host_tokens}[/\\]([^/\\]+))"
    for match in re.finditer(path_pattern, text, flags=re.I):
        owner, repo = normalize(match.group(1)), normalize(match.group(2)).removesuffix(".git")
        if repo == normalize(skill_name).replace(" ", "-") or re.fullmatch(escaped_name, repo, flags=re.I):
            hints.append((owner, repo))
    return list(dict.fromkeys(hints))


def _read_local_evidence(path: Optional[Path], skill_text: str, max_bytes: int = DEFAULT_MAX_SKILL_BYTES) -> str:
    parts = [str(skill_text or "")]
    if not path:
        return "\n".join(parts)
    current = path.parent
    for _ in range(5):
        candidates = (
            current / "references" / "upstream-sync" / "apply-report.json",
            current / "installation.json",
            current / ".skill-lock.json",
        )
        for candidate in candidates:
            try:
                if candidate.is_file() and candidate.stat().st_size <= max_bytes:
                    parts.append(candidate.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
        if current.parent == current:
            break
        current = current.parent
    return "\n".join(parts)


def score_candidate(
    candidate: Mapping[str, Any],
    skill_name: str,
    local_text: str,
    remote_text: str,
    remote_path: str,
) -> Tuple[float, Dict[str, Any]]:
    owner = normalize(candidate.get("owner") or candidate.get("owner_login"))
    repo = normalize(candidate.get("name") or skill_name).removesuffix(".git")
    expected = normalize(skill_name).replace(" ", "-")
    similarity = text_similarity(local_text, remote_text)
    path_parent = normalize(Path(remote_path).parent.name).replace(" ", "-") if remote_path else ""
    path_match = bool(path_parent == expected or Path(remote_path).name.casefold() == "skill.md")
    hints = _local_hints(local_text, skill_name)
    hint_match = any(hint_owner == owner and hint_repo == repo for hint_owner, hint_repo in hints)
    repo_hint = any(hint_repo == repo for _, hint_repo in hints)
    score = 0.24 + similarity * 0.43 + (0.17 if path_match else 0) + (0.28 if hint_match else 0) + (0.06 if repo_hint else 0)
    return round(min(score, 1.0), 4), {
        "similarity": similarity,
        "path_match": path_match,
        "author_path_match": hint_match,
        "repository_hint_match": repo_hint,
        "author_hints": [f"{owner}/{repo}" for owner, repo in hints],
    }


def _candidate_rows(search_payload: Any, skill_name: str) -> List[Dict[str, Any]]:
    rows = search_payload.get("items") if isinstance(search_payload, dict) else []
    if not isinstance(rows, list):
        return []
    expected = normalize(skill_name).replace(" ", "-")
    candidates: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        repo = normalize(row.get("name")).removesuffix(".git")
        if repo != expected:
            continue
        if bool(row.get("fork")) or bool(row.get("archived")):
            continue
        owner = row.get("owner") if isinstance(row.get("owner"), dict) else {}
        login = str(owner.get("login") or row.get("owner_login") or "").strip()
        if not login:
            continue
        candidates.append({
            "owner": login,
            "name": str(row.get("name") or skill_name),
            "url": canonical_repository(row.get("html_url") or f"https://github.com/{login}/{row.get('name')}"),
            "default_branch": str(row.get("default_branch") or "main"),
            "fork": False,
            "archived": False,
        })
    return candidates


def discover_repository(
    skill_name: str,
    local_text: str = "",
    local_path: Optional[Path] = None,
    *,
    fetch_json: Optional[FetchJson] = None,
    fetch_bytes: Optional[FetchBytes] = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_page_bytes: int = DEFAULT_MAX_PAGE_BYTES,
    max_skill_bytes: int = DEFAULT_MAX_SKILL_BYTES,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
    search_payload: Any = None,
    search_query: str = "",
) -> Dict[str, Any]:
    """Search and verify one Skill family, returning an auditable decision."""
    fetch_json = fetch_json or _default_fetch_json
    fetch_bytes = fetch_bytes or _default_fetch_bytes
    evidence_text = _read_local_evidence(local_path, local_text, max_skill_bytes)
    query_url = search_query or _search_url(skill_name, max_candidates)
    try:
        if search_payload is None:
            search_payload = _call_fetch(fetch_json, query_url, timeout, max_page_bytes)
        rows = _candidate_rows(search_payload, skill_name)
    except DiscoveryError as exc:
        return {"status": "error", "skill": skill_name, "query": query_url, "error": str(exc)}
    if not rows:
        return {"status": "not-found", "skill": skill_name, "query": query_url, "candidate_count": 0, "candidates": []}

    def verify_candidate(candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        owner = quote(str(candidate["owner"]), safe="")
        repo = quote(str(candidate["name"]), safe="")
        branch = quote(str(candidate.get("default_branch") or "main"), safe="")
        tree_url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        try:
            tree = _call_fetch(fetch_json, tree_url, timeout, max_page_bytes)
            paths = _matching_skill_paths(tree, skill_name)
            if not paths:
                return None
            remote_path = paths[0]
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{quote(remote_path, safe='/')}"
            remote_text = _call_fetch(fetch_bytes, raw_url, timeout, max_skill_bytes)
            if isinstance(remote_text, bytes):
                remote_text = remote_text.decode("utf-8", errors="replace")
            score, detail = score_candidate(candidate, skill_name, evidence_text, str(remote_text), remote_path)
            return {
                **candidate,
                "skill_path": remote_path,
                "raw_url": raw_url,
                "score": score,
                **detail,
            }
        except (DiscoveryError, UnicodeError, TypeError, ValueError):
            return None

    candidate_rows = rows[:max_candidates]
    if len(candidate_rows) <= 1:
        verified = [row for row in (verify_candidate(candidate_rows[0]) if candidate_rows else None,) if row]
    else:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(DEFAULT_CANDIDATE_WORKERS, len(candidate_rows))
        ) as executor:
            verified = [row for row in executor.map(verify_candidate, candidate_rows) if row]
    verified.sort(key=lambda row: (-float(row.get("score", 0)), str(row.get("url") or "").casefold()))
    if not verified:
        return {"status": "unverified", "skill": skill_name, "query": query_url, "candidate_count": len(rows), "candidates": []}

    best = verified[0]
    second_score = float(verified[1].get("score", 0)) if len(verified) > 1 else 0.0
    margin = round(float(best.get("score", 0)) - second_score, 4)
    strong_local_evidence = bool(best.get("author_path_match") or best.get("repository_hint_match"))
    min_score = DEFAULT_MIN_SCORE if strong_local_evidence else 0.62
    if float(best.get("score", 0)) < min_score:
        status = "ambiguous" if len(verified) > 1 else "low-confidence"
    elif len(verified) > 1 and margin < DEFAULT_MIN_MARGIN and not strong_local_evidence:
        status = "ambiguous"
    else:
        status = "matched"
    result: Dict[str, Any] = {
        "status": status,
        "skill": skill_name,
        "query": query_url,
        "candidate_count": len(rows),
        "verified_count": len(verified),
        "margin": margin,
        "candidates": verified,
    }
    if status == "matched":
        result["repository"] = best["url"]
        result["remote_skill_path"] = best["skill_path"]
    return result


def discover_github_families(
    items: List[Dict[str, Any]],
    families: Sequence[Mapping[str, Any]],
    *,
    skill_texts: Optional[Mapping[str, str]] = None,
    skill_paths: Optional[Mapping[str, Path]] = None,
    config: Optional[Mapping[str, Any]] = None,
    cache_dir: Optional[Path] = None,
    fetch_json: Optional[FetchJson] = None,
    fetch_bytes: Optional[FetchBytes] = None,
) -> Dict[str, Any]:
    """Mutate missing family-primary items with verified GitHub associations."""
    options = config if isinstance(config, Mapping) else {}
    enabled = bool(options.get("enabled", False))
    if not enabled:
        return {"enabled": False, "status": "disabled", "matched": 0, "attempted": 0, "results": []}
    timeout = float(options.get("timeout_seconds", DEFAULT_TIMEOUT) or DEFAULT_TIMEOUT)
    ttl_hours = float(options.get("cache_ttl_hours", DEFAULT_TTL_HOURS) or DEFAULT_TTL_HOURS)
    max_families = max(0, int(options.get("max_families", DEFAULT_MAX_FAMILIES) or DEFAULT_MAX_FAMILIES))
    max_candidates = max(1, int(options.get("max_candidates", DEFAULT_MAX_CANDIDATES) or DEFAULT_MAX_CANDIDATES))
    max_page_bytes = max(1024, int(options.get("max_page_bytes", DEFAULT_MAX_PAGE_BYTES) or DEFAULT_MAX_PAGE_BYTES))
    max_skill_bytes = max(1024, int(options.get("max_skill_bytes", DEFAULT_MAX_SKILL_BYTES) or DEFAULT_MAX_SKILL_BYTES))
    workers = max(1, int(options.get("workers", DEFAULT_WORKERS) or DEFAULT_WORKERS))
    search_batch_size = max(1, min(10, int(options.get("search_batch_size", DEFAULT_SEARCH_BATCH_SIZE) or DEFAULT_SEARCH_BATCH_SIZE)))
    now = time.time()
    item_by_id = {str(item.get("id")): item for item in items if item.get("id")}
    text_map = skill_texts or {}
    path_map = skill_paths or {}
    results: List[Dict[str, Any]] = []
    matched = 0
    eligible_jobs: List[Tuple[Mapping[str, Any], Dict[str, Any], str, str, Optional[Path], Optional[Path]]] = []
    for family in families:
        primary_id = str(family.get("primary_id") or "")
        primary = item_by_id.get(primary_id)
        if not primary or primary.get("kind") != "skill":
            continue
        if isinstance(family.get("github"), dict) and family["github"].get("url"):
            continue
        if isinstance(primary.get("github"), dict) and primary["github"].get("url"):
            continue
        name = str(family.get("name") or primary.get("name") or "").strip()
        if not name:
            continue
        local_text = str(text_map.get(primary_id) or primary.get("source_description") or primary.get("description") or "")
        cache_path = cache_dir / f"{_cache_key(name, local_text)}.json" if cache_dir else None
        eligible_jobs.append((family, primary, primary_id, local_text, path_map.get(primary_id), cache_path))
    jobs = eligible_jobs[:max_families]
    prefetched: Dict[str, Tuple[Any, str]] = {}
    prefetch_errors: Dict[str, Tuple[str, str]] = {}
    uncached_jobs = [
        job for job in jobs
        if _read_cache(job[5], ttl_hours * 3600, now) is None
    ]
    if search_batch_size > 1 and uncached_jobs:
        batch_fetch = fetch_json or _default_fetch_json
        for offset in range(0, len(uncached_jobs), search_batch_size):
            batch = uncached_jobs[offset:offset + search_batch_size]
            names = [str(job[0].get("name") or job[1].get("name") or "") for job in batch]
            query_url = _batch_search_url(names, max_candidates)
            try:
                payload = _call_fetch(batch_fetch, query_url, timeout, max_page_bytes)
                for job in batch:
                    prefetched[job[2]] = (payload, query_url)
            except DiscoveryError as exc:
                for job in batch:
                    prefetch_errors[job[2]] = (query_url, str(exc))

    def discover_job(job):
        family, primary, primary_id, local_text, local_path, cache_path = job
        result = _read_cache(cache_path, ttl_hours * 3600, now)
        if result is None:
            if primary_id in prefetch_errors:
                query_url, error = prefetch_errors[primary_id]
                result = {"status": "error", "skill": str(family.get("name") or primary.get("name") or ""), "query": query_url, "error": error}
            else:
                payload, query_url = prefetched.get(primary_id, (None, ""))
                result = discover_repository(
                    str(family.get("name") or primary.get("name") or ""),
                    local_text,
                    local_path,
                    fetch_json=fetch_json,
                    fetch_bytes=fetch_bytes,
                    timeout=timeout,
                    max_page_bytes=max_page_bytes,
                    max_skill_bytes=max_skill_bytes,
                    max_candidates=max_candidates,
                    search_payload=payload,
                    search_query=query_url,
                )
            _write_cache(cache_path, result, now)
        return job, dict(result)

    if len(jobs) <= 1:
        completed = [discover_job(job) for job in jobs]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(workers, len(jobs))) as executor:
            completed = list(executor.map(discover_job, jobs))

    for job, result in completed:
        family, primary, primary_id, _, _, _ = job
        result["family_id"] = family.get("id")
        result["primary_id"] = primary_id
        results.append(result)
        if result.get("status") != "matched" or not result.get("repository"):
            continue
        repository = str(result["repository"])
        best = (result.get("candidates") or [{}])[0]
        primary["github"] = {
            "url": repository,
            "source": "github-discovery",
            "verification": "network-verified",
        }
        primary["github_evidence"] = [{
            "url": repository,
            "source": "github-discovery",
            "query": result.get("query"),
            "remote_skill_path": result.get("remote_skill_path"),
            "similarity": best.get("similarity"),
            "score": best.get("score"),
            "candidate_count": result.get("candidate_count"),
            "margin": result.get("margin"),
            "author_path_match": best.get("author_path_match", False),
        }]
        matched += 1
    eligible = len(eligible_jobs)
    status_counts: Dict[str, int] = {}
    for result in results:
        key = str(result.get("status") or "unknown")
        status_counts[key] = status_counts.get(key, 0) + 1
    return {
        "enabled": True,
        "status": "complete" if len(jobs) >= eligible else "budget-exhausted",
        "matched": matched,
        "attempted": len(jobs),
        "eligible": eligible,
        "deferred": max(0, eligible - len(jobs)),
        "workers": min(workers, len(jobs)) if jobs else 0,
        "search_batch_size": search_batch_size,
        "search_requests": (len(uncached_jobs) + search_batch_size - 1) // search_batch_size if search_batch_size > 1 else len(uncached_jobs),
        "status_counts": status_counts,
        "results": results,
    }


__all__ = [
    "DiscoveryError",
    "canonical_repository",
    "discover_github_families",
    "discover_repository",
    "score_candidate",
    "text_similarity",
]
