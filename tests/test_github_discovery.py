import importlib.util
import json
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.error import HTTPError


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "skills" / "agent-skill-catalog" / "scripts" / "github_discovery.py"
BUILD_SCRIPT = REPO_ROOT / "skills" / "agent-skill-catalog" / "scripts" / "build_catalog.py"


def load_module(path: Path, name: str):
    scripts = str(path.parent)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def repository(owner: str, name: str, *, fork: bool = False, archived: bool = False):
    return {
        "name": name,
        "html_url": f"https://github.com/{owner}/{name}",
        "default_branch": "main",
        "fork": fork,
        "archived": archived,
        "owner": {"login": owner},
    }


def fetchers(rows, trees, texts):
    def fetch_json(url, *_):
        if "/search/repositories?" in url:
            return {"items": rows}
        for key, value in trees.items():
            if f"/repos/{key}/git/trees/" in url:
                return {"tree": value}
        raise AssertionError(url)

    def fetch_bytes(url, *_):
        for key, value in texts.items():
            if f"/{key}/main/" in url:
                return value.encode("utf-8")
        raise AssertionError(url)

    return fetch_json, fetch_bytes


def test_author_evidence_selects_canonical_repository_over_same_name_copy():
    module = load_module(SCRIPT, "github_discovery_author")
    rows = [repository("copy", "baoyu-design"), repository("JimLiu", "baoyu-design")]
    tree = [{"type": "blob", "path": "SKILL.md"}]
    local = "Baoyu design tools. Source: https://github.com/JimLiu/baoyu-design"
    fetch_json, fetch_bytes = fetchers(rows, {"copy/baoyu-design": tree, "JimLiu/baoyu-design": tree}, {"copy/baoyu-design": local, "JimLiu/baoyu-design": local})
    result = module.discover_repository("baoyu-design", local, fetch_json=fetch_json, fetch_bytes=fetch_bytes)
    assert result["status"] == "matched"
    assert result["repository"] == "https://github.com/JimLiu/baoyu-design"


def test_equivalent_candidates_without_author_evidence_stay_ambiguous():
    module = load_module(SCRIPT, "github_discovery_ambiguous")
    rows = [repository("one", "demo"), repository("two", "demo")]
    tree = [{"type": "blob", "path": "SKILL.md"}]
    fetch_json, fetch_bytes = fetchers(rows, {"one/demo": tree, "two/demo": tree}, {"one/demo": "demo skill", "two/demo": "demo skill"})
    result = module.discover_repository("demo", "demo skill", fetch_json=fetch_json, fetch_bytes=fetch_bytes)
    assert result["status"] == "ambiguous"
    assert "repository" not in result


def test_forks_archives_and_repositories_without_matching_skill_are_rejected():
    module = load_module(SCRIPT, "github_discovery_reject")
    rows = [repository("one", "demo", fork=True), repository("two", "demo", archived=True), repository("three", "demo")]
    fetch_json, fetch_bytes = fetchers(rows, {"three/demo": [{"type": "blob", "path": "README.md"}]}, {})
    result = module.discover_repository("demo", "demo skill", fetch_json=fetch_json, fetch_bytes=fetch_bytes)
    assert result["status"] == "unverified"
    assert result["candidate_count"] == 1


def test_batch_only_queries_family_primary_and_reports_all_statuses():
    module = load_module(SCRIPT, "github_discovery_batch")
    items = [
        {"id": "primary", "name": "suite", "kind": "skill"},
        {"id": "child", "name": "suite-child", "kind": "skill"},
    ]
    families = [{"id": "family:suite", "name": "suite", "primary_id": "primary", "skill_ids": ["primary", "child"]}]
    calls = []

    def fake_discover(name, *_args, **_kwargs):
        calls.append(name)
        return {"status": "not-found", "skill": name, "candidates": []}

    module.discover_repository = fake_discover
    report = module.discover_github_families(items, families, config={"enabled": True, "workers": 4, "max_families": 256, "search_batch_size": 1})
    assert calls == ["suite"]
    assert report["eligible"] == report["attempted"] == 1
    assert report["status_counts"] == {"not-found": 1}


def test_cache_hit_avoids_network_and_errors_are_not_cached():
    module = load_module(SCRIPT, "github_discovery_cache")
    items = [{"id": "primary", "name": "demo", "kind": "skill", "description": "demo"}]
    families = [{"id": "family:demo", "name": "demo", "primary_id": "primary"}]
    with tempfile.TemporaryDirectory() as temp:
        cache = Path(temp)
        calls = 0

        def matched(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            return {"status": "matched", "repository": "https://github.com/one/demo", "candidates": [{"score": 1, "similarity": 1}]}

        module.discover_repository = matched
        module.discover_github_families(items, families, config={"enabled": True, "search_batch_size": 1}, cache_dir=cache)
        items[0].pop("github", None)
        module.discover_github_families(items, families, config={"enabled": True, "search_batch_size": 1}, cache_dir=cache)
        assert calls == 1

        error_cache = cache / "error.json"
        module._write_cache(error_cache, {"status": "error"}, time.time())
        assert not error_cache.exists()


def test_https_host_and_redirect_guards():
    module = load_module(SCRIPT, "github_discovery_security")
    for url in ("http://api.github.com/search/repositories", "https://example.com/search"):
        try:
            module._validate_github_url(url)
        except module.DiscoveryError:
            pass
        else:
            raise AssertionError(f"accepted unsafe URL: {url}")
    handler = module.AllowedRedirectHandler(module.GITHUB_ALLOWED_HOSTS)
    try:
        handler.redirect_request(None, None, 302, "redirect", {}, "https://example.com/steal")
    except HTTPError:
        pass
    else:
        raise AssertionError("accepted unsafe redirect")


def test_concurrent_batch_processes_every_eligible_family():
    module = load_module(SCRIPT, "github_discovery_concurrent")
    items = [{"id": f"id-{index}", "name": f"skill-{index}", "kind": "skill"} for index in range(12)]
    families = [{"id": f"family-{index}", "name": f"skill-{index}", "primary_id": f"id-{index}"} for index in range(12)]
    threads = set()
    lock = threading.Lock()

    def fake_discover(name, *_args, **_kwargs):
        with lock:
            threads.add(threading.get_ident())
        time.sleep(0.01)
        return {"status": "not-found", "skill": name, "candidates": []}

    module.discover_repository = fake_discover
    report = module.discover_github_families(items, families, config={"enabled": True, "workers": 4, "max_families": 256, "search_batch_size": 1})
    assert report["attempted"] == report["eligible"] == 12
    assert report["deferred"] == 0
    assert report["status_counts"] == {"not-found": 12}
    assert len(threads) > 1


def test_discovered_repository_flows_into_preview_and_disable_flag_skips_network():
    builder = load_module(BUILD_SCRIPT, "build_catalog_discovery_plumbing")
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "skills"
        skill = root / "demo"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: demo\ndescription: Demo skill.\n---\n", encoding="utf-8")
        config = builder.load_config(REPO_ROOT / "skills" / "agent-skill-catalog" / "references" / "catalog-config.json")
        observed = []

        def fake_discovery(items, _families, **_kwargs):
            items[0]["github"] = {"url": "https://github.com/one/demo", "source": "github-discovery", "verification": "network-verified"}
            return {"enabled": True, "status": "complete", "matched": 1, "attempted": 1, "results": []}

        def fake_preview(url, *_args):
            observed.append(url)
            return {}

        builder.discover_github_families = fake_discovery
        builder.github_preview_image = fake_preview
        builder.scan(config, [{"path": str(root), "label": "Skills", "kind": "skill"}], False, Path(temp) / "cache", no_github_discovery=False)
        assert observed == ["https://github.com/one/demo"]

        builder.discover_github_families = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network called"))
        builder.scan(config, [{"path": str(root), "label": "Skills", "kind": "skill"}], False, Path(temp) / "offline-cache", no_github_discovery=True)


def test_published_default_enables_discovery():
    builder = load_module(BUILD_SCRIPT, "build_catalog_default_discovery")
    config = builder.load_config(REPO_ROOT / "skills" / "agent-skill-catalog" / "references" / "catalog-config.json")
    assert config["github_discovery"]["enabled"] is True


def test_batch_search_reuses_one_search_response_for_a_group():
    module = load_module(SCRIPT, "github_discovery_search_batch")
    items = [{"id": f"id-{index}", "name": f"skill-{index}", "kind": "skill"} for index in range(12)]
    families = [{"id": f"family-{index}", "name": f"skill-{index}", "primary_id": f"id-{index}"} for index in range(12)]
    search_calls = []

    def fetch_json(url, *_args):
        if "/search/repositories?" in url:
            search_calls.append(url)
            return {"items": []}
        raise AssertionError(url)

    report = module.discover_github_families(
        items,
        families,
        config={"enabled": True, "workers": 4, "search_batch_size": 5},
        fetch_json=fetch_json,
    )
    assert report["attempted"] == 12
    assert report["search_requests"] == 3
    assert len(search_calls) == 3
